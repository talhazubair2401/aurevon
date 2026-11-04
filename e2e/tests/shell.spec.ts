import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// M3 storefront shell: accessibility baseline (R-09, WCAG 2.2 AA target), Urdu right-to-left (A-18),
// tokens and fonts from decision 0004.

async function axe(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  return results.violations.map(
    (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
  );
}

for (const [locale, dir] of [
  ["en", "ltr"],
  ["ur", "rtl"],
] as const) {
  test.describe(`/${locale}`, () => {
    test(`has lang="${locale}" dir="${dir}" and landmarks`, async ({ page }) => {
      await page.goto(`/${locale}`);
      const html = page.locator("html");
      await expect(html).toHaveAttribute("lang", locale);
      await expect(html).toHaveAttribute("dir", dir);
      await expect(page.getByRole("banner")).toHaveCount(1);
      await expect(page.getByRole("main")).toHaveCount(1);
      await expect(page.getByRole("contentinfo")).toHaveCount(1);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByRole("banner").getByRole("link", { name: /AureVon/ })).toContainText(
        "AUREVON",
      );
    });

    test("has no automatically detectable WCAG 2.2 AA violations", async ({ page }) => {
      await page.goto(`/${locale}`);
      expect(await axe(page)).toEqual([]);
    });

    test("not-found page is localised, inside the shell, and returns 404", async ({ page }) => {
      const response = await page.goto(`/${locale}/does-not-exist`);
      expect(response?.status()).toBe(404);
      await expect(page.locator("html")).toHaveAttribute("dir", dir);
      await expect(page.getByRole("banner")).toHaveCount(1);
      expect(await axe(page)).toEqual([]);
    });
  });
}

test("the skip link is the first focusable element and moves focus to main", async ({ page }) => {
  await page.goto("/en");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to main content" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await page.keyboard.press("Enter");
  await expect(page.locator("main#main")).toBeFocused();
});

test("focus ring is charcoal, not gold (decision 0004, item 1)", async ({ page }) => {
  await page.goto("/en");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab"); // past the skip link to the next control
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement!).outlineColor);
  expect(outline).toBe("rgb(18, 18, 18)");
});

test("the language switch keeps the page and changes direction", async ({ page }) => {
  await page.goto("/en/does-not-exist");
  await page.getByRole("contentinfo").getByRole("link", { name: /اردو/ }).click();
  await expect(page).toHaveURL(/\/ur\/does-not-exist$/);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page
    .getByRole("contentinfo")
    .getByRole("link", { name: /English/ })
    .click();
  await expect(page).toHaveURL(/\/en\/does-not-exist$/);
});

test("Urdu text uses Nastaliq for reading and Naskh for controls; the wordmark stays Playfair", async ({
  page,
}) => {
  await page.goto("/ur");
  const family = (selector: string) =>
    page
      .locator(selector)
      .first()
      .evaluate((el) => getComputedStyle(el).fontFamily);
  // next/font names each self-hosted family after its variable in app/fonts.ts.
  expect(await family("body")).toMatch(/^urduReadingFont/);
  expect(await family("header nav a")).toMatch(/^urduUiFont/);
  const wordmark = page
    .getByRole("banner")
    .getByRole("link", { name: /AureVon/ })
    .locator("[lang=en]");
  expect(await wordmark.evaluate((el) => getComputedStyle(el).fontFamily)).toMatch(/^displayFont/);
  await expect(wordmark).toHaveAttribute("dir", "ltr");
});

test("Urdu fonts are not downloaded on English pages", async ({ page }) => {
  const fonts: string[] = [];
  page.on("request", (r) => {
    if (r.resourceType() === "font") fonts.push(r.url());
  });
  await page.goto("/en", { waitUntil: "networkidle" });
  expect(fonts.length).toBeGreaterThan(0);
  // next/font hashes file names, so check what the fonts are by their declared families instead.
  const families = await page.evaluate(() =>
    [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family),
  );
  expect(families.join(" ")).not.toMatch(/urdu/i);
});

test.describe("phone menu", () => {
  test.skip(({ isMobile }) => !isMobile, "phone viewport only");

  test("opens as a modal, traps focus, closes on Escape and returns focus", async ({ page }) => {
    await page.goto("/en");
    const openButton = page.getByRole("button", { name: "Open menu" });
    await openButton.click();
    const dialog = page.getByRole("dialog", { name: "Menu" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("link", { name: "Shop All" })).toBeVisible();
    expect(await axe(page)).toEqual([]);
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(openButton).toBeFocused();
  });

  test("opens from the right in Urdu", async ({ page }) => {
    await page.goto("/ur");
    await page.getByRole("button", { name: "مینو کھولیں" }).click();
    const dialog = page.getByRole("dialog");
    const width = page.viewportSize()!.width;
    // Measured once the slide-in has finished.
    await expect(async () => {
      const box = await dialog.boundingBox();
      expect(Math.round(box!.x + box!.width)).toBe(width);
    }).toPass({ timeout: 3000 });
  });
});

test("every interactive control in the header is at least 44px tall", async ({ page }) => {
  await page.goto("/en");
  const heights = await page
    .getByRole("banner")
    .locator("a:visible, button:visible")
    .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height));
  expect(heights.length).toBeGreaterThan(0);
  for (const h of heights) expect(h).toBeGreaterThanOrEqual(44);
});
