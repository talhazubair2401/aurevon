import { execSync } from "node:child_process";
import { createHmac } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

/*
 * The M2 staff journey, end to end through the proxy, the real API and real email (Mailpit):
 * bootstrap Owner -> enrol with an authenticator -> single-Owner warning -> invite staff ->
 * staff enrols -> Owner suspends them -> their session ends at once -> audit log shows it.
 * Runs once (desktop project only, see playwright.config.ts) against a fresh database, as in CI.
 */

const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";
const MANAGE = process.env.E2E_MANAGE ?? "cd ../backend && python manage.py";
const OWNER = "owner@aurevon.test";
const MEMBER = "support.member@aurevon.test";
const PASSWORD = "quiet linen evening 2026";

// No retries: the journey creates the first Owner, which can only happen once per database.
test.describe.configure({ mode: "serial", retries: 0 });

// --- RFC 6238 TOTP, as an authenticator app computes it ---
function base32(secret: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of secret.replace(/=+$/, ""))
    bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const bytes = bits.match(/.{8}/g) ?? [];
  return Buffer.from(bytes.map((b) => parseInt(b, 2)));
}
const lastStep = new Map<string, number>();
/** A code for the current step, or the next one if the current step was already used (replay is refused). */
function totp(secret: string): string {
  let step = Math.floor(Date.now() / 1000 / 30);
  if ((lastStep.get(secret) ?? -1) >= step) step = (lastStep.get(secret) ?? step) + 1;
  lastStep.set(secret, step);
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac("sha1", base32(secret)).update(counter).digest();
  const offset = digest[digest.length - 1]! & 0x0f;
  const value = (digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return value.toString().padStart(6, "0");
}

// --- Mailpit ---
async function latestLinkTo(page: Page, address: string, pathPart: string): Promise<string> {
  for (let attempt = 0; attempt < 40; attempt++) {
    const search = await page.request.get(
      `${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:"${address}"`)}`,
    );
    const { messages } = (await search.json()) as { messages: { ID: string }[] };
    for (const message of messages) {
      const body = (await (
        await page.request.get(`${MAILPIT}/api/v1/message/${message.ID}`)
      ).json()) as { Text: string };
      const match = body.Text.match(new RegExp(`https?://\\S+/staff/${pathPart}#token=[\\w-]+`));
      if (match) return match[0];
    }
    await page.waitForTimeout(250);
  }
  throw new Error(`no ${pathPart} email to ${address}`);
}

async function enrol(page: Page, link: string): Promise<string> {
  await page.goto(link);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Set up your staff account");
  const secret = (await page.getByTestId("totp-secret").textContent())!.trim();
  await page.getByLabel("New password (at least 12 characters)").fill(PASSWORD);
  await page.getByLabel("Repeat the password").fill(PASSWORD);
  await page.getByLabel("Code shown in your authenticator app").fill(totp(secret));
  await page.getByRole("button", { name: "Finish set-up" }).click();
  await expect(page.getByTestId("recovery-codes").locator("li")).toHaveCount(10);
  await page.getByRole("button", { name: "I've saved them" }).click();
  return secret;
}

let ownerSecret = "";

test("the first Owner is bootstrapped, enrols and sees the single-Owner warning", async ({
  page,
}) => {
  execSync(`${MANAGE} create_owner --email ${OWNER} --name "First Owner"`, { stdio: "inherit" });
  ownerSecret = await enrol(page, await latestLinkTo(page, OWNER, "enroll"));
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Welcome, First Owner");
  await expect(page.getByTestId("single-owner-warning")).toBeVisible();
  // The link token never stays in the address bar.
  expect(page.url()).not.toContain("token=");
});

