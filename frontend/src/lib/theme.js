// Single source of truth for the design-system colours. `tailwind.config.js`
// builds its `brand` token scale from these values, and any JS that can't use a
// Tailwind class (e.g. a <canvas> or inline <svg> fill) imports the raw values
// from here, so every colour changes in one place. It lives in lib/ so other
// pages can adopt the design system gradually. CommonJS so the Tailwind config
// (Node) can require it and components (webpack) can import it.
module.exports = {
  // Platform Ant Design primary (#1651b6, src/variables.scss $blue) so the
  // landing matches the antd-based app it funnels into.
  brand: "#1651b6", // primary: buttons, accents
  brandDark: "#114299", // hover
  brandLight: "#E7EEF9", // light backgrounds, badges
  brandBorder: "#A9C2EE", // borders, outline buttons
  brandDeep: "#0E2E6B", // hero band (deep navy)
  brandText: "#13448F", // blue text on white (9:1)
  brandBright: "#5B8DEF", // accent on dark surfaces / dark mode (6:1 on navy)
  brandLead: "#D4E2F7", // hero lead paragraph on the deep-navy band
  brandInk: "#0a1426", // hero demo card surface (near-black navy)
  brandFrame: "#060a14", // phone frame bezel
  brandChart: "#3A74D9", // hero demo chart area fill
  dotRgb: "130, 180, 255", // hero dot-field dots (light blue on navy)
};
