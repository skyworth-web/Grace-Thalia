import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";
import {
  copyFileSync,
  mkdirSync,
  existsSync,
  readdirSync,
  statSync,
  rmSync,
} from "fs";

export default defineConfig({
  plugins: [
    react(),

    {
      name: "copy-extension-files",
      apply: "build",
      enforce: "post",
      closeBundle() {
        // 1) manifest.json → dist/
        copyFileSync(
          resolve(__dirname, "src/manifest.json"),
          resolve(__dirname, "dist/manifest.json")
        );

        // 2) popup.html: dist/src/popup/popup.html → dist/popup/popup.html
        const builtPopupHtml = resolve(__dirname, "dist/src/popup/popup.html");
        const finalPopupDir = resolve(__dirname, "dist/popup");
        if (existsSync(builtPopupHtml)) {
          mkdirSync(finalPopupDir, { recursive: true });
          copyFileSync(builtPopupHtml, resolve(finalPopupDir, "popup.html"));
        } else {
          console.warn("⚠️ popup.html not found at", builtPopupHtml);
        }

        // (optional) remove dist/src to keep dist clean
        const distSrcDir = resolve(__dirname, "dist/src");
        if (existsSync(distSrcDir)) {
          rmSync(distSrcDir, { recursive: true, force: true });
        }

        // 3) raw content script → dist/content/contentRaw.js
        const contentSrc = resolve(
          __dirname,
          "src/content/contentRaw.js"
        );
        const contentDestDir = resolve(__dirname, "dist/content");
        mkdirSync(contentDestDir, { recursive: true });
        if (existsSync(contentSrc)) {
          copyFileSync(contentSrc, resolve(contentDestDir, "contentRaw.js"));
        }

        // 4) icons → dist/icons
        const iconsSrc = resolve(__dirname, "src/icons");
        const iconsDest = resolve(__dirname, "dist/icons");
        mkdirSync(iconsDest, { recursive: true });

        if (existsSync(iconsSrc)) {
          for (const file of readdirSync(iconsSrc)) {
            const s = resolve(iconsSrc, file);
            const d = resolve(iconsDest, file);
            if (statSync(s).isFile()) copyFileSync(s, d);
          }
        }

        // 5) pdf.worker → dist/
        const pdfSrc = resolve(
          __dirname,
          "node_modules/pdfjs-dist/build/pdf.worker.min.js"
        );
        const pdfDest = resolve(__dirname, "dist/pdf.worker.min.js");
        if (existsSync(pdfSrc)) copyFileSync(pdfSrc, pdfDest);
      },
    },
  ],

  build: {
    emptyOutDir: true,
    outDir: "dist",
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "src/popup/popup.html"),
        background: resolve(__dirname, "src/background/background.ts"),
        // content is copied raw, not bundled
      },
      output: {
        inlineDynamicImports: false,
        entryFileNames: (chunk) => {
          const id = chunk.facadeModuleId || "";
          if (id.includes("popup/popup.html")) return "popup/popup.js";
          if (id.includes("background")) return "background/background.js";
          return "chunks/[name].js";
        },
        chunkFileNames: "chunks/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },

  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
});
