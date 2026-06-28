/** @type {import('tailwindcss').Config} */
export default {
	content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
	darkMode: "class",
	theme: {
		extend: {
			screens: {
				xs: "475px",
				sm: "640px",
				md: "768px",
				lg: "1024px",
				xl: "1280px",
				"2xl": "1536px",
				"3xl": "1920px",
			},
			colors: {
				carbon: {
					950: "rgb(var(--carbon-950-rgb) / <alpha-value>)",
					900: "rgb(var(--carbon-900-rgb) / <alpha-value>)",
					850: "rgb(var(--carbon-850-rgb) / <alpha-value>)",
					800: "rgb(var(--carbon-800-rgb) / <alpha-value>)",
					750: "rgb(var(--carbon-750-rgb) / <alpha-value>)",
					700: "rgb(var(--carbon-700-rgb) / <alpha-value>)",
					650: "rgb(var(--carbon-650-rgb) / <alpha-value>)",
					600: "rgb(var(--carbon-600-rgb) / <alpha-value>)",
					550: "rgb(var(--carbon-550-rgb) / <alpha-value>)",
					500: "rgb(var(--carbon-500-rgb) / <alpha-value>)",
					400: "rgb(var(--carbon-400-rgb) / <alpha-value>)",
					300: "rgb(var(--carbon-300-rgb) / <alpha-value>)",
					200: "rgb(var(--carbon-200-rgb) / <alpha-value>)",
					100: "rgb(var(--carbon-100-rgb) / <alpha-value>)",
					50: "rgb(var(--carbon-50-rgb) / <alpha-value>)",
				},
				signal: {
					fail: "rgb(var(--signal-fail-rgb) / <alpha-value>)",
					pass: "rgb(var(--signal-pass-rgb) / <alpha-value>)",
					warn: "rgb(var(--signal-warn-rgb) / <alpha-value>)",
					info: "rgb(var(--signal-info-rgb) / <alpha-value>)",
				},
			},
			fontFamily: {
				sans: [
					"Inter",
					"SF Pro Display",
					"Helvetica Neue",
					"system-ui",
					"sans-serif",
				],
				mono: ["JetBrains Mono", "IBM Plex Mono", "SF Mono", "monospace"],
			},
			fontSize: {
				micro: ["0.65rem", { lineHeight: "0.85rem", letterSpacing: "0.05em" }],
				"2xs": ["0.7rem", { lineHeight: "0.95rem", letterSpacing: "0.02em" }],
			},
			borderRadius: {
				sharp: "0px",
				micro: "2px",
				soft: "4px",
			},
			borderWidth: {
				hair: "0.5px",
				micro: "1px",
			},
			spacing: {
				18: "4.5rem",
				22: "5.5rem",
			},
			boxShadow: {
				subtle: "0 1px 0 0 rgba(255,255,255,0.03)",
				elevated: "0 0 0 1px rgba(255,255,255,0.04)",
			},
			letterSpacing: {
				tight: "-0.02em",
				diplomatic: "0.04em",
			},
			transitionDuration: {
				swift: "150ms",
				deliberate: "300ms",
			},
		},
	},
	plugins: [],
};
