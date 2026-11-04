import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { colorVariables, colors } from "./index";

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

  it.each(Object.entries(colorVariables))(
    "declares %s in tokens.css with the same value",
    (key, variable) => {
      const value = colors[key as keyof typeof colors].toLowerCase();
      expect(css).toContain(`${variable}: ${value};`);
    },
  );
});
