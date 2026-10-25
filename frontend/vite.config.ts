import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
  },
  build: {
    target: "es2020",
    rollupOptions: {
      output: {
        // A few mid-sized chunks instead of a dozen tiny ones per screen: on a 150 ms RTT phone,
        // round trips cost more than bytes. The QR scanner stays its own lazy chunk.
        manualChunks(id) {
          if (/node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(id)) return "react";
          if (id.includes("@tanstack")) return "query";
          if (/node_modules[\\/](motion|framer-motion|motion-dom|motion-utils|lucide-react)[\\/]/.test(id)) return "ui";
          if (/[\\/]src[\\/](lib|components[\\/]ui)[\\/]/.test(id)) return "core";
        },
      },
    },
  },
});
