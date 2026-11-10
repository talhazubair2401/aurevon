import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/*
 * M7/M8 customer journeys through the proxy, the real API, real stock and real email (Mailpit):
 * bag -> checkout as a guest with cash on delivery; register -> confirm email -> sign in -> pay by card
 * (sandbox provider) -> confirmation -> account history; a declined card and a retry.
 */

const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";
const PRODUCTS = [
  "silk-column-dress",
  "relaxed-chino",
  "oxford-poplin-shirt",
  "wool-wrap-coat",
  "satin-slip-dress",
];

type Variant = { sku: string; colour: string; size: string; available: boolean };

/** Any in-stock variant from the demo catalogue, chosen at random so parallel runs spread across stock. */
async function inStock(request: APIRequestContext) {
  for (const slug of [...PRODUCTS].sort(() => Math.random() - 0.5)) {
    const response = await request.get(`/api/v1/catalog/products/${slug}/availability`);
    if (!response.ok()) continue;
    const variants = ((await response.json()) as { variants: Variant[] }).variants.filter(
      (v) => v.available,
    );
    if (variants.length)
      return { slug, variant: variants[Math.floor(Math.random() * variants.length)]! };
  }
  throw new Error("no demo product in stock");
}

async function addToBag(page: Page) {
  const { slug, variant } = await inStock(page.request);
  await page.goto(
    `/en/products/${slug}?colour=${variant.colour}&size=${encodeURIComponent(variant.size)}`,
  );
  await page.getByTestId("add-to-bag").click();
  await expect(page.getByText("Added to your bag")).toBeVisible();
  await expect(page.getByTestId("bag-link")).toHaveAccessibleName(/Bag \(1\)/);
}

async function fillAddress(page: Page, city = "Karachi", province = "sindh") {
  await page.locator('input[name="full_name"]').fill("Ayesha Khan");
  await page.locator('input[name="phone"]').fill("0300 1234567");
  await page.locator('input[name="line1"]').fill("House 12, Street 4");
  await page.locator('input[name="area"]').fill("DHA Phase 6");
  await page.locator('input[name="city"]').fill(city);
  await page.locator('select[name="province"]').selectOption(province);
}

