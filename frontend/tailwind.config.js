/** @type {import('tailwindcss').Config} */
// Scoped to the landing page only: `important: "#landing"` and preflight off
// keep every utility class inside <div id="landing">, so Ant Design screens
// render exactly as before. The `brand` token scale mirrors the platform's
// Ant Design primary; all hexes live in ./src/lib/theme.js (the one
// place colours change — the hero canvas/SVG import the same file).
const brand = require("./src/lib/theme");

module.exports = {
  content: [
    "./src/pages/landing/**/*.{js,jsx}",
    "./src/pages/onboarding/**/*.{js,jsx}",
    "./src/components/Turnstile.jsx",
  ],
  important: "#landing",
  corePlugins: { preflight: false },
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: brand.brand,
          dark: brand.brandDark,
          light: brand.brandLight,
          border: brand.brandBorder,
          deep: brand.brandDeep,
          text: brand.brandText,
          bright: brand.brandBright,
          lead: brand.brandLead,
          ink: brand.brandInk,
          frame: brand.brandFrame,
          chart: brand.brandChart,
        },
        "text-primary": "#191919",
        "text-secondary": "#474747",
        "text-muted": "#656565",
        "text-subtle": "#767676",
        "text-faint": "#E8E8E8",
        "bg-primary": "#FFFFFF",
        "bg-secondary": "#FAFAFA",
        "bg-dark": "#191919",
      },
      fontFamily: {
        title: ['"Roboto Condensed"', "sans-serif"],
        sans: ["Assistant", "Arial", "Helvetica", "sans-serif"],
      },
    },
  },
  plugins: [],
};
