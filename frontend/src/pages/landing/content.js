import en from "./content/en.json";
import es from "./content/es.json";
import fr from "./content/fr.json";

// One file per language (D-9). English is the default and the fallback — both
// when a locale file is absent entirely and per-key for anything it lacks.
const LOCALES = { en, es, fr };

export const LANDING_LANGS = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
];

export const DEFAULT_LANG = "en";

export const resolveLang = (code) =>
  LANDING_LANGS.some((l) => l.code === code) ? code : DEFAULT_LANG;

const isPlainObject = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

// Merge the active locale over English. Objects merge key-by-key so a missing
// key falls back to en; arrays and scalars from the locale win when present.
const merge = (base, override) => {
  if (typeof override === "undefined") {
    return base;
  }
  if (isPlainObject(base) && isPlainObject(override)) {
    const out = { ...base };
    Object.keys(base).forEach((key) => {
      out[key] = merge(base[key], override[key]);
    });
    return out;
  }
  return override;
};

// Replace the {brand} token everywhere with the app-wide name (one knob for a
// future rebrand, D-11); default to "Akvo MIS" if config has not loaded.
const applyBrand = (node, brand) => {
  if (typeof node === "string") {
    return node.split("{brand}").join(brand);
  }
  if (Array.isArray(node)) {
    return node.map((item) => applyBrand(item, brand));
  }
  if (isPlainObject(node)) {
    const out = {};
    Object.keys(node).forEach((key) => {
      out[key] = applyBrand(node[key], brand);
    });
    return out;
  }
  return node;
};

export const brandName = () => window?.appConfig?.name || "Akvo MIS";

export const getLandingContent = (code) => {
  const lang = resolveLang(code);
  const merged = merge(en, LOCALES[lang]);
  return applyBrand(merged, brandName());
};
