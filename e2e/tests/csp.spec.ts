import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

// V-05, first run (MTS v2.1 §12). The baseline policy is sent report-only; this test records every violation
// the production builds trigger, as evidence for D-08. It fails only if the policy header is missing.
interface Violation {
  directive: string;
  blockedURI: string;
  sample: string;
}

async function collect(
  page: Page,
  path: string,
): Promise<{ header: string | null; violations: Violation[] }> {
  await page.addInitScript(() => {
    const w = window as unknown as { __csp: unknown[] };
    w.__csp = [];
    document.addEventListener("securitypolicyviolation", (e) => {
      w.__csp.push({ directive: e.effectiveDirective, blockedURI: e.blockedURI, sample: e.sample });
    });
  });
  const response = await page.goto(path, { waitUntil: "networkidle" });
  const header = response?.headers()["content-security-policy-report-only"] ?? null;
  const violations =
    (await page.evaluate(() => (window as unknown as { __csp: Violation[] }).__csp)) ?? [];
  return { header, violations };
}

test("CSP baseline is reported against the production builds", async ({ page }, testInfo) => {
  const results: Record<string, { header: string | null; violations: Violation[] }> = {};
  for (const path of ["/en", "/ur", "/staff/"]) {
    results[path] = await collect(page, path);
    expect(results[path].header, `report-only CSP header on ${path}`).toContain(
      "default-src 'self'",
    );
  }
  mkdirSync("results", { recursive: true });
  const file = `results/csp-v05-${testInfo.project.name}.json`;
  writeFileSync(file, JSON.stringify({ date: new Date().toISOString(), results }, null, 2));
  for (const [path, r] of Object.entries(results)) {
    testInfo.annotations.push({
      type: "csp-violations",
      description: `${path}: ${r.violations.length}`,
    });
  }
});
