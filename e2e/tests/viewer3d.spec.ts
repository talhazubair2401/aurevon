import { execSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

/*
 * M6 3D viewer on the storefront (V-03 port of the P-09 v2 checks), against the production builds behind the
 * proxy. The stack runs with THREED_FOR_SHOPPERS on so the viewer can be tested; everywhere else it stays off
 * until V-01 to V-03 pass. The demo model (variants ivory and sage) goes through the real pipeline and approval.
 */

const MANAGE = process.env.E2E_MANAGE ?? "cd ../backend && python manage.py";
const PRODUCT = "/en/products/block-print-kurta";
const viewer = (page: Page) => page.locator("[data-viewer3d]");

test.beforeAll(() => {
  execSync(`${MANAGE} seed_demo_3d block-print-kurta --name garment.glb`, {
    input: readFileSync("../packages/asset-pipeline/fixtures/garment.glb"),
    stdio: ["pipe", "inherit", "inherit"],
  });
});

async function watchViolations(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __csp: unknown[] };
    w.__csp = [];
    document.addEventListener("securitypolicyviolation", (e) => {
      w.__csp.push({ directive: e.effectiveDirective, blockedURI: e.blockedURI });
    });
  });
}

test("the image comes first, then 3D takes over with zero CSP violations (V-05)", async ({
  page,
  request,
}, testInfo) => {
  // Server HTML: the product image is there before any 3D code runs.
  const html = await (await request.get(`${PRODUCT}?colour=sage`)).text();
  expect(html).toContain("data-viewer3d");
  expect(html).toContain('data-phase="loading"');
  expect(html).not.toMatch(/<canvas/);

  await watchViolations(page);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const started = Date.now();
  await page.goto(`${PRODUCT}?colour=sage`);
  await expect(viewer(page)).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
  const readyMs = Date.now() - started;
  await expect(viewer(page)).toHaveAttribute("data-showing", "3d");
  await expect(viewer(page)).toHaveAttribute("data-decoder", "wasm"); // Draco WebAssembly allowed by the CSP
  await expect(page.getByText("3D view shown in Sage")).toBeVisible();
  const canvas = page.getByRole("application", { name: /3D view of the garment/ });
  await expect(canvas).toBeVisible();

  const violations = await page.evaluate(() => (window as unknown as { __csp: unknown[] }).__csp);
  mkdirSync("results", { recursive: true });
  writeFileSync(
    `results/csp-v05-3d-${testInfo.project.name}.json`,
    JSON.stringify({ date: new Date().toISOString(), page: PRODUCT, readyMs, violations }, null, 2),
  );
  expect(violations).toEqual([]);
  expect(errors).toEqual([]);
});

test("the shopper can go back to the image and on to 3D; hidden 3D doesn't render", async ({
  page,
}) => {
  await page.goto(PRODUCT);
  await expect(viewer(page)).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
  await expect(viewer(page)).toHaveAttribute("data-rendering", "true");

  await page.getByRole("button", { name: "Show image" }).click();
  await expect(viewer(page)).toHaveAttribute("data-showing", "image");
  await expect(viewer(page)).toHaveAttribute("data-rendering", "false");
  await page.getByRole("button", { name: "Show 3D" }).click();
  await expect(viewer(page)).toHaveAttribute("data-showing", "3d");

  // Off screen: no rendering (D3). A short window, so the stage can scroll fully out of view.
  const size = page.viewportSize()!;
  await page.setViewportSize({ width: size.width, height: 360 });
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(viewer(page)).toHaveAttribute("data-rendering", "false");
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect(viewer(page)).toHaveAttribute("data-rendering", "true");
});

test("colour changes switch the material variant without reloading the model", async ({ page }) => {
  await page.goto(`${PRODUCT}?colour=ivory`);
  await expect(viewer(page)).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
  await expect(page.getByText("3D view shown in Ivory")).toBeVisible();
  const loads: string[] = [];
  page.on("request", (r) => {
    if (r.url().endsWith(".glb")) loads.push(r.url());
  });
  await page.getByRole("link", { name: "Sage" }).first().click();
  await expect(page.getByText("3D view shown in Sage")).toBeVisible();
  await expect(viewer(page)).toHaveAttribute("data-phase", "ready");
  expect(loads).toEqual([]);
});

test("the mouse wheel scrolls the page; Ctrl + wheel zooms (D-05)", async ({ page, isMobile }) => {
  test.skip(isMobile, "no mouse wheel on phones; pinch is unchanged");
  await page.goto(PRODUCT);
  await expect(viewer(page)).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
  const box = (await viewer(page).boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 3);

  await page.mouse.wheel(0, 300);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(100);
  await expect(page.getByText(/Use (Ctrl|⌘) \+ scroll to zoom/)).toBeVisible();

  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(200);
  const after = (await viewer(page).boundingBox())!;
  await page.mouse.move(after.x + after.width / 2, after.y + after.height / 3);
  await page.keyboard.down("Control");
  await page.mouse.wheel(0, -300);
  await page.keyboard.up("Control");
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
});

test("keyboard and buttons work the 3D view", async ({ page }) => {
  await page.goto(PRODUCT);
  await expect(viewer(page)).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
  const rotate = page.getByRole("button", { name: "Auto-rotate" });
  await rotate.click();
  await expect(rotate).toHaveAttribute("aria-pressed", "false");
  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.getByRole("button", { name: "Reset view" }).click();
  await expect(rotate).toHaveAttribute("aria-pressed", "true");
  const canvas = page.getByRole("application", { name: /3D view of the garment/ });
  await canvas.focus();
  await page.keyboard.press("ArrowLeft");
  await expect(rotate).toHaveAttribute("aria-pressed", "false"); // keys take over from auto-rotate
  await page.keyboard.press("Home");
  await expect(rotate).toHaveAttribute("aria-pressed", "true");
});

test("a model that fails keeps the image, says so and can be retried", async ({ page }) => {
  let fail = true;
  await page.route("**/media/products/3d/*.glb", (route) =>
    fail ? route.fulfill({ status: 503, body: "" }) : route.fallback(),
  );
  await page.goto(PRODUCT);
  await expect(viewer(page)).toHaveAttribute("data-phase", "failed", { timeout: 60_000 });
  await expect(viewer(page)).toHaveAttribute("data-showing", "image");
  await expect(page.getByText("The 3D view couldn't load.")).toBeVisible();
  await expect(page.getByRole("img").first()).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(viewer(page)).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
});

test("a damaged file fails with a reason instead of a spinner", async ({ page }) => {
  await page.route("**/media/products/3d/*.glb", (route) =>
    route.fulfill({
      status: 200,
      contentType: "model/gltf-binary",
      body: readFileSync("../packages/asset-pipeline/fixtures/truncated.glb"),
    }),
  );
  await page.goto(PRODUCT);
  await expect(viewer(page)).toHaveAttribute("data-phase", "failed", { timeout: 60_000 });
  await expect(viewer(page)).toHaveAttribute("data-error", "truncated");
});
