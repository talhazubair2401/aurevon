import { expect, test } from "@playwright/test";

// No control on the storefront may lead to a broken page. Routes from later milestones (product pages, search,
// account, bag) aren't linked until they exist (apps/storefront/lib/features.ts).

const PAGES = [
  "/en/products/relaxed-chino",
  "/ur/search?q=kurta",
  "/en",
  "/ur",
  "/en/shop",
  "/ur/shop?department=men",
  "/en/collections",
  "/ur/collections/evening",
  "/en/pages/about",
];

test("every internal link on the main pages opens a working page", async ({ page, request }) => {
  const hrefs = new Set<string>();
  for (const path of PAGES) {
    await page.goto(path);
    for (const href of await page
      .locator("a[href^='/']")
      .evaluateAll((as) => as.map((a) => a.getAttribute("href")!)))
      if (!href.startsWith("/staff")) hrefs.add(href.split("#")[0]!);
  }
  expect(hrefs.size).toBeGreaterThan(20);
  const broken: string[] = [];
  for (const href of hrefs) {
    const status = (await request.get(href, { maxRedirects: 5 })).status();
    if (status >= 400) broken.push(`${href} → ${status}`);
  }
  expect(broken).toEqual([]);
});

test("unbuilt header utilities are shown but don't link anywhere", async ({ page }) => {
  await page.goto("/en");
  const header = page.getByRole("banner");
  await expect(header.getByRole("link", { name: "Search" })).toHaveAttribute("href", "/en/search");
  for (const name of ["Account", "Bag"]) {
    await expect(header.getByRole("img", { name: `${name}: coming soon` })).toBeVisible();
    await expect(header.getByRole("link", { name })).toHaveCount(0);
  }
});

test("product cards open their product pages (M5)", async ({ page }) => {
  await page.goto("/en/shop");
  await page.locator("main article").first().getByRole("link").click();
  await expect(page).toHaveURL(/\/en\/products\/[a-z0-9-]+$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});
