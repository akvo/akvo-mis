import axios from "axios";
import {
  baseDomain,
  baseDomainHost,
  baseDomainUrl,
  fetchTenant,
  onAdminHost,
  onBaseDomainHost,
  workspaceUrl,
  adminUrl,
} from "../tenant";
import store from "../../lib/store";

jest.mock("axios");

const withLocation = (patch, run) => {
  const original = window.location;
  delete window.location;
  window.location = { ...original, ...patch };
  try {
    return run();
  } finally {
    window.location = original;
  }
};

describe("the console's label", () => {
  const appConfig = window.appConfig;

  afterEach(() => {
    window.appConfig = appConfig;
  });

  const at = (hostname, config) => {
    window.appConfig = { ...appConfig, baseDomain: "app.com", ...config };
    return withLocation({ hostname, protocol: "http:", port: "" }, () => ({
      onAdmin: onAdminHost(),
      url: adminUrl("/admin/tenants"),
    }));
  };

  it("follows the deployment's configured label", () => {
    // A deployment that already serves something at admin.<domain>
    // moves the console; both the host test and the link it builds have
    // to follow, or Exit lands nowhere.
    const moved = { adminSubdomain: "console" };
    expect(at("console.app.com", moved).onAdmin).toBe(true);
    expect(at("admin.app.com", moved).onAdmin).toBe(false);
    expect(at("console.app.com", moved).url).toBe(
      "http://console.app.com/admin/tenants"
    );
  });

  it("falls back to admin when config.js predates the key", () => {
    // Regenerating config.js is a deploy step that gets missed, and a
    // console that stops recognising its own host is a blank page.
    // `{}` is the point: the key is absent, exactly as it is in a
    // config.js generated before this setting existed.
    expect(at("admin.app.com", {}).onAdmin).toBe(true);
    expect(at("admin.app.com", {}).url).toBe(
      "http://admin.app.com/admin/tenants"
    );
  });
});

