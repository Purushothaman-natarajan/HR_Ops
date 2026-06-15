import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/graph": "http://localhost:8000",
      "/agui": "http://localhost:8000",
      "/trace": "http://localhost:8000",
      "/debug": "http://localhost:8000",
      "/rl": "http://localhost:8000",
      "/policies": "http://localhost:8000",
      "/conversation": "http://localhost:8000",
      "/feedback": "http://localhost:8000",
      "/docs": "http://localhost:8000",
      "/database": "http://localhost:8000",
      "/vector-store": "http://localhost:8000",
      "/openapi.json": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
  },
});
