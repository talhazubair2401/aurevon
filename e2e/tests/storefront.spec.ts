import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// M4 first slice: homepage and Shop All against the running API with the demo catalogue (seed_demo_catalog).

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

const prices = (page: Page) =>
  page
    .locator("main article")
    .evaluateAll((cards) =>
      cards.map((c) =>
        Number((c.textContent ?? "").match(/Rs\s?([\d,]+)/)?.[1]?.replace(/,/g, "")),
      ),
    );

test.describe("homepage", () => {
  test("shows hero, collections, featured, new arrivals and brand story from the CMS", async ({
    page,
  }) => {
    await page.goto("/en");
    const main = page.getByRole("main");
    await expect(main.getByRole("heading", { level: 1 })).toContainText("Modern Style");
    for (const heading of [
      "The Collections",
      "Featured",
      "New Arrivals",
      "Heritage, reconsidered",
    ]) {
      await expect(main.getByRole("heading", { name: heading })).toBeVisible();
    }
    expect(await main.locator("article").count()).toBeGreaterThanOrEqual(8);
    await expect(main.getByText(/Rs\s?[\d,]+/).first()).toBeVisible();
  });

  test("hero calls to action open Shop All for each department", async ({ page }) => {
    await page.goto("/en");
    await page.getByRole("link", { name: "Shop women" }).click();
    await expect(page).toHaveURL(/\/en\/shop\?department=women/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Shop All");
  });

  test("the moving hero can be paused (WCAG 2.2.2)", async ({ page }) => {
    await page.goto("/en");
    const pause = page.getByRole("button", { name: "Pause motion" });
    await expect(pause).toHaveAttribute("aria-pressed", "false");
    await pause.click();
    await expect(page.getByRole("button", { name: "Play motion" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.locator("html")).toHaveAttribute("data-motion-paused", "");
  });

  for (const locale of ["en", "ur"]) {
    test(`/${locale} has no automatically detectable WCAG 2.2 AA violations`, async ({ page }) => {
      await page.goto(`/${locale}`);
      expect(await axe(page)).toEqual([]);
    });
  }
});

test.describe("Shop All", () => {
  test("lists the catalogue in a four-column grid with balanced departments", async ({
    page,
    isMobile,
  }) => {
    await page.goto("/en/shop");
    await expect(page.getByRole("heading", { name: "BEYOND THE ORDINARY" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Join the AureVon list" })).toBeVisible();
    await expect(page.getByRole("status").first()).toContainText(/\d+ pieces/);
    const firstRow = await page
      .locator("main article")
      .evaluateAll((cards) => cards.map((c) => Math.round(c.getBoundingClientRect().top)));
    const columns = firstRow.filter((top) => top === firstRow[0]).length;
    expect(columns).toBe(isMobile ? 2 : 4);

    const women = await page.request.get("/api/v1/catalog/products?department=women");
    const men = await page.request.get("/api/v1/catalog/products?department=men");
    const count = async (r: typeof women) =>
      ((await r.json()) as { results: unknown[] }).results.length;
    // Balanced presentation; staff tests running in parallel may publish one extra product.
    expect(Math.abs((await count(women)) - (await count(men)))).toBeLessThanOrEqual(1);
  });

  test("filters and sorting live in the URL and work without JavaScript", async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await page.goto("/en/shop?department=men&sort=price_asc");
    const list = await prices(page);
    expect(list.length).toBeGreaterThan(0);
    expect(list).toEqual([...list].sort((a, b) => a - b));
    await expect(page.locator("main article").first()).toBeVisible();
    await context.close();
  });

  test("department tabs, sort and filters update the results", async ({ page, isMobile }) => {
    test.skip(isMobile, "the phone filter dialog is covered separately");
    await page.goto("/en/shop");
    const total = await page.locator("main article").count();

    await page
      .getByRole("navigation", { name: "Department" })
      .getByRole("link", { name: "Women" })
      .click();
    await expect(page).toHaveURL(/department=women/);
    expect(await page.locator("main article").count()).toBeLessThan(total);

    await page.getByLabel("Sort by").selectOption("price_desc");
    await expect(page).toHaveURL(/sort=price_desc/);
    const list = await prices(page);
    expect(list).toEqual([...list].sort((a, b) => b - a));

    await page.getByRole("complementary").getByText("Black", { exact: true }).click();
    await expect(page).toHaveURL(/colour=/);
    // Clear all removes the filters but keeps the chosen department and sort order.
    await page.getByRole("link", { name: "Clear all" }).click();
    await expect(page).not.toHaveURL(/colour=/);
    await expect(page).toHaveURL(/department=women/);
  });

  test("an impossible filter shows the empty state", async ({ page }) => {
    await page.goto("/en/shop?price_max=1");
    await expect(
      page.getByRole("heading", { name: "Nothing matches these filters" }),
    ).toBeVisible();
  });

  test("phone filters open in a dialog", async ({ page, isMobile }) => {
    test.skip(!isMobile, "phone only");
    await page.goto("/en/shop");
    await page.getByRole("button", { name: "Filters" }).click();
    const dialog = page.getByRole("dialog", { name: "Filters" });
    await expect(dialog).toBeVisible();
    expect(await axe(page)).toEqual([]);
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  });

  test("the newsletter requires consent before it sends anything", async ({ page }) => {
    await page.goto("/en/shop");
    const form = page.getByRole("region", { name: "Join the AureVon list" });
    await form.getByLabel("Email address").fill("reader@example.com");
    await form.getByRole("button", { name: "Subscribe" }).click();
    await expect(form.getByText("Tick the box to agree to receive emails.")).toBeVisible();
    await form.getByRole("checkbox").check();
    await form.getByRole("button", { name: "Subscribe" }).click();
    await expect(form.getByText(/Check your inbox/)).toBeVisible();
  });

  for (const locale of ["en", "ur"]) {
    test(`/${locale}/shop has no automatically detectable WCAG 2.2 AA violations`, async ({
      page,
    }) => {
      await page.goto(`/${locale}/shop`);
      expect(await axe(page)).toEqual([]);
    });
  }
});
