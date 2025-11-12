import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve, dirname } from "path";
import { copyFileSync, mkdirSync } from "fs";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export default defineConfig({
  plugins: [
    react(),
    {
      name: "copy-manifest",
      closeBundle() {
        // Copy manifest.json to dist
        const manifestSrc = resolve(__dirname, "src/manifest.json");
        const manifestDest = resolve(__dirname, "../dist/manifest.json");
        copyFileSync(manifestSrc, manifestDest);
        
        // Create icons directory if it doesn't exist
        const iconsDir = resolve(__dirname, "../dist/icons");
        try {
          mkdirSync(iconsDir, { recursive: true });
        } catch (e) {
          // Directory might already exist
        }
      },
    },
  ],
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "src/popup/popup.html"),
        background: resolve(__dirname, "src/background/background.ts"),
        content: resolve(__dirname, "src/content/contentScript.tsx"),
      },
      output: {
        entryFileNames: (chunkInfo) => {
          const facadeModuleId = chunkInfo.facadeModuleId
            ? chunkInfo.facadeModuleId.split("/").pop()
            : "entry";
          return `${facadeModuleId.replace(/\.tsx?$/, "")}.js`;
        },
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (assetInfo) => {
          // Keep HTML files at root level
          if (assetInfo.name?.endsWith(".html")) {
            return "[name][extname]";
          }
          return "assets/[name]-[hash].[ext]";
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
});
