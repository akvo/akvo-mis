import { getContent, resolveLang } from "../index";
import enLanding from "../en/landing.json";
import esLanding from "../es/landing.json";
import frLanding from "../fr/landing.json";
import enRegister from "../en/register.json";
import esRegister from "../es/register.json";
import frRegister from "../fr/register.json";
import enFindWorkspace from "../en/find-workspace.json";
import esFindWorkspace from "../es/find-workspace.json";
import frFindWorkspace from "../fr/find-workspace.json";
import enOnboarding from "../en/onboarding.json";
import esOnboarding from "../es/onboarding.json";
import frOnboarding from "../fr/onboarding.json";

// Every key path (objects by key, arrays by index) so a missing or extra key
// in a translation is caught — the one cost of the per-locale split.
const keyPaths = (node, prefix = "") => {
  if (Array.isArray(node)) {
    return node.flatMap((item, i) => keyPaths(item, `${prefix}[${i}]`));
  }
  if (node !== null && typeof node === "object") {
    return Object.keys(node).flatMap((key) =>
      keyPaths(node[key], prefix ? `${prefix}.${key}` : key)
    );
  }
  return [prefix];
};

const PAGES = {
  landing: { en: enLanding, es: esLanding, fr: frLanding },
  register: { en: enRegister, es: esRegister, fr: frRegister },
  findWorkspace: {
    en: enFindWorkspace,
    es: esFindWorkspace,
    fr: frFindWorkspace,
  },
  onboarding: { en: enOnboarding, es: esOnboarding, fr: frOnboarding },
};

describe("i18n", () => {
  it("es and fr mirror en key paths, per page", () => {
    Object.values(PAGES).forEach((page) => {
      const base = keyPaths(page.en).sort();
      expect(keyPaths(page.es).sort()).toEqual(base);
      expect(keyPaths(page.fr).sort()).toEqual(base);
    });
  });

  it("resolves a known locale and falls back to en for unknown", () => {
    expect(resolveLang("es")).toBe("es");
    expect(resolveLang("de")).toBe("en");
    expect(resolveLang()).toBe("en");
  });

  it("returns the requested locale's copy, falling back to en", () => {
    expect(getContent("landing", "es").hero.badge).toBe("Gratis para siempre");
    expect(getContent("landing", "fr").hero.badge).toBe(
      "Gratuit pour toujours"
    );
    // unknown locale falls back to English
    expect(getContent("landing", "de").hero.badge).toBe("Free forever");
    // register namespace resolves too
    expect(getContent("register", "es").submit).toBe(
      "Crear espacio de trabajo"
    );
  });

  it("substitutes {brand} from appConfig.name", () => {
    window.appConfig = { name: "AMIS" };
    expect(getContent("landing", "en").hero.title).toBe("Welcome to AMIS.");
    delete window.appConfig;
    expect(getContent("landing", "en").hero.title).toBe("Welcome to AIMS.");
  });
});
