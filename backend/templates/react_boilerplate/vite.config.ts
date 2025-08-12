import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    port: 3002,
    host: true,
    cors: true,
    headers: {
      'X-Frame-Options': 'ALLOWALL',
    }
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./client"),
    },
  },
  plugins: [react()],
});

