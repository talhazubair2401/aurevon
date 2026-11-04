import { describe, expect, it } from "vitest";
import { directionOf, formatDate, formatMoney, isLocale, locales, messages } from "./index";

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "object" && v !== null ? keys(v as object, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

function placeholders(obj: object): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  const walk = (o: object, p: string) => {
    for (const [k, v] of Object.entries(o)) {
      if (typeof v === "string") out[`${p}${k}`] = (v.match(/\{\w+\}/g) ?? []).sort();
      else walk(v as object, `${p}${k}.`);
    }
  };
  walk(obj, "");
  return out;
}

describe("locales", () => {
  it("are English (LTR) and Urdu (RTL) at launch (A-18)", () => {
    expect(locales).toEqual(["en", "ur"]);
    expect(directionOf("en")).toBe("ltr");
    expect(directionOf("ur")).toBe("rtl");
    expect(isLocale("ur")).toBe(true);
    expect(isLocale("fr")).toBe(false);
  });

  it("every locale has exactly the English message keys", () => {
    const expected = keys(messages.en).sort();
    for (const locale of locales) expect(keys(messages[locale]).sort()).toEqual(expected);
  });

  it("translations keep the same placeholders", () => {
    const en = placeholders(messages.en);
    expect(placeholders(messages.ur)).toEqual(en);
  });

  it("no message is empty", () => {
    const walk = (o: object, p: string): void => {
      for (const [k, v] of Object.entries(o)) {
        if (typeof v === "string") expect(v.trim().length, `${p}${k}`).toBeGreaterThan(0);
        else walk(v as object, `${p}${k}.`);
      }
    };
    for (const locale of locales) walk(messages[locale], `${locale}.`);
  });
});

describe("formatting goes through Intl", () => {
  it("formats PKR from the API's decimal string", () => {
    const en = formatMoney("48500.00", "en");
    expect(en).toContain("48,500");
    expect(en).toMatch(/Rs|PKR/);
    // Urdu keeps Latin digits for prices.
    expect(formatMoney("48500.00", "ur")).toMatch(/48,?500|48٬500/);
  });

  it("rejects amounts that are not numbers", () => {
    expect(() => formatMoney("abc", "en")).toThrow();
  });

  it("formats dates in Asia/Karachi", () => {
    // 2026-11-04T20:00Z is 5 November 01:00 in Karachi.
    expect(formatDate("2026-11-04T20:00:00Z", "en", { day: "numeric" })).toBe("5");
  });
});
