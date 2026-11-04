import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  colorVariables,
  colors,
  functionalColorVariables,
  functionalColors,
  registrationColorVariables,
  registrationColors,
} from "./index";
import { contrastRatio } from "./contrast";

const css = readFileSync(new URL("./tokens.css", import.meta.url), "utf8");

describe("design tokens", () => {
  it("match the approved brand palette (A-03)", () => {
    expect(colors).toEqual({
      offWhite: "#F9F8F6",
      charcoal: "#121212",
      stone: "#E5E0DB",
      deepBrown: "#3B2F2F",
      champagneGold: "#C2A676",
    });
  });

  it("match the approved functional colours (decision 0004, item 1)", () => {
    expect(functionalColors).toEqual({
      white: "#FFFFFF",
      mutedText: "#6B6461",
      fieldBorder: "#8C7F78",
      error: "#9A2B2B",
      success: "#2E5E3A",
    });
  });

  it("match the approved registration palette (decision 0004, item 4)", () => {
    expect(registrationColors).toEqual({
      burgundy: "#70263D",
      blush: "#E8C5CC",
      ivory: "#FAF7F4",
      ink: "#292629",
    });
  });

  const groups = [
    [colors, colorVariables],
    [functionalColors, functionalColorVariables],
    [registrationColors, registrationColorVariables],
  ] as const;
  for (const [values, variables] of groups) {
    it.each(Object.entries(variables))(
      "declares %s in tokens.css with the same value",
      (key, v) => {
        const value = (values as Record<string, string>)[key]!.toLowerCase();
        expect(css).toContain(`${v}: ${value};`);
      },
    );
  }

  it("uses charcoal for the focus ring, never gold (decision 0004, item 1)", () => {
    expect(css).toContain("--av-focus: var(--av-color-charcoal);");
    expect(css).not.toMatch(/--av-focus:\s*var\(--av-color-champagne-gold\)/);
  });
});

// WCAG 2.2: 4.5:1 for normal text (1.4.3), 3:1 for UI component boundaries and focus indicators (1.4.11).
describe("contrast of approved pairings", () => {
  const text: Array<[string, string, string]> = [
    ["charcoal on off-white", colors.charcoal, colors.offWhite],
    ["charcoal on white", colors.charcoal, functionalColors.white],
    ["deep brown on off-white", colors.deepBrown, colors.offWhite],
    ["muted text on off-white", functionalColors.mutedText, colors.offWhite],
    ["muted text on white", functionalColors.mutedText, functionalColors.white],
    ["error on off-white", functionalColors.error, colors.offWhite],
    ["error on white", functionalColors.error, functionalColors.white],
    ["success on off-white", functionalColors.success, colors.offWhite],
    ["success on white", functionalColors.success, functionalColors.white],
    ["off-white on charcoal (primary button)", colors.offWhite, colors.charcoal],
    ["off-white on deep brown", colors.offWhite, colors.deepBrown],
    ["gold on charcoal (accent on dark)", colors.champagneGold, colors.charcoal],
    ["registration ink on ivory", registrationColors.ink, registrationColors.ivory],
    ["registration burgundy on ivory", registrationColors.burgundy, registrationColors.ivory],
    ["registration ivory on burgundy", registrationColors.ivory, registrationColors.burgundy],
    ["registration burgundy on blush", registrationColors.burgundy, registrationColors.blush],
  ];
  it.each(text)("%s meets 4.5:1", (_name, fg, bg) => {
    expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });

  const nonText: Array<[string, string, string]> = [
    ["field border on white", functionalColors.fieldBorder, functionalColors.white],
    ["field border on off-white", functionalColors.fieldBorder, colors.offWhite],
    ["charcoal focus ring on off-white", colors.charcoal, colors.offWhite],
    ["off-white focus ring on charcoal", colors.offWhite, colors.charcoal],
  ];
  it.each(nonText)("%s meets 3:1", (_name, fg, bg) => {
    expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(3);
  });

  it("confirms gold is below text contrast on light surfaces, so it is never used there", () => {
    expect(contrastRatio(colors.champagneGold, colors.offWhite)).toBeLessThan(3);
  });
});
