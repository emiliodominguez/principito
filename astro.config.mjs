import { defineConfig } from "astro/config";

export default defineConfig({
	output: "static",
	trailingSlash: "ignore",
	devToolbar: { enabled: false },
	server: { host: "localhost", port: 4321 },
	vite: {
		css: { preprocessorOptions: { scss: { api: "modern-compiler" } } },
		build: { chunkSizeWarningLimit: 1200 },
	},
});