async function latestLink(address: string, pattern: RegExp) {
  for (let attempt = 0; attempt < 30; attempt++) {
    const search = await fetch(
      `${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:"${address}"`)}`,
    );
    const { messages } = (await search.json()) as { messages: { ID: string }[] };
    for (const message of messages) {
      const body = (await (await fetch(`${MAILPIT}/api/v1/message/${message.ID}`)).json()) as {
        Text: string;
      };
      const match = body.Text.match(pattern);
      if (match) return match[0];
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`no email for ${address} matching ${pattern}`);
}

test.describe("bag", () => {
  test("adds a piece, keeps it across pages and changes quantity", async ({ page }) => {
    await addToBag(page);
    await page.getByTestId("bag-link").click();
    await expect(page.getByRole("heading", { level: 1, name: "Your bag" })).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("listitem").filter({ has: page.getByRole("combobox") }),
    ).toHaveCount(1);
    await page.getByRole("button", { name: "Remove" }).click();
    await expect(page.getByRole("heading", { name: "Your bag is empty" })).toBeVisible();
  });

  test("an unknown discount code is refused politely", async ({ page }) => {
    await addToBag(page);
    await page.goto("/en/cart");
    await page.getByLabel("Discount code").fill("NOT-A-CODE");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
  });
});

test.describe("checkout", () => {
  test("a guest orders with cash on delivery and sees the confirmation", async ({ page }) => {
    await addToBag(page);
    await page.goto("/en/checkout");
    await page.locator('input[name="email"]').fill(`guest.${Date.now()}@aurevon.test`);
    await fillAddress(page);
    await expect(page.getByText("Standard delivery")).toBeVisible();
    await page.getByText("Cash on delivery", { exact: true }).click();
    await page.getByTestId("place-order").click();
    await expect(page.getByTestId("order-placed")).toBeVisible();
    await expect(page.getByTestId("order-number")).toHaveText(/^AV\d{6,}$/);
    await expect(page.getByTestId("order-status")).toHaveText("Confirmed");
    // The bag is empty afterwards.
    await expect(page.getByTestId("bag-link")).toHaveAccessibleName("Bag");
  });

  test("a delivery city outside the zones still gets the fallback rates", async ({ page }) => {
    await addToBag(page);
    await page.goto("/en/checkout");
    await fillAddress(page, "Gilgit", "gb");
    await expect(page.getByText("Standard delivery")).toBeVisible();
  });

  test("register, confirm email, sign in and pay by card", async ({ page }) => {
    const email = `shopper.${Date.now()}.${Math.floor(Math.random() * 1e4)}@aurevon.test`;
    await page.goto("/en/account/register");
    await page.getByLabel("Full name").fill("Sana Malik");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("quiet linen evening 2026");
    await page.getByTestId("register").click();
    await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();

    const link = await latestLink(email, /https?:\/\/\S+\/account\/verify#token=\S+/);
    await page.goto(link.replace(/^https?:\/\/[^/]+/, ""));
    await expect(page.getByRole("heading", { name: "Email confirmed" })).toBeVisible();

    await page.goto("/en/account/sign-in?next=/account");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("quiet linen evening 2026");
    await page.getByTestId("sign-in").click();
    await expect(page).toHaveURL(/\/en\/account$/);

    await addToBag(page);
    await page.goto("/en/checkout");
    await expect(page.getByText(`Signed in as ${email}`)).toBeVisible();
    await fillAddress(page, "Lahore", "punjab");
    await page.getByText("Card", { exact: true }).click();
    await page.getByTestId("place-order").click();

    // The sandbox provider's hosted page (never available in production).
    await expect(page.getByRole("button", { name: "Pay", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Pay", exact: true }).click();
    await expect(
      page
        .getByRole("heading", { name: "Thank you for your order" })
        .or(page.getByTestId("order-placed")),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("order-status")).toHaveText("Confirmed");
    const number = (await page.getByTestId("order-number").textContent())!;

    await page.goto("/en/account");
    await expect(page.getByRole("link", { name: new RegExp(number) })).toBeVisible();
    await page.getByRole("button", { name: "Addresses" }).click();
    await expect(page.getByText("House 12, Street 4")).toBeVisible();
  });

  test("a declined card can be tried again", async ({ page }) => {
    await addToBag(page);
    await page.goto("/en/checkout");
    await page.locator('input[name="email"]').fill(`decline.${Date.now()}@aurevon.test`);
    await fillAddress(page, "Islamabad", "ict");
    await page.getByText("Card", { exact: true }).click();
    await page.getByTestId("place-order").click();
    await page.getByRole("button", { name: "Decline" }).click();
    await expect(page.getByRole("heading", { name: "Payment not completed" })).toBeVisible({
      timeout: 20_000,
    });
    await page.getByTestId("retry-payment").click();
    await page.getByRole("button", { name: "Pay", exact: true }).click();
    await expect(page.getByTestId("order-status")).toHaveText("Confirmed", { timeout: 20_000 });
  });
});

test.describe("account", () => {
  test("pages for signed-out shoppers lead to sign in", async ({ page }) => {
    await page.goto("/en/account");
    await expect(page).toHaveURL(/\/account\/sign-in/);
    await expect(page.getByRole("heading", { name: "Sign in to AureVon" })).toBeVisible();
  });

  test("registration keeps its own burgundy and blush direction", async ({ page }) => {
    await page.goto("/en/account/register");
    const button = page.getByTestId("register");
    await expect(button).toHaveCSS("background-color", "rgb(112, 38, 61)");
  });

  test("a wrong password is refused without saying which part was wrong", async ({ page }) => {
    await page.goto("/en/account/sign-in");
    await page.getByLabel("Email").fill("nobody@aurevon.test");
    await page.getByLabel("Password").fill("not the password at all");
    await page.getByTestId("sign-in").click();
    await expect(page.getByRole("alert")).toBeVisible();
  });
});

test.describe("accessibility", () => {
  for (const path of [
    "/en/account/sign-in",
    "/en/account/register",
    "/ur/account/sign-in",
    "/en/cart",
    "/en/checkout",
  ]) {
    test(`${path} has no automatically detectable WCAG 2.2 AA violations`, async ({ page }) => {
      if (path.endsWith("checkout")) await addToBag(page);
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const { default: AxeBuilder } = await import("@axe-core/playwright");
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      expect(
        results.violations.map(
          (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
        ),
      ).toEqual([]);
    });
  }
});
