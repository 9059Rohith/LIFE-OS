import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
const backend = process.env.LIFEOS_API_URL || "http://127.0.0.1:8010";
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": backend, "/health": backend } },
  build: { sourcemap: false, rollupOptions: {
    input: { main: resolve(__dirname, "index.html"), desktop: resolve(__dirname, "desktop.html") },
  } },
});
