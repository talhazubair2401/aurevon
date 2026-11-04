import { describe, expect, it } from "vitest";
import { buildPolicy, generateNonce } from "./index";

function directives(policy: string): Map<string, string[]> {
  return new Map(
    policy.split(";").map((part) => {
      const [name, ...values] = part.trim().split(/\s+/);
      return [name!, values];
    }),
  );
}

describe("nonce", () => {
  it("is 128 random bits in base64 and different every time", () => {
    const seen = new Set(Array.from({ length: 1000 }, generateNonce));
    expect(seen.size).toBe(1000);
    for (const n of seen) expect(n).toMatch(/^[A-Za-z0-9+/]{22}==$/);
  });

  it("is rejected if malformed, so nothing can be smuggled into the header", () => {
    expect(() => buildPolicy({ app: "storefront", nonce: "abc'; script-src *" })).toThrow();
  });
});

describe.each(["storefront", "staff"] as const)("%s production policy", (app) => {
  const nonce = generateNonce();
  const policy = buildPolicy({ app, nonce });
  const d = directives(policy);

  it("allows scripts only by nonce, with strict-dynamic", () => {
    expect(d.get("script-src")).toEqual(["'self'", `'nonce-${nonce}'`, "'strict-dynamic'"]);
  });

  it("never allows unsafe-inline or unsafe-eval", () => {
    expect(policy).not.toContain("'unsafe-inline'");
    expect(policy).not.toContain("'unsafe-eval'");
  });

  it("forbids framing, plugins and base-tag hijacking, and reports violations", () => {
    expect(d.get("frame-ancestors")).toEqual(["'none'"]);
    expect(d.get("object-src")).toEqual(["'none'"]);
    expect(d.get("base-uri")).toEqual(["'none'"]);
    expect(d.get("report-uri")).toEqual(["/api/v1/csp-reports"]);
  });

  it("has no third-party origins", () => {
    expect(policy).not.toMatch(/https?:/);
  });

  it("has no WebAssembly or blob workers until the 3D viewer needs them (M6)", () => {
    expect(policy).not.toContain("wasm-unsafe-eval");
    expect(d.has("worker-src")).toBe(false);
  });
});

it("the 3D option adds exactly WebAssembly and blob workers to the storefront", () => {
  const d = directives(
    buildPolicy({ app: "storefront", nonce: generateNonce(), webAssembly: true }),
  );
  expect(d.get("script-src")).toContain("'wasm-unsafe-eval'");
  expect(d.get("worker-src")).toEqual(["'self'", "blob:"]);
});

it("only development builds get unsafe-eval", () => {
  const policy = buildPolicy({ app: "storefront", nonce: generateNonce(), development: true });
  expect(policy).toContain("'unsafe-eval'");
  expect(policy).toContain("ws:");
});
