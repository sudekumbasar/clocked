/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  server: {
    // During development the API runs separately on port 8000.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "node",
  },
});
