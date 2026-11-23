import store from "../store";

import enLanding from "./en/landing.json";
import esLanding from "./es/landing.json";
import frLanding from "./fr/landing.json";
import enRegister from "./en/register.json";
import esRegister from "./es/register.json";
import frRegister from "./fr/register.json";
import enFindWorkspace from "./en/find-workspace.json";
import esFindWorkspace from "./es/find-workspace.json";
import frFindWorkspace from "./fr/find-workspace.json";
import enOnboarding from "./en/onboarding.json";
import esOnboarding from "./es/onboarding.json";
import frOnboarding from "./fr/onboarding.json";

// Global i18n for the public base-domain pages. Translations are split per
// page and per locale as `./<locale>/<namespace>.json`, so a translator opens
// one locale folder and sees every page, and a new page adds one small file
// per locale. Register the namespace in BUNDLES (one block — static imports so
// the bundler and Jest can resolve them), then read it with
// `useTranslation("<namespace>")`. English is the default and per-key fallback.
//
// `store` is imported directly (not via the ../lib barrel) so this module never
// pulls geo.js → d3-scale, which keeps Jest suites that import it loadable.
const BUNDLES = {
  landing: { en: enLanding, es: esLanding, fr: frLanding },
  register: { en: enRegister, es: esRegister, fr: frRegister },
  findWorkspace: {
    en: enFindWorkspace,
    es: esFindWorkspace,
    fr: frFindWorkspace,
  },
  onboarding: { en: enOnboarding, es: esOnboarding, fr: frOnboarding },
};

export const LANGS = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
];

export const DEFAULT_LANG = "en";

export const resolveLang = (code) =>
  LANGS.some((l) => l.code === code) ? code : DEFAULT_LANG;

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
// future rebrand); default to "Akvo MIS" if config has not loaded.
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

// Read window live so a config.js that loads after this module (or a test
// that sets window.appConfig) is reflected; appName is captured at import.
export const brandName = () => window?.appConfig?.name || "Akvo MIS";

// Merge one namespace of the active locale over English and substitute {brand}.
export const getContent = (namespace, code) => {
  const bundle = BUNDLES[namespace] || {};
  const lang = resolveLang(code);
  return applyBrand(merge(bundle.en || {}, bundle[lang]), brandName());
};

// React hook: returns a namespace's content and re-renders on language change.
export const useTranslation = (namespace) => {
  const active = store.useState((s) => s.language.active);
  return getContent(namespace, active);
};
