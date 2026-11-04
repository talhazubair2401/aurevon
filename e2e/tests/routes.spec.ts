import { expect, test } from "@playwright/test";

// Routing and staff restrictions (MTS v2.1 A-27, §2).
test.describe("routes behind the proxy", () => {
  test("storefront is served at /", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("AUREVON");
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
  });

  test("staff dashboard is served at /staff/ and is never cached or indexed", async ({ page }) => {
    const response = await page.goto("/staff/");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("AureVon Staff");
    const headers = response!.headers();
    expect(headers["cache-control"]).toContain("no-store");
    expect(headers["x-robots-tag"]).toContain("noindex");
    expect(headers["referrer-policy"]).toBe("same-origin");
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  });

  test("API is served at /api/v1/, uncached, with a request ID", async ({ request }) => {
    const response = await request.get("/api/v1/");
    expect(response.status()).toBe(200);
    expect(await response.json()).toEqual({ name: "AureVon API", version: "v1" });
    expect(response.headers()["cache-control"]).toContain("no-store");
    expect(response.headers()["x-request-id"]).toMatch(/^[A-Za-z0-9._-]{8,64}$/);
  });

  test("unknown API paths return problem details", async ({ request }) => {
    const response = await request.get("/api/v1/does-not-exist");
    expect(response.status()).toBe(404);
    expect(response.headers()["content-type"]).toContain("application/problem+json");
    expect((await response.json()).title).toBe("Not found");
  });

  for (const path of ["/health/live", "/health/ready", "/admin/"]) {
    test(`${path} is not publicly routed to the API`, async ({ request }) => {
      const response = await request.get(path);
      expect(response.status()).toBe(404);
      expect(response.headers()["content-type"] ?? "").not.toContain("json");
    });
  }
});
