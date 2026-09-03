import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev server is reached over a private network (LAN / Tailscale MagicDNS),
    // so accept any Host header. Override with VITE_ALLOWED_HOSTS (comma list)
    // to lock it down.
    allowedHosts: process.env.VITE_ALLOWED_HOSTS
      ? process.env.VITE_ALLOWED_HOSTS.split(",").map((h) => h.trim())
      : true,
    proxy: {
      // Forward /api/* to the local FastAPI backend during development.
      // The backend itself exposes routes at the root (e.g. /ideas, not
      // /api/ideas) — strip the /api prefix on the way through.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
