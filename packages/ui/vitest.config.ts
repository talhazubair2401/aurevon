import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { environment: "jsdom", css: { modules: { classNameStrategy: "non-scoped" } } },
});
