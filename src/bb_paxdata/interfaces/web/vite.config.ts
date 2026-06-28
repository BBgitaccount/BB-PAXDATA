import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

const apiUrl = process.env.VITE_API_URL || "http://localhost:8000";
const wsUrl = apiUrl.replace("http://", "ws://").replace("https://", "wss://");

export default defineConfig({
	plugins: [react()],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./src"),
		},
	},
	build: {
		rollupOptions: {
			output: {
				manualChunks: {
					// Split heavy visualization libraries
					'd3-vendor': ['d3', 'd3-geo', 'd3-interpolate', 'd3-scale', 'd3-sankey'],
					'framer-motion': ['framer-motion'],
					'react-simple-maps': ['react-simple-maps'],
					'react-query': ['@tanstack/react-query'],
					'lucide-react': ['lucide-react'],
				},
			},
		},
		chunkSizeWarningLimit: 600,
	},
	server: {
		port: 5173,
		strictPort: false,
		proxy: {
			"/api/ws": { target: wsUrl, ws: true, changeOrigin: true },
			"/api": { target: apiUrl, changeOrigin: true },
			"/ws": { target: wsUrl, ws: true, changeOrigin: true },
		},
	},
});