describe("tenant util", () => {
  const appConfig = window.appConfig;

  beforeEach(() => {
    window.appConfig = { ...appConfig, baseDomain: "app.com" };
    store.update((s) => {
      s.tenant = null;
      s.tenantMissing = false;
    });
  });

  afterEach(() => {
    window.appConfig = appConfig;
  });

  test("baseDomain is empty on a single-host deployment", () => {
    window.appConfig = { ...appConfig };
    expect(baseDomain()).toBe("");
  });

  test("workspaceUrl puts the workspace in front of the base domain", () => {
    withLocation({ protocol: "https:", port: "" }, () => {
      expect(workspaceUrl("acme")).toBe("https://acme.app.com");
    });
  });

  test("workspaceUrl keeps the port the browser is already using", () => {
    // Local development runs on :3000 and the redirect has to land
    // there, not on the default port of a server that is not listening.
    withLocation({ protocol: "http:", port: "3000" }, () => {
      expect(workspaceUrl("acme")).toBe("http://acme.app.com:3000");
    });
  });

  test("the base domain and its www alias are the main site", () => {
    withLocation({ hostname: "app.com" }, () => {
      expect(onBaseDomainHost()).toBe(true);
    });
    withLocation({ hostname: "www.app.com" }, () => {
      expect(onBaseDomainHost()).toBe(true);
    });
  });

  test("a workspace host is not the main site", () => {
    withLocation({ hostname: "acme.app.com" }, () => {
      expect(onBaseDomainHost()).toBe(false);
    });
  });

  test("a workspace that does not exist is not the main site either", () => {
    // The whole point of deciding this from the address bar: a lookup
    // answers "no workspace" here just as it does on the base domain,
    // and the sign-up form must render on only one of the two.
    withLocation({ hostname: "sleman.app.com" }, () => {
      expect(onBaseDomainHost()).toBe(false);
    });
  });

  test("a single-host deployment is always the main site", () => {
    window.appConfig = { ...appConfig };
    withLocation({ hostname: "mis.example.org" }, () => {
      expect(onBaseDomainHost()).toBe(true);
    });
  });

  test("the main site's host ignores the host the browser is on", () => {
    withLocation({ hostname: "sleman.app.com", host: "sleman.app.com" }, () => {
      expect(baseDomainHost()).toBe("app.com");
    });
  });

  test("the main site's host keeps the port in local development", () => {
    withLocation({ host: "acme.app.com:3000", port: "3000" }, () => {
      expect(baseDomainHost()).toBe("app.com:3000");
    });
  });

  test("a single-host deployment's main site is the host it is on", () => {
    window.appConfig = { ...appConfig };
    withLocation({ host: "mis.example.org", port: "" }, () => {
      expect(baseDomainHost()).toBe("mis.example.org");
    });
  });

  test("baseDomainUrl builds a page on the main site", () => {
    withLocation({ protocol: "https:", host: "sleman.app.com", port: "" }, () =>
      expect(baseDomainUrl("/find-workspace")).toBe(
        "https://app.com/find-workspace"
      )
    );
  });

  test("fetchTenant stores the workspace this host serves and updates language and title", async () => {
    axios.mockResolvedValue({
      status: 200,
      data: {
        subdomain: "acme",
        name: "Acme Corp",
        logo: "/images/logo.png",
        language: "fr",
      },
    });
    const tenant = await fetchTenant();
    expect(tenant.subdomain).toBe("acme");
    expect(tenant.name).toBe("Acme Corp");
    expect(tenant.logo).toBe("/images/logo.png");
    expect(tenant.language).toBe("fr");
    expect(store.getRawState().tenant.subdomain).toBe("acme");
    expect(store.getRawState().tenant.name).toBe("Acme Corp");
    expect(store.getRawState().tenant.logo).toBe("/images/logo.png");
    expect(store.getRawState().language.active).toBe("fr");
    expect(document.title).toBe("Akvo MIS - Acme");
  });

  test("fetchTenant falls back to title-cased subdomain when tenant name is empty", async () => {
    axios.mockResolvedValue({
      status: 200,
      data: {
        subdomain: "test-workspace",
        name: "",
        logo: null,
      },
    });
    await fetchTenant();
    expect(document.title).toBe("Akvo MIS - Test Workspace");
  });

  test("a 204 means there is no workspace here and resets title", async () => {
    // axios gives an empty body as "", which must not be mistaken for a
    // workspace whose subdomain happens to be blank.
    axios.mockResolvedValue({ status: 204, data: "" });
    expect(await fetchTenant()).toBeNull();
    expect(store.getRawState().tenant).toBeNull();
    expect(document.title).toBe("Akvo MIS");
  });

  test("a 404 means this host serves no workspace at all", async () => {
    axios.mockRejectedValue({ response: { status: 404 } });
    expect(await fetchTenant()).toBeNull();
    expect(store.getRawState().tenantMissing).toBe(true);
  });
  test("a failed request leaves no workspace rather than throwing", async () => {
    axios.mockRejectedValue(new Error("network"));
    expect(await fetchTenant()).toBeNull();
  });
  test("being unable to ask is not the same as being told there is none", async () => {
    // Offline, or a 5xx, leaves the question open. Answering it with the
    // dead-workspace page would tell a workspace's own users that their
    // address does not exist every time the backend hiccups.
    axios.mockRejectedValue(new Error("network"));
    await fetchTenant();
    expect(store.getRawState().tenantMissing).toBe(false);
  });

  describe("onAdminHost", () => {
    it("is true on the console host", () => {
      withLocation({ hostname: "admin.app.com" }, () => {
        expect(onAdminHost()).toBe(true);
      });
    });

    it("is false on a workspace and on the base domain", () => {
      withLocation({ hostname: "acme.app.com" }, () => {
        expect(onAdminHost()).toBe(false);
      });
      withLocation({ hostname: "app.com" }, () => {
        expect(onAdminHost()).toBe(false);
      });
    });

    it("is false with no base domain", () => {
      // Unlike onBaseDomainHost, which treats a single-host install as
      // the base domain, a single-host install has no console at all.
      window.appConfig = { ...window.appConfig, baseDomain: "" };
      withLocation({ hostname: "admin.app.com" }, () => {
        expect(onAdminHost()).toBe(false);
      });
    });
  });
});
