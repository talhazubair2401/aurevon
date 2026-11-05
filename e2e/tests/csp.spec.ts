import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test, type APIResponse, type Page } from "@playwright/test";

// D-08 (decision 0005): enforcing CSP with a per-request nonce on every page of both apps, verified against the
// production builds behind the routing proxy. Also V-05: zero violations, recorded per run.

const PAGES = [
  "/staff",
  "/en",
  "/ur",
  "/en/does-not-exist",
  "/ur/does-not-exist",
  "/en/collections",
  "/ur/collections/heritage-edit",
  "/en/pages/about",
  "/ur/pages/returns",
  "/en/products/relaxed-chino",
  "/en/products/block-print-kurta", // 3D viewer (M6) when 3D is on for shoppers
  "/ur/search?q=kurta",
  "/staff/sign-in",
  "/staff/forgot-password",
  "/staff/enroll",
  "/staff/recover",
];

interface Violation {
  directive: string;
  blockedURI: string;
  sample: string;
}

async function watchViolations(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __csp: unknown[] };
    w.__csp = [];
    document.addEventListener("securitypolicyviolation", (e) => {
      w.__csp.push({ directive: e.effectiveDirective, blockedURI: e.blockedURI, sample: e.sample });
    });
  });
}

const violations = (page: Page) =>
  page.evaluate(() => (window as unknown as { __csp: Violation[] }).__csp);

function nonceOf(policy: string): string {
  const match = /'nonce-([A-Za-z0-9+/=]+)'/.exec(policy);
  expect(match, `nonce in ${policy}`).not.toBeNull();
  return match![1]!;
}

function expectNotPubliclyCacheable(response: APIResponse | null | undefined, path: string) {
  const cc = response?.headers()["cache-control"] ?? "";
  expect(cc, `Cache-Control on ${path}`).toContain("no-store");
  expect(cc, `Cache-Control on ${path}`).toContain("private");
  expect(cc, `Cache-Control on ${path}`).not.toMatch(/public|s-maxage|immutable/);
}

test("every page enforces the nonce policy with zero violations", async ({ page }, testInfo) => {
  await watchViolations(page);
  const results: Record<string, { policy: string; violations: Violation[] }> = {};

  for (const path of PAGES) {
    const response = await page.goto(path, { waitUntil: "networkidle" });
    const headers = response!.headers();
    const policy = headers["content-security-policy"] ?? "";
    expect(headers["content-security-policy-report-only"], path).toBeUndefined();
    expect(policy, path).toMatch(/script-src 'self' 'nonce-[^']+' 'strict-dynamic'/);
    expect(policy, path).not.toContain("unsafe-inline");
    expect(policy, path).not.toMatch(/'unsafe-eval'/); // 'wasm-unsafe-eval' (3D viewer, M6) is allowed
    expect(headers["reporting-endpoints"], path).toContain("/api/v1/csp-reports");

    // Every <script> in the server-sent HTML carries this response's nonce. (Chunks that those scripts load
    // later have none, and need none: 'strict-dynamic' trusts scripts created by trusted scripts.)
    const nonce = nonceOf(policy);
    const html = await response!.text();
    const tags = html.match(/<script\b[^>]*>/g) ?? [];
    expect(tags.length, path).toBeGreaterThan(0);
    for (const tag of tags) expect(tag, path).toContain(`nonce="${nonce}"`);

    // The app works: hydration ran (React attached), which is impossible if scripts were blocked.
    await expect(page.locator("body")).toBeVisible();
    results[path] = { policy, violations: await violations(page) };
  }

  mkdirSync("results", { recursive: true });
  writeFileSync(
    `results/csp-d08-${testInfo.project.name}.json`,
    JSON.stringify({ date: new Date().toISOString(), results }, null, 2),
  );
  for (const [path, r] of Object.entries(results)) expect(r.violations, path).toEqual([]);
});

test("pages hydrate under the enforced policy (interactive controls work)", async ({ page }) => {
  await page.goto("/en/does-not-exist");
  await page.getByRole("contentinfo").getByRole("link", { name: /اردو/ }).click();
  await expect(page).toHaveURL(/\/ur\/does-not-exist$/); // client-side navigation needs the bundles
});

