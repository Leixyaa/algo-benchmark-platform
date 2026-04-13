import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const isDesktop = mode === "desktop";

  return {
    base: isDesktop ? "./" : "/",
    plugins: [vue()],
    build: {
      outDir: isDesktop ? "dist-desktop" : "dist",
      emptyOutDir: true,
    },
  };
});
