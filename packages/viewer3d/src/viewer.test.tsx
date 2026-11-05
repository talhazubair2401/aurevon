import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { THREE_REVISION, decoderPath } from "./decoders";
import { inspectGlb, ModelError } from "./glb";
import { ProductViewer } from "./ProductViewer";
import { is3D, shouldRender, ViewerStore } from "./state";

const fixture = (name: string) => {
  const b = readFileSync(resolve(__dirname, "../../asset-pipeline/fixtures", name));
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
};
const code = (name: string) => {
  try {
    inspectGlb(fixture(name));
    return "ok";
  } catch (e) {
    return (e as ModelError).code;
  }
};

describe("inspectGlb", () => {
  it("accepts good models and reads their variants", () => {
    expect(code("garment.glb")).toBe("ok");
    expect(code("garment-draco.glb")).toBe("ok");
    expect(code("garment-meshopt.glb")).toBe("ok");
    expect(
      inspectGlb(fixture("garment.glb")).extensions?.KHR_materials_variants?.variants.map(
        (v) => v.name,
      ),
    ).toEqual(["ivory", "sage"]);
  });
  it("names the problem with a bad file", () => {
    expect(code("not-a-model.glb")).toBe("badheader");
    expect(code("truncated.glb")).toBe("truncated");
    expect(code("corrupt.glb")).toBe("corrupt");
    expect(code("needs-unknown-extension.glb")).toBe("extension");
  });
});

describe("viewer state", () => {
  it("renders only while 3D is on screen", () => {
    const s = new ViewerStore({ canvasMounted: true });
    expect(shouldRender(s.get())).toBe(true); // warm-up under the poster
    s.set({ phase: "ready" });
    expect(is3D(s.get())).toBe(true);
    s.set({ visible: false });
    expect(shouldRender(s.get())).toBe(false);
    s.set({ visible: true, userChoseImage: true });
    expect(shouldRender(s.get())).toBe(false);
    s.set({ userChoseImage: false, colourHas3D: false });
    expect(is3D(s.get())).toBe(false);
    s.set({ colourHas3D: true, pageVisible: false });
    expect(shouldRender(s.get())).toBe(false);
  });
  it("notifies only on real changes", () => {
    const s = new ViewerStore();
    let n = 0;
    s.subscribe(() => n++);
    s.set({ phase: "loading" });
    s.set({ phase: "ready" });
    expect(n).toBe(1);
  });
});

describe("decoders", () => {
  it("matches the installed three.js release", () => {
    const main = createRequire(join(__dirname, "x.js")).resolve("three");
    const three = JSON.parse(
      readFileSync(join(dirname(dirname(main)), "package.json"), "utf8"),
    ) as { version: string };
    expect(three.version.split(".")[1]).toBe(THREE_REVISION);
    expect(decoderPath()).toBe(`/3d/draco/${THREE_REVISION}/`);
  });
});

describe("ProductViewer", () => {
  it("keeps the image and says so where WebGL is missing", async () => {
    render(
      <ProductViewer src="/m.glb" decoderPath={decoderPath()}>
        <img alt="Kurta in ivory" src="/p.jpg" />
      </ProductViewer>,
    );
    expect(screen.getByAltText("Kurta in ivory")).toBeTruthy();
    expect(await screen.findByText(/3D isn't available on this device/)).toBeTruthy();
    expect(document.querySelector("[data-viewer3d]")?.getAttribute("data-showing")).toBe("image");
  });
  it("shows the colour's photos when it has no 3D version", async () => {
    render(
      <ProductViewer src="/m.glb" decoderPath={decoderPath()} colourHas3D={false}>
        <span>poster</span>
      </ProductViewer>,
    );
    expect(screen.getByText("poster")).toBeTruthy();
  });
});

describe("labels", () => {
  it("English matches the storefront's messages", async () => {
    const { ENGLISH } = await import("./strings");
    const en = JSON.parse(
      readFileSync(resolve(__dirname, "../../i18n/src/messages/en.json"), "utf8"),
    ) as { viewer3d: unknown };
    expect(en.viewer3d).toEqual(ENGLISH);
  });
});
