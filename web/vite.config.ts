/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      "/api": "http://localhost:8002",
      "/ws": {
        target: "ws://localhost:8002",
        ws: true,
        configure: (proxy) => {
          proxy.on("error", (err: NodeJS.ErrnoException) => {
            // Client disconnect / React StrictMode remount — không phải lỗi server
            if (err.code === "ECONNRESET" || err.code === "EPIPE") return;
            console.error("[vite] ws proxy error:", err);
          });
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
  },
});
