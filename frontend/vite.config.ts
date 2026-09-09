import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite reads .env files automatically; values must be prefixed with VITE_.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