test("the nonce changes on every request", async ({ request }) => {
  for (const path of ["/en", "/staff/sign-in"]) {
    const nonces = new Set<string>();
    for (let i = 0; i < 5; i++) {
      const response = await request.get(path);
      const policy = response.headers()["content-security-policy"]!;
      const nonce = nonceOf(policy);
      expect(await response.text(), path).toContain(`nonce="${nonce}"`);
      nonces.add(nonce);
    }
    expect(nonces.size, path).toBe(5);
  }
});

test("injected markup cannot run scripts (reflected-XSS simulation)", async ({ page }) => {
  // Rewrite the real /en response in flight, as an HTML-injection bug would, keeping its headers and policy.
  await page.route("**/en", async (route) => {
    const response = await route.fetch();
    const policy = response.headers()["content-security-policy"]!;
    const nonce = nonceOf(policy);
    const injected = [
      "<script>window.__inline = true</script>",
      '<script src="https://attacker.example/x.js"></script>',
      '<img src="/missing.png" onerror="window.__handler = true" alt="">',
      '<a id="js-link" href="javascript:window.__jsurl=true">x</a>',
      // Trusted code (carries the nonce) still cannot use eval: no 'unsafe-eval' in production.
      `<script nonce="${nonce}">try { eval("1"); window.__eval = "allowed" } catch { window.__eval = "blocked" }</script>`,
    ].join("");
    const body = (await response.text()).replace("</body>", `${injected}</body>`);
    await route.fulfill({ response, body });
  });
  await watchViolations(page);
  await page.goto("/en", { waitUntil: "networkidle" });
  await page.locator("#js-link").click();

  const state = await page.evaluate(() => {
    const w = window as unknown as Record<string, unknown>;
    return { inline: w.__inline, handler: w.__handler, jsurl: w.__jsurl, eval: w.__eval };
  });
  expect(state).toEqual({
    inline: undefined,
    handler: undefined,
    jsurl: undefined,
    eval: "blocked",
  });
  const directives = new Set((await violations(page)).map((v) => v.directive));
  for (const d of ["script-src-elem", "script-src-attr", "script-src"])
    expect(directives).toContain(d);
});

test("HTML carrying a nonce is never publicly cacheable", async ({ request }) => {
  for (const path of [...PAGES, "/staff/", "/staff"]) {
    expectNotPubliclyCacheable(await request.get(path, { maxRedirects: 0 }), path);
  }
  // React Server Component payloads used by client navigation also carry per-request data.
  const rsc = await request.get("/en", { headers: { RSC: "1" } });
  expectNotPubliclyCacheable(rsc, "/en (RSC)");
});

test("responses that bypass the apps' policy still get a strict script-free fallback", async ({
  request,
}) => {
  const response = await request.get("/no-such-file.txt");
  expect(response.status()).toBe(404);
  const policy = response.headers()["content-security-policy"] ?? "";
  expect(policy).toContain("default-src 'none'");
  expectNotPubliclyCacheable(response, "/no-such-file.txt");
});

test("content-hashed static assets keep long-term caching", async ({ page, request }) => {
  for (const path of ["/en", "/staff/sign-in"]) {
    const assets: string[] = [];
    page.on("response", (r) => {
      if (r.url().includes("/_next/static/")) assets.push(r.url());
    });
    await page.goto(path, { waitUntil: "networkidle" });
    const scripts = assets.filter((u) => u.endsWith(".js"));
    const fonts = assets.filter((u) => u.endsWith(".woff2"));
    expect(scripts.length, `${path} scripts`).toBeGreaterThan(0);
    expect(fonts.length, `${path} fonts`).toBeGreaterThan(0);
    for (const url of [scripts[0]!, fonts[0]!]) {
      const cc = (await request.get(url)).headers()["cache-control"] ?? "";
      expect(cc, url).toContain("public");
      expect(cc, url).toMatch(/max-age=31536000/);
      expect(cc, url).toContain("immutable");
      expect(cc, url).not.toContain("no-store");
    }
    page.removeAllListeners("response");
  }
});
