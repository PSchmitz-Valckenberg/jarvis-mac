import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served by the FastAPI backend at /dashboard (see jarvis/server.py's
// StaticFiles mount), so every asset URL needs that prefix baked in.
export default defineConfig({
  base: "/dashboard/",
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/ws": { target: "ws://127.0.0.1:8765", ws: true },
    },
  },
  build: {
    outDir: "dist",
  },
});