test("Owner invites a staff member, who enrols, and suspension ends their session at once", async ({
  browser,
}) => {
  const owner = await browser.newPage();
  await owner.goto("/staff/sign-in");
  await owner.getByLabel("Email").fill(OWNER);
  await owner.getByLabel("Password").fill(PASSWORD);
  await owner.getByRole("button", { name: "Continue" }).click();
  await owner.getByLabel("Authenticator code").fill(totp(ownerSecret));
  await owner.getByRole("button", { name: "Sign in" }).click();
  await expect(owner.getByTestId("single-owner-warning")).toBeVisible();

  await owner
    .getByRole("navigation", { name: "Staff" })
    .getByRole("link", { name: "Team" })
    .click();
  await owner.getByLabel("Full name").fill("Sana Support");
  await owner.getByLabel("Email").fill(MEMBER);
  await owner.getByLabel("Role").selectOption("support");
  await owner.getByRole("button", { name: "Send invitation" }).click();
  await expect(owner.getByText(`Invitation sent to ${MEMBER}`)).toBeVisible();

  const member = await browser.newPage();
  await enrol(member, await latestLinkTo(member, MEMBER, "enroll"));
  await expect(member.getByRole("heading", { level: 1 })).toContainText("Welcome, Sana Support");
  await expect(
    member.getByRole("navigation", { name: "Staff" }).getByRole("link", { name: "Team" }),
  ).toHaveCount(0); // Support can't manage staff

  await owner.reload();
  await owner.getByTestId(`staff-row-${MEMBER}`).getByRole("button", { name: "Manage" }).click();
  const panel = owner.getByTestId("account-panel");
  await panel.getByLabel("Reason for suspension").fill("End-to-end test");
  await panel.getByRole("button", { name: "Suspend" }).click();
  const stepUp = owner.getByRole("dialog");
  if (await stepUp.isVisible().catch(() => false)) {
    await stepUp.getByLabel("Authenticator code").fill(totp(ownerSecret));
    await stepUp.getByRole("button", { name: "Confirm" }).click();
  }
  await expect(panel.getByText("Suspended. All sessions ended.")).toBeVisible();

  await member.reload();
  await expect(member).toHaveURL(/\/staff\/sign-in$/);

  await owner
    .getByRole("navigation", { name: "Staff" })
    .getByRole("link", { name: "Audit log" })
    .click();
  await expect(owner.getByRole("cell", { name: "staff.suspended" })).toBeVisible();
});

/** Waits until the authenticator shows a code that hasn't been used yet (codes are single-use, decision 0003). */
async function freshStep(secret: string): Promise<void> {
  const used = lastStep.get(secret) ?? -1;
  while (Math.floor(Date.now() / 1000 / 30) <= used) await new Promise((r) => setTimeout(r, 500));
}

async function signInOwner(browser: import("@playwright/test").Browser): Promise<Page> {
  await freshStep(ownerSecret);
  const owner = await browser.newPage();
  await owner.goto("/staff/sign-in");
  await owner.getByLabel("Email").fill(OWNER);
  await owner.getByLabel("Password").fill(PASSWORD);
  await owner.getByRole("button", { name: "Continue" }).click();
  await owner.getByLabel("Authenticator code").fill(totp(ownerSecret));
  await owner.getByRole("button", { name: "Sign in" }).click();
  await expect(owner.getByTestId("single-owner-warning")).toBeVisible();
  return owner;
}

/*
 * M4 content journey: a new page stays private as a draft, goes live on publish, later edits stay private
 * until published, the store shows each publish at once (cache refreshed on publish, decision 0005), and
 * renaming the live page keeps its old address working through a redirect.
 */
