import {
  initMatomo,
  setTenantDimensions,
  trackPageView,
  resetCustomDimensions,
} from "../matomo";

describe("Matomo Analytics Utility", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    delete window._paq;
    const existingScript = document.getElementById("matomo-tracker-script");
    if (existingScript && existingScript.parentNode) {
      existingScript.parentNode.removeChild(existingScript);
    }
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it("does not initialize if Matomo URL or Site ID is not configured", () => {
    delete process.env.REACT_APP_MATOMO_URL;
    delete process.env.REACT_APP_MATOMO_SITE_ID;

    const initialized = initMatomo();
    expect(initialized).toBe(false);
    expect(window._paq).toBeFalsy();
    expect(document.getElementById("matomo-tracker-script")).toBeNull();
  });

  it("initializes Matomo tracker script and configures URL and Site ID", () => {
    process.env.REACT_APP_MATOMO_URL = "https://matomo.example.org";
    process.env.REACT_APP_MATOMO_SITE_ID = "8";

    const initialized = initMatomo();
    expect(initialized).toBe(true);
    expect(Array.isArray(window._paq)).toBe(true);
    expect(window._paq).toContainEqual([
      "setTrackerUrl",
      "https://matomo.example.org/matomo.php",
    ]);
    expect(window._paq).toContainEqual(["setSiteId", "8"]);

    const script = document.getElementById("matomo-tracker-script");
    expect(script).not.toBeNull();
    expect(script.src).toBe("https://matomo.example.org/matomo.js");
  });

  it("does not inject duplicate script tags when initMatomo is called repeatedly", () => {
    process.env.REACT_APP_MATOMO_URL = "https://matomo.example.org";
    process.env.REACT_APP_MATOMO_SITE_ID = "8";

    initMatomo();
    const secondCall = initMatomo();
    expect(secondCall).toBe(true);

    const scripts = document.querySelectorAll("#matomo-tracker-script");
    expect(scripts.length).toBe(1);
  });

  it("sets custom tenant dimensions correctly", () => {
    process.env.REACT_APP_MATOMO_DIM_TENANT = "1";
    process.env.REACT_APP_MATOMO_DIM_SUBDOMAIN = "2";
    window._paq = [];

    setTenantDimensions({ tenantName: "sleman", subdomain: "sleman" });

    expect(window._paq).toContainEqual(["setCustomDimension", 1, "sleman"]);
    expect(window._paq).toContainEqual(["setCustomDimension", 2, "sleman"]);
  });

  it("deletes custom dimensions when tenant values are missing", () => {
    process.env.REACT_APP_MATOMO_DIM_TENANT = "1";
    process.env.REACT_APP_MATOMO_DIM_SUBDOMAIN = "2";
    window._paq = [];

    setTenantDimensions({});

    expect(window._paq).toContainEqual(["deleteCustomDimension", 1]);
    expect(window._paq).toContainEqual(["deleteCustomDimension", 2]);
  });

  it("tracks page views with custom url and title", () => {
    window._paq = [];
    document.title = "Akvo MIS - Sleman";

    trackPageView("/control-center/data");

    expect(window._paq).toContainEqual([
      "setCustomUrl",
      "/control-center/data",
    ]);
    expect(window._paq).toContainEqual([
      "setDocumentTitle",
      "Akvo MIS - Sleman",
    ]);
    expect(window._paq).toContainEqual(["trackPageView"]);
    expect(window._paq).toContainEqual(["enableLinkTracking"]);
  });

  it("resets custom dimensions", () => {
    process.env.REACT_APP_MATOMO_DIM_TENANT = "1";
    process.env.REACT_APP_MATOMO_DIM_SUBDOMAIN = "2";
    window._paq = [];

    resetCustomDimensions();

    expect(window._paq).toContainEqual(["deleteCustomDimension", 1]);
    expect(window._paq).toContainEqual(["deleteCustomDimension", 2]);
  });
});
