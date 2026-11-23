import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Two build variants (design D1, D10):
 * - standard (default): no example data, no mock service worker.
 * - example (`--mode example-data`): serves example data in the browser and ships the mock worker.
 * The flag is a build-time constant, so the standard build drops the example code entirely.
 */
export default defineConfig(({ mode }) => {
  const example = mode === "example-data";
  return {
    plugins: [react()],
    define: {
      "import.meta.env.VITE_EXAMPLE_MODE": JSON.stringify(example ? "true" : "false"),
      // The git tag of the design under review, passed by the build (shown only in the example footer).
      "import.meta.env.VITE_DESIGN_VERSION": JSON.stringify(process.env.DESIGN_VERSION ?? ""),
    },
    // Only the example variant has static files (the mock service worker).
    publicDir: example ? "public-example" : false,
    server: { proxy: { "/api": "http://localhost:8000" } },
    test: { environment: "jsdom", globals: true, setupFiles: ["./src/test-setup.ts"] },
  };
});
