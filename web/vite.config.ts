import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI app serves the built UI itself: `/ui` returns frontend/index.html
// and `/static/*` is mounted on that same directory. So the build lands in
// ../frontend and every asset URL is written as /static/… — that keeps the
// backend untouched, and `python -m rip.cli serve` still serves the whole app.
export default defineConfig({
  plugins: [react()],
  base: "/static/",
  build: {
    outDir: "../frontend",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    // Explicitly IPv4. Vite's default host is "localhost", which Node resolves
    // to ::1 on Windows — so the server binds IPv6 only and the 127.0.0.1 URL
    // everyone actually types is refused.
    host: "127.0.0.1",
    port: 5173,
    // In dev the page is served by Vite, so API calls need somewhere to go.
    proxy: {
      "/v1": {
        target: process.env.SEEKR_API || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
