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
  await preview.scrollIntoViewIfNeeded(); // the viewer only renders on screen (D3), warm-up included
  await expect(preview).toHaveAttribute("data-phase", "ready", { timeout: 60_000 });
  const approve = draft.getByRole("button", { name: "Approve model" });
  await expect(approve).toBeDisabled();
  await draft.getByRole("checkbox", { name: /I checked this model in the viewer/ }).check();
  await approve.click();
  await expect(panel.getByText("Approved.")).toBeVisible();
  await expect(panel.locator('[data-model3d="approved"]').first()).toBeVisible();
});

/*
 * M8/M10 order operations: a guest orders with cash on delivery on the storefront; the Owner finds it, packs it,
 * dispatches it with the courier's tracking number and records delivery. The customer is emailed at dispatch.
 */
test("Owner packs, dispatches and delivers a cash-on-delivery order", async ({ browser, page }) => {
  test.setTimeout(180_000);
  // Storefront: a guest checkout with cash on delivery.
  const slugs = ["silk-column-dress", "relaxed-chino", "oxford-poplin-shirt", "wool-wrap-coat"];
  let target = "";
  for (const slug of slugs) {
    const res = await page.request.get(`/api/v1/catalog/products/${slug}/availability`);
    const v = (
      (await res.json()) as { variants: { colour: string; size: string; available: boolean }[] }
    ).variants.find((x) => x.available);
    if (v) {
      target = `/en/products/${slug}?colour=${v.colour}&size=${encodeURIComponent(v.size)}`;
      break;
    }
  }
  expect(target).not.toBe("");
  await page.goto(target);
  await page.getByTestId("add-to-bag").click();
  await expect(page.getByText("Added to your bag")).toBeVisible();
  const email = `ops.${Date.now()}@aurevon.test`;
  await page.goto("/en/checkout");
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="full_name"]').fill("Hira Shah");
  await page.locator('input[name="phone"]').fill("0300 7654321");
  await page.locator('input[name="line1"]').fill("Flat 3, Block B");
  await page.locator('input[name="area"]').fill("Gulberg");
  await page.locator('input[name="city"]').fill("Lahore");
  await page.locator('select[name="province"]').selectOption("punjab");
  await page.getByText("Cash on delivery", { exact: true }).click();
  await page.getByTestId("place-order").click();
  const number = (await page.getByTestId("order-number").textContent())!.trim();
  expect(number).toMatch(/^AV\d{6,}$/);

  // Staff: find it, pack, dispatch, deliver.
  const owner = await signInOwner(browser);
  await owner
    .getByRole("navigation", { name: "Staff" })
    .getByRole("link", { name: "Orders" })
    .click();
  await owner
    .getByLabel("Search by order number, name, email, phone or tracking number")
    .fill(number);
  await owner.getByRole("button", { name: "Search" }).click();
  await owner.getByRole("link", { name: number }).click();
  await expect(owner.getByText("Hira Shah", { exact: false }).first()).toBeVisible();
  await owner.getByRole("button", { name: "Start packing" }).click();
  await expect(owner.getByText("Order is now packing.")).toBeVisible();
  await owner.getByLabel("Courier tracking number").fill(`TRK${Date.now()}`);
  await owner.getByRole("button", { name: "Dispatch", exact: true }).click();
  await expect(owner.getByText(/Dispatched\. The customer has been emailed/)).toBeVisible();
  await owner.getByLabel("New tracking status").selectOption("delivered");
  await owner.getByRole("button", { name: "Add tracking update" }).click();
  await expect(owner.getByText("Tracking updated.")).toBeVisible();
  await expect(
    owner.getByRole("heading", { name: new RegExp(number) }).locator(".."),
  ).toContainText("Delivered");
  await expect(owner.getByText("COD: remittance pending").first()).toBeVisible();

  // The customer got the dispatch email with the tracking number.
  const search = await fetch(
    `${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:"${email}" subject:"on its way"`)}`,
  );
  expect(((await search.json()) as { messages: unknown[] }).messages.length).toBeGreaterThan(0);
});

/*
 * M9 inventory: the Owner adds a supplier, raises a purchase order, sends it and receives part of it; sellable
 * stock goes up by the received units and the movement shows the purchase order.
 */
test("Owner buys stock from a supplier and receives it", async ({ browser }) => {
  test.setTimeout(180_000);
  const owner = await signInOwner(browser);
  await owner.goto("/staff/inventory");
  const firstSku = (await owner.locator("table tbody tr td a").first().textContent())!.trim();
  const onHandBefore = Number(
    await owner.locator("table tbody tr").first().locator("td").nth(2).textContent(),
  );

  const supplier = `Lawn House ${Date.now()}`;
  await owner.getByRole("link", { name: "Suppliers" }).click();
  await owner.getByLabel("Name").last().fill(supplier);
  await owner.getByRole("button", { name: "Add supplier" }).click();
  await expect(owner.getByRole("heading", { name: supplier })).toBeVisible();

  await owner.getByRole("link", { name: "Purchase orders" }).click();
  await owner.getByLabel("Supplier").selectOption({ label: supplier });
  await owner.getByLabel("Line 1 SKU").fill(firstSku);
  await owner.getByLabel("Line 1 quantity").fill("10");
  await owner.getByLabel("Line 1 unit cost (PKR)").fill("1500");
  await owner.getByRole("button", { name: "Create draft" }).click();
  await expect(
    owner.getByRole("heading", { name: new RegExp(`PO-\\d+ · ${supplier}`) }),
  ).toBeVisible();
  await owner.getByRole("button", { name: "Mark as sent" }).click();
  await expect(owner.getByText("Marked as sent to the supplier.")).toBeVisible();
  await owner.getByLabel(`Units of ${firstSku} that arrived`).fill("4");
  await owner.getByRole("button", { name: "Receive stock" }).click();
  await expect(owner.getByText("Received. Sellable stock has gone up.")).toBeVisible();
  await expect(owner.getByText("Partly received")).toBeVisible();

  await owner.getByRole("link", { name: firstSku }).click();
  await expect(
    owner.getByText("Sellable on hand").locator("xpath=following-sibling::dd[1]"),
  ).toHaveText(String(onHandBefore + 4));
  await expect(owner.getByRole("cell", { name: /^PO-\d+$/ }).first()).toBeVisible();
});

test("Owner adds a delivery zone with a rate, and a coupon code", async ({ browser }) => {
  test.setTimeout(120_000);
  const owner = await signInOwner(browser);
  const stamp = Date.now().toString(36);
  await owner.goto("/staff/settings/delivery");
  const newZone = owner.getByRole("region", { name: "New zone" });
  await newZone.getByLabel("Code").fill(`hyd-${stamp}`);
  await newZone.getByLabel("Name").fill(`Hyderabad ${stamp}`);
  await newZone.getByLabel("Cities (comma separated)").fill(`Hyderabad ${stamp}`);
  await newZone.getByRole("button", { name: "Add zone" }).click();
  const zone = owner.getByRole("region", { name: `Hyderabad ${stamp}` });
  await expect(zone.getByText("No rates: addresses in this zone can't check out.")).toBeVisible();
  await zone.getByLabel("Fee (Rs)", { exact: true }).fill("300");
  await zone.getByRole("button", { name: "Add rate" }).click();
  await expect(zone.getByRole("cell", { name: "Rs 300" })).toBeVisible();

  await owner.goto("/staff/marketing");
  const form = owner.getByRole("region", { name: "New coupon" });
  const code = `E2E${stamp.toUpperCase()}`.slice(0, 20);
  await form.getByLabel("Code").fill(code);
  await form.getByLabel("Percent (at most 90)").fill("10");
  await form.getByRole("button", { name: "Create coupon" }).click();
  await expect(owner.getByRole("cell", { name: new RegExp(code) })).toBeVisible();
  await expect(owner.getByText("10% off").first()).toBeVisible();
});

test("a customer's contact message is answered by staff and the reply reaches them", async ({
  browser,
  page,
}) => {
  test.setTimeout(150_000);
  const email = `contact-${Date.now()}@aurevon.test`;
  await page.goto("/en/pages/contact");
  await page.getByLabel("Your name").fill("Sana Mir");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("What is it about?").selectOption("delivery");
  await page.getByLabel("Subject", { exact: true }).fill("When will my dupatta arrive?");
  await page
    .getByLabel("Message", { exact: true })
    .fill("I ordered last week and would like an update, please.");
  await page.getByRole("button", { name: "Send message" }).click();
  const sent = page.getByTestId("contact-sent");
  await expect(sent).toContainText(/T-\d{6}/);
  const number = (await sent.textContent())!.match(/T-\d{6}/)![0];

  const owner = await signInOwner(browser);
  await owner.goto("/staff/support/tickets");
  await owner.getByRole("link", { name: number }).click();
  await expect(owner.getByText("I ordered last week")).toBeVisible();
  await owner.getByLabel("Internal note (staff only)").check();
  await owner.getByLabel("Note", { exact: true }).fill("Checked with the courier: Thursday.");
  await owner.getByRole("button", { name: "Add note" }).click();
  await expect(owner.getByText("Note added.")).toBeVisible();
  await owner.getByLabel("Reply to the customer (emailed)").check();
  await owner
    .getByLabel("Reply", { exact: true })
    .fill("It arrives on Thursday. Thank you for waiting.");
  await owner.getByRole("button", { name: "Send reply" }).click();
  await expect(owner.getByText("Reply emailed to the customer.")).toBeVisible();

  let link = "";
  for (let attempt = 0; attempt < 40 && !link; attempt++) {
    const search = await page.request.get(
      `${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:"${email}" subject:"Re:"`)}`,
    );
    const { messages } = (await search.json()) as { messages: { ID: string }[] };
    if (messages.length) {
      const body = (await (
        await page.request.get(`${MAILPIT}/api/v1/message/${messages[0]!.ID}`)
      ).json()) as { Text: string };
      link = body.Text.match(/https?:\/\/\S+\/support\/ticket#token=[\w-]+/)?.[0] ?? "";
    }
    if (!link) await page.waitForTimeout(250);
  }
  expect(link).not.toBe("");
  await page.goto(link.replace(/^https?:\/\/[^/]+/, ""));
  await expect(page.getByText("It arrives on Thursday.")).toBeVisible();
  await expect(page.getByText("Checked with the courier")).toHaveCount(0); // internal notes stay internal
  await page.getByLabel("Your reply").fill("Wonderful, thank you!");
  await page.getByRole("button", { name: "Send reply" }).click();
  await expect(page.getByText("Sent. We'll reply by email.")).toBeVisible();
});

test("Owner reads the sales report and downloads a CSV", async ({ browser }) => {
  test.setTimeout(90_000);
  const owner = await signInOwner(browser);
  await owner.goto("/staff/reports");
  await expect(owner.getByRole("heading", { name: "Gross sales by day" })).toBeVisible();
  await expect(owner.getByText(/net sales \(after refunds\)/)).toBeVisible();
  await owner.getByRole("button", { name: "Show as table" }).click();
  await expect(owner.getByRole("columnheader", { name: "Day" })).toBeVisible();
  const download = owner.waitForEvent("download");
  await owner.getByRole("link", { name: "Daily sales" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^aurevon-daily-sales-.*\.csv$/);
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
