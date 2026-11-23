import en from "./en/ui";
import fr from "./fr/ui";
import es from "./es/ui";

// Platform UI strings (menus, buttons, messages), split per locale as
// ./<locale>/ui.js. Per-locale JS — not JSON — because many values are
// JSX elements or functions. Each locale overrides English per key;
// English fills any gap so a missing translation never crashes a page.
const uiText = {
  en,
  es: { ...en, ...es },
  fr: { ...en, ...fr },
};

export default uiText;
