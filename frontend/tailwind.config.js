/** @type {import('tailwindcss').Config} */
// Scoped to the landing page only: `important: "#landing"` and preflight off
// keep every utility class inside <div id="landing">, so Ant Design screens
// render exactly as before. Tokens + fonts mirror akvo.org (akvo-web).
module.exports = {
  content: ["./src/pages/landing/**/*.{js,jsx}"],
  important: "#landing",
  corePlugins: { preflight: false },
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        // Token names are historical (akvo-web was green); values are the
        // platform's Ant Design primary (#1651b6, src/variables.scss $blue)
        // so the landing matches the antd-based app. Change hex here only.
        akvo: {
          DEFAULT: "#1651b6", // primary: buttons, accents (antd $blue)
          dark: "#114299", // hover
          light: "#E7EEF9", // light backgrounds, badges
          border: "#A9C2EE", // borders, outline buttons
          deep: "#0E2E6B", // hero band (deep navy)
          text: "#13448F", // blue text on white (9:1)
          bright: "#5B8DEF", // accent on dark surfaces / dark mode (6:1 on navy)
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
