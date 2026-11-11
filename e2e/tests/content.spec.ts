import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// M4 second slice: collection pages, content and policy pages, CMS navigation and SEO, against the demo content.

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

const head = (page: Page, selector: string, attribute: string) =>
  page.locator(selector).first().getAttribute(attribute);

test.describe("collections", () => {
  test("the index lists every published collection and each opens its page", async ({ page }) => {
    await page.goto("/en/collections");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Collections");
    for (const name of ["The Heritage Edit", "Modern Tailoring", "Evening"]) {
      await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
    }
    await page.getByRole("link", { name: /The Heritage Edit/ }).click();
    await expect(page).toHaveURL(/\/en\/collections\/heritage-edit$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("The Heritage Edit");
    await expect(page.getByRole("status")).toHaveText("6 pieces");
    expect(await page.locator("main article").count()).toBe(6);
  });

  test("homepage collection cards open collection pages", async ({ page }) => {
    await page.goto("/en");
    await page.getByRole("link", { name: /Modern Tailoring/ }).click();
    await expect(page).toHaveURL(/\/en\/collections\/modern-tailoring$/);
  });

  test("sorting stays on the collection; filtering hands over to Shop All", async ({ page }) => {
    await page.goto("/en/collections/evening?sort=price_asc");
    await expect(head(page, 'meta[name="robots"]', "content")).resolves.toContain("noindex");
    await expect(head(page, 'link[rel="canonical"]', "href")).resolves.toMatch(
      /\/en\/collections\/evening$/,
    );
    await page.getByRole("link", { name: "Filter this collection" }).click();
    await expect(page).toHaveURL(/\/en\/shop\?collection=evening$/);
  });

  test("an unknown or unpublished collection is not found", async ({ page }) => {
    expect((await page.goto("/en/collections/nope"))!.status()).toBe(404);
  });
});

test.describe("content and policy pages", () => {
  test("pages render from the CMS with breadcrumbs and structured data", async ({ page }) => {
    await page.goto("/en/pages/about");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Our story");
    await expect(page.getByRole("heading", { level: 2, name: "Modern heritage" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText("Home");
    const ld = await page.locator('script[type="application/ld+json"]').first().textContent();
    expect(JSON.parse(ld!)["@type"]).toBe("BreadcrumbList");
  });

  test("policy pages are placeholders until the policy decisions are made", async ({ page }) => {
    await page.goto("/en/pages/returns");
    await expect(page.getByText("Policy", { exact: true })).toBeVisible();
    await expect(page.getByText(/being finalised/)).toBeVisible();
    await expect(page.getByText(/Last updated/)).toBeVisible();
  });

  test("Urdu pages are right-to-left and use the Urdu copy", async ({ page }) => {
    await page.goto("/ur/pages/about");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("ہماری کہانی");
  });

  test("the footer links come from CMS navigation", async ({ page }) => {
    await page.goto("/en");
    const footer = page.getByRole("navigation", { name: "Footer" });
    await footer.getByRole("link", { name: "Returns" }).click();
    await expect(page).toHaveURL(/\/en\/pages\/returns$/);
  });

  for (const path of [
    "/en/collections",
    "/en/collections/heritage-edit",
    "/en/pages/about",
    "/ur/pages/returns",
  ]) {
    test(`${path} has no automatically detectable WCAG 2.2 AA violations`, async ({ page }) => {
      await page.goto(path);
      expect(await axe(page)).toEqual([]);
    });
  }
});

test.describe("SEO", () => {
  test("pages carry canonical and hreflang links for both languages", async ({ page }) => {
    await page.goto("/ur/pages/about");
    await expect(head(page, 'link[rel="canonical"]', "href")).resolves.toMatch(
      /\/ur\/pages\/about$/,
    );
    await expect(head(page, 'link[hreflang="en"]', "href")).resolves.toMatch(/\/en\/pages\/about$/);
    await expect(head(page, 'link[hreflang="x-default"]', "href")).resolves.toMatch(
      /\/en\/pages\/about$/,
    );
  });

  test("the homepage uses its SEO record and Organization data", async ({ page }) => {
    await page.goto("/en");
    await expect(page).toHaveTitle("AureVon · Modern Style. Timeless Confidence.");
    const ld = await page.locator('script[type="application/ld+json"]').first().textContent();
    expect(JSON.stringify(JSON.parse(ld!))).toContain('"Organization"');
  });

  test("filtered Shop All views point at their department and stay out of the index", async ({
    page,
  }) => {
    await page.goto("/en/shop?department=men&size=M");
    await expect(head(page, 'link[rel="canonical"]', "href")).resolves.toMatch(
      /\/en\/shop\?department=men$/,
    );
    await expect(head(page, 'meta[name="robots"]', "content")).resolves.toContain("noindex");
    await page.goto("/en/shop?department=men");
    await expect(page.locator('meta[name="robots"]')).toHaveCount(0);
  });

  test("the sitemap lists every public page in both languages", async ({ request }) => {
    const xml = await (await request.get("/sitemap.xml")).text();
    for (const path of ["/en", "/ur/shop", "/en/collections/evening", "/ur/pages/privacy"]) {
      expect(xml).toContain(`${path}</loc>`);
    }
    expect(xml).toContain('hreflang="ur"');
  });

  test("robots.txt keeps non-production stores out of search and points at the sitemap", async ({
    request,
  }) => {
    const text = await (await request.get("/robots.txt")).text();
    expect(text).toContain("Disallow: /");
    expect(text).toMatch(/Sitemap: .*\/sitemap\.xml/);
  });

  test("the storefront's internal refresh endpoint is never reachable through the proxy", async ({
    request,
  }) => {
    expect((await request.post("/internal/revalidate", { data: { tags: ["cms"] } })).status()).toBe(
      404,
    );
  });
});
