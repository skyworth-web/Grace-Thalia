import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve, dirname } from "path";
import { copyFileSync, mkdirSync } from "fs";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const srcRoot = resolve(__dirname, "src");

export default defineConfig({
  root: srcRoot,
  plugins: [
    react(),
    {
      name: "copy-manifest",
      closeBundle() {
        // Copy manifest.json to dist
        const manifestSrc = resolve(srcRoot, "manifest.json");
        const manifestDest = resolve(__dirname, "dist/manifest.json");
        copyFileSync(manifestSrc, manifestDest);
        
        // Copy icons directory if it exists
        const iconsSrc = resolve(srcRoot, "icons");
        const iconsDest = resolve(__dirname, "dist/icons");
        try {
          mkdirSync(iconsDest, { recursive: true });
          const { readdirSync, statSync, copyFileSync: copyFile } = require("fs");
          const { join } = require("path");
          
          if (statSync(iconsSrc).isDirectory()) {
            const files = readdirSync(iconsSrc);
            files.forEach((file: string) => {
              const srcPath = join(iconsSrc, file);
              const destPath = join(iconsDest, file);
              if (statSync(srcPath).isFile()) {
                copyFile(srcPath, destPath, (err: Error) => {
                  if (err) console.error(`Failed to copy ${file}:`, err);
                });
              }
            });
          }
        } catch (e) {
          // Icons directory might not exist yet - that's okay
          console.log("Icons directory not found - you'll need to create icon files");
        }
      },
    },
  ],
  build: {
    outDir: resolve(__dirname, "dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: resolve(srcRoot, "popup/popup.html"),
        "background/background": resolve(srcRoot, "background/background.ts"),
        "content/contentScript": resolve(srcRoot, "content/contentScript.tsx"),
      },
      output: {
        entryFileNames: (chunkInfo) => {
          // For HTML entries, the script inside becomes the entry
          // We need to handle the actual JS entry point
          const facadeModuleId = chunkInfo.facadeModuleId || "";
          
          if (facadeModuleId.includes("popup/index.tsx")) {
            return "popup/index.js";
          }
          if (facadeModuleId.includes("background/background.ts")) {
            return "background/background.js";
          }
          if (facadeModuleId.includes("content/contentScript.tsx")) {
            return "content/contentScript.js";
          }
          
          // Fallback
          const name = chunkInfo.name || "entry";
          if (name.includes("background")) {
            return "background/background.js";
          }
          if (name.includes("content")) {
            return "content/contentScript.js";
          }
          
          const fileName = facadeModuleId.split("/").pop()?.replace(/\.tsx?$/, "") || "entry";
          return `${fileName}.js`;
        },
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (assetInfo) => {
          // Keep HTML files in popup directory
          if (assetInfo.name?.endsWith(".html")) {
            return "popup/[name][extname]";
          }
          // Put popup JS files in popup directory
          if (assetInfo.name?.includes("popup.html.js")) {
            return "popup/[name]";
          }
          return "assets/[name]-[hash].[ext]";
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": srcRoot,
    },
  },
});