test("Owner creates, publishes, edits and renames a content page", async ({ browser, page }) => {
  test.setTimeout(120_000); // may wait up to one authenticator step for a fresh code
  const owner = await signInOwner(browser);
  await owner
    .getByRole("navigation", { name: "Staff" })
    .getByRole("link", { name: "Content" })
    .click();
  await expect(owner.getByTestId("panel-hero")).toBeVisible();
  await owner
    .getByRole("navigation", { name: "Content" })
    .getByRole("link", { name: "Pages" })
    .click();
  await owner.getByRole("link", { name: "New page" }).click();
  await owner.getByLabel("Address: /pages/…").fill("size-guide");
  await owner.locator("#page-en-title").fill("Size guide");
  await owner.getByLabel("Block 1 text").first().fill("How our pieces fit.");
  await owner.getByRole("button", { name: "Create draft" }).click();
  await expect(owner.getByText("Not published")).toBeVisible();

  expect((await page.goto("/en/pages/size-guide"))!.status()).toBe(404);

  await owner.getByRole("button", { name: "Publish", exact: true }).click();
  await expect(owner.getByText("Published. The store shows it now.")).toBeVisible();
  await page.goto("/en/pages/size-guide");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Size guide");

  await owner.locator("#page-en-title").fill("Size and fit");
  await owner.getByRole("button", { name: "Save draft" }).click();
  await expect(owner.getByText("Draft saved.")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Size guide");

  await owner.getByRole("button", { name: "Publish", exact: true }).click();
  await expect(owner.getByText("Published. The store shows it now.")).toBeVisible();
  // Well inside the one-minute cache: only the refresh on publish can make this pass.
  await expect(async () => {
    await page.reload();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Size and fit", {
      timeout: 1000,
    });
  }).toPass({ timeout: 15_000 });

  await owner.getByLabel("Address: /pages/…").fill("fit-guide");
  await owner.getByRole("button", { name: "Save settings" }).click();
  await expect(owner.getByText("Page settings saved.")).toBeVisible();
  await page.goto("/ur/pages/size-guide");
  await expect(page).toHaveURL(/\/ur\/pages\/fit-guide$/);

  await owner.getByRole("navigation", { name: "Staff" }).getByRole("link", { name: "SEO" }).click();
  await owner.getByRole("link", { name: "Redirects" }).click();
  await expect(owner.getByRole("cell", { name: "/pages/size-guide", exact: true })).toBeVisible();
  await owner
    .getByRole("navigation", { name: "Staff" })
    .getByRole("link", { name: "Audit log" })
    .click();
  await expect(owner.getByRole("cell", { name: "cms.page.publish" }).first()).toBeVisible();
});

/*
 * M5 catalogue journey: a new product is a draft with a style number, gets colours and sizes (SKUs and stock
 * records), a price, is published and appears on the store with its own page.
 */
