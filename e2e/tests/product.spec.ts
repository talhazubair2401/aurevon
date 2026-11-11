import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// M5 slice 1: product page and search, against the demo catalogue (decision 0006 rules).

async function axe(page: Page) {
  // Contrast is judged at rest: let the entrance fades finish (infinite loops are ignored).
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  );
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  return results.violations.map(
    (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
  );
}

test.describe("product page", () => {
  test("shows name, price, colours, sizes in category order and details", async ({ page }) => {
    await page.goto("/en/products/relaxed-chino");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Relaxed Chino");
    await expect(page.getByText(/Rs\s?8,500/).first()).toBeVisible();
    const sizes = page.getByRole("group", { name: "Size" }).getByRole("link");
    await expect(sizes).toHaveText(["30", "32", "34", "36"]);
    await expect(page.getByText("Style no. 0022")).toBeVisible();
    await page.getByText("Size chart (cm)").click();
    await expect(page.getByRole("rowheader", { name: "Waist" })).toBeVisible();
  });

  test("colour and size are chosen with links and the stock status follows", async ({ page }) => {
    await page.goto("/en/products/relaxed-chino");
    await page.getByRole("link", { name: "Olive", exact: true }).click();
    await expect(page).toHaveURL(/colour=olive/);
    await expect(page.getByRole("group", { name: /Colour: Olive/ })).toBeVisible();
    await page.getByRole("link", { name: /^Size 32$|^32, sold out$/ }).click();
    await expect(page).toHaveURL(/colour=olive&size=32/);
    await expect(page.getByRole("status").first()).toHaveText(/In stock|Sold out/);
    await expect(page.getByTestId("add-to-bag")).toBeVisible();
  });

  test("on phones the colour swatches sit directly under the title and price (A-12)", async ({
    page,
    isMobile,
  }) => {
    test.skip(!isMobile, "phone layout");
    await page.goto("/en/products/silk-column-dress");
    const price = await page.locator("h1 + p").boundingBox();
    const colours = await page.getByRole("group", { name: /Colour:/ }).boundingBox();
    const sizes = await page.getByRole("group", { name: "Size" }).boundingBox();
    expect(colours!.y).toBeGreaterThan(price!.y);
    expect(colours!.y).toBeLessThan(sizes!.y);
  });

  test("carries Product structured data with fresh offers", async ({ page }) => {
    await page.goto("/en/products/silk-column-dress");
    const blocks = await page.locator('script[type="application/ld+json"]').allTextContents();
    const product = blocks.map((b) => JSON.parse(b)).find((d) => d["@type"] === "Product");
    expect(product.offers.length).toBeGreaterThan(0);
    expect(product.offers[0].priceCurrency).toBe("PKR");
  });

  test("an unknown product is not found", async ({ page }) => {
    expect((await page.goto("/en/products/nope"))!.status()).toBe(404);
  });

  for (const path of [
    "/en/products/relaxed-chino",
    "/ur/products/chikankari-kurta?colour=ivory&size=M",
  ]) {
    test(`${path} has no automatically detectable WCAG 2.2 AA violations`, async ({ page }) => {
      await page.goto(path);
      expect(await axe(page)).toEqual([]);
    });
  }
});

test.describe("search", () => {
  test("the header search opens search, which finds products by name, colour or in Urdu", async ({
    page,
  }) => {
    await page.goto("/en");
    await page.getByRole("banner").getByRole("link", { name: "Search" }).click();
    await page.getByLabel("Search the store").fill("kurta");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page).toHaveURL(/\/en\/search\?q=kurta/);
    await expect(page.getByRole("status")).toHaveText(/^\d+ results for “kurta”$/);
    await expect(page.getByRole("heading", { name: "Chikankari Kurta" })).toBeVisible();
    await page.goto("/ur/search?q=کرتا");
    expect(await page.locator("main article").count()).toBeGreaterThan(0);
  });

  test("no match says so", async ({ page }) => {
    await page.goto("/en/search?q=zzzz");
    await expect(page.getByRole("status")).toHaveText("Nothing matches “zzzz”.");
  });

  test("/en/search has no automatically detectable WCAG 2.2 AA violations", async ({ page }) => {
    await page.goto("/en/search?q=coat");
    expect(await axe(page)).toEqual([]);
  });
});
