import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy keeps the browser on one origin, so no CORS in dev.
    //
    // Everything the backend owns has to be listed, not just /api. In
    // production FastAPI serves the bundle itself and therefore answers for
    // all of these; in dev Vite owns the root and falls back to index.html for
    // any path it doesn't recognise. So an unlisted backend route doesn't 404
    // in development — it silently returns the React app with a 200, which is
    // how the About panel's link to /privacy came to show the map instead of
    // the privacy notice.
    proxy: Object.fromEntries(
      ["/api", "/privacy", "/healthz", "/docs", "/openapi.json"].map((path) => [
        path,
        { target: "http://127.0.0.1:8000", changeOrigin: true },
      ]),
    ),
  },
});