test("Owner creates, prices and publishes a product", async ({ browser, page }) => {
  test.setTimeout(120_000);
  const owner = await signInOwner(browser);
  await owner
    .getByRole("navigation", { name: "Staff" })
    .getByRole("link", { name: "Catalogue" })
    .click();
  await owner.getByRole("link", { name: "New product" }).click();
  await owner.getByLabel("Address: /products/…").fill("e2e-linen-kurta");
  await owner.getByLabel("Category").selectOption({ label: "Women · Kurtas" });
  await owner.locator("#copy-en-name").fill("E2E Linen Kurta");
  await owner.getByRole("button", { name: "Create draft" }).click();
  await expect(owner.getByRole("heading", { name: "Colours and sizes" })).toBeVisible();

  await owner.getByRole("checkbox", { name: "Ivory" }).check();
  await owner.getByRole("checkbox", { name: "S", exact: true }).check();
  await owner.getByRole("checkbox", { name: "M", exact: true }).check();
  await owner.getByRole("button", { name: "Save colours and sizes" }).click();
  await expect(owner.getByText("Colours and sizes saved.")).toBeVisible();
  await expect(owner.getByRole("cell", { name: /^AV-WKU-\d{4}-IVR-M$/ })).toBeVisible();

  await owner.getByLabel("Base price, for every variant without its own").fill("11800");
  await owner.getByRole("button", { name: "Save prices" }).click();
  const stepUp = owner.getByRole("dialog");
  if (await stepUp.isVisible().catch(() => false)) {
    await freshStep(ownerSecret);
    await stepUp.getByLabel("Authenticator code").fill(totp(ownerSecret));
    await stepUp.getByRole("button", { name: "Confirm" }).click();
  }
  await expect(owner.getByText("Prices saved.")).toBeVisible();

  await owner.getByLabel("Image file").setInputFiles("fixtures/product-photo.jpg");
  await owner.getByLabel("Colour", { exact: true }).selectOption("ivory");
  await owner.getByLabel("Description for screen readers (English)").fill("E2E kurta, front");
  await owner.getByRole("button", { name: "Upload image" }).click();
  await expect(owner.getByText("Image added.")).toBeVisible();

  expect((await page.goto("/en/products/e2e-linen-kurta"))!.status()).toBe(404);
  await owner.getByRole("button", { name: "Publish", exact: true }).click();
  await expect(owner.getByText("Published. The store shows it now.")).toBeVisible();
  await page.goto("/en/products/e2e-linen-kurta");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("E2E Linen Kurta");
  await expect(page.getByText(/Rs\s?11,800/).first()).toBeVisible();
  const photo = page.getByRole("img", { name: "E2E kurta, front" }).first();
  await expect(photo).toBeVisible();
  const src = (await photo.getAttribute("src"))!;
  expect(src).toMatch(/^\/media\/products\/[0-9a-f]+-page\.webp$/);
  const media = await page.request.get(src);
  expect(media.status()).toBe(200);
  expect(media.headers()["content-type"]).toBe("image/webp");
  expect(media.headers()["cache-control"]).toContain("immutable");

  await owner.getByRole("button", { name: "Archive" }).click();
  await expect(owner.getByText("Moved to archived.")).toBeVisible();
  expect((await page.goto("/en/products/e2e-linen-kurta"))!.status()).toBe(404);
});

/*
 * M6 model workflow: upload a .glb, the pipeline checks and compresses it into a draft, staff preview it in the
 * shoppers' viewer through a short-lived signed address, and only a confirmed check lets it be approved.
 */
test("Owner uploads, previews and approves a 3D model", async ({ browser }) => {
  test.setTimeout(180_000);
  const owner = await signInOwner(browser);
  await owner.goto("/staff/catalog");
  await owner.getByRole("link", { name: "Block-Print Kurta" }).click();
  const panel = owner.getByRole("region", { name: "3D model" });
  await expect(panel).toBeVisible();
  const before = await panel.locator('[data-model3d="draft"]').count();
  await panel
    .getByLabel("Model file (.glb)")
    .setInputFiles("../packages/asset-pipeline/fixtures/garment-textured.glb");
  await panel.getByRole("button", { name: "Upload model" }).click();
  const draft = panel.locator('[data-model3d="draft"]').nth(before);
  await expect(draft).toBeVisible({ timeout: 90_000 });
  await expect(draft.getByText("garment-textured.glb")).toBeVisible();

  const preview = draft.locator("[data-viewer3d]");
  await expect(preview).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
  const approve = draft.getByRole("button", { name: "Approve model" });
  await expect(approve).toBeDisabled();
  await draft.getByRole("checkbox", { name: /I checked this model in the viewer/ }).check();
  await approve.click();
  await expect(panel.getByText("Approved.")).toBeVisible();
  await expect(panel.locator('[data-model3d="approved"]').first()).toBeVisible();
});

test("a customer session is never accepted by the staff API", async ({ request }) => {
  const email = `shopper-${Date.now()}@aurevon.test`;
  await request.post("/api/v1/auth/register", { data: { email, password: PASSWORD } });
  const login = await request.post("/api/v1/auth/login", { data: { email, password: PASSWORD } });
  expect(login.status()).toBe(200);
  expect((await request.get("/api/v1/auth/session")).status()).toBe(200);
  expect((await request.get("/api/v1/staff/auth/session")).status()).toBe(401);
  expect((await request.get("/api/v1/staff/accounts")).status()).toBe(401);
});
