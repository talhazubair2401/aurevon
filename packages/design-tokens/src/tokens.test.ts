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
  it("match the approved Midnight Indigo & Amber palette (decision 0008)", () => {
    expect(colors).toEqual({
      midnightIndigo: "#111322",
      deepIndigo: "#191D35",
      amber: "#D99A32",
      softAmber: "#E8B968",
      warmIvory: "#F5F3EE",
      mutedSlate: "#85879A",
    });
  });

  it("match the approved functional colours (decisions 0004 and 0008)", () => {
    expect(functionalColors).toEqual({
      white: "#FFFFFF",
      mutedText: "#5C5F74",
      fieldBorder: "#7A7D91",
      ivoryShade: "#E4E1D9",
      error: "#9A2B2B",
      success: "#2E5E3A",
      errorOnDark: "#E8A3A3",
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

  it("uses indigo for the focus ring on light surfaces, never amber (decisions 0004 and 0008)", () => {
    expect(css).toContain("--av-focus: var(--av-color-midnight-indigo);");
    expect(css).not.toMatch(/--av-focus:\s*var\(--av-color-(amber|soft-amber)\)/);
  });

  it("keeps no trace of the retired palette", () => {
    expect(css).not.toMatch(/off-white|charcoal|champagne|deep-brown|--av-color-stone/);
  });
});

// WCAG 2.2: 4.5:1 for normal text (1.4.3), 3:1 for UI component boundaries and focus indicators (1.4.11).
describe("contrast of approved pairings", () => {
  const text: Array<[string, string, string]> = [
    ["midnight indigo on warm ivory", colors.midnightIndigo, colors.warmIvory],
    ["midnight indigo on white", colors.midnightIndigo, functionalColors.white],
    ["deep indigo on warm ivory", colors.deepIndigo, colors.warmIvory],
    ["muted text on warm ivory", functionalColors.mutedText, colors.warmIvory],
    ["muted text on white", functionalColors.mutedText, functionalColors.white],
    ["muted text on ivory shade", functionalColors.mutedText, functionalColors.ivoryShade],
    ["error on warm ivory", functionalColors.error, colors.warmIvory],
    ["error on white", functionalColors.error, functionalColors.white],
    ["success on warm ivory", functionalColors.success, colors.warmIvory],
    ["success on white", functionalColors.success, functionalColors.white],
    ["warm ivory on midnight indigo", colors.warmIvory, colors.midnightIndigo],
    ["warm ivory on deep indigo", colors.warmIvory, colors.deepIndigo],
    ["muted slate on midnight indigo", colors.mutedSlate, colors.midnightIndigo],
    ["muted slate on deep indigo", colors.mutedSlate, colors.deepIndigo],
    ["amber on midnight indigo", colors.amber, colors.midnightIndigo],
    ["amber on deep indigo", colors.amber, colors.deepIndigo],
    ["soft amber on midnight indigo", colors.softAmber, colors.midnightIndigo],
    ["midnight indigo on amber (amber button)", colors.midnightIndigo, colors.amber],
    ["error on dark surfaces", functionalColors.errorOnDark, colors.deepIndigo],
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
    ["field border on warm ivory", functionalColors.fieldBorder, colors.warmIvory],
    ["indigo focus ring on warm ivory", colors.midnightIndigo, colors.warmIvory],
    ["ivory focus ring on midnight indigo", colors.warmIvory, colors.midnightIndigo],
    ["slate field border on deep indigo", colors.mutedSlate, colors.deepIndigo],
  ];
  it.each(nonText)("%s meets 3:1", (_name, fg, bg) => {
    expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(3);
  });

  it("confirms amber and muted slate fall below text contrast on light surfaces, so they are never used there", () => {
    expect(contrastRatio(colors.amber, colors.warmIvory)).toBeLessThan(3);
    expect(contrastRatio(colors.mutedSlate, colors.warmIvory)).toBeLessThan(4.5);
  });
});
