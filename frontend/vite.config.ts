import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
const backend = process.env.LIFEOS_API_URL || "http://127.0.0.1:8010";
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": backend, "/health": backend } },
  build: { sourcemap: false },
});
