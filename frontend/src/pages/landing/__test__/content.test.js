import en from "../content/en.json";
import es from "../content/es.json";
import fr from "../content/fr.json";
import { getLandingContent, resolveLang } from "../content";

// Collect every key path (objects by key, arrays by index) so a missing or
// extra key in a translation is caught — the one cost of the per-locale split.
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

describe("landing content", () => {
  it("es.json and fr.json mirror en.json key paths", () => {
    const base = keyPaths(en).sort();
    expect(keyPaths(es).sort()).toEqual(base);
    expect(keyPaths(fr).sort()).toEqual(base);
  });

  it("resolves a known locale and falls back to en for unknown", () => {
    expect(resolveLang("es")).toBe("es");
    expect(resolveLang("de")).toBe("en");
    expect(resolveLang()).toBe("en");
  });

  it("returns the requested locale's copy", () => {
    expect(getLandingContent("es").hero.badge).toBe("Gratis para siempre");
    expect(getLandingContent("fr").hero.badge).toBe("Gratuit pour toujours");
    // unknown locale falls back to English
    expect(getLandingContent("de").hero.badge).toBe("Free forever");
  });

  it("substitutes {brand} from appConfig.name", () => {
    window.appConfig = { name: "AMIS" };
    expect(getLandingContent("en").hero.title).toBe("Welcome to AMIS.");
    delete window.appConfig;
    expect(getLandingContent("en").hero.title).toBe("Welcome to Akvo MIS.");
  });
});
