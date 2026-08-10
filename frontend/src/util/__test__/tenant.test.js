import axios from "axios";
import {
  baseDomain,
  baseDomainHost,
  baseDomainUrl,
  fetchTenant,
  onBaseDomainHost,
  workspaceUrl,
} from "../tenant";
import store from "../../lib/store";

jest.mock("axios");

const withLocation = (patch, run) => {
  const original = window.location;
  delete window.location;
  window.location = { ...original, ...patch };
  try {
    run();
  } finally {
    window.location = original;
  }
};

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

  test("fetchTenant stores the workspace this host serves", async () => {
    axios.mockResolvedValue({
      status: 200,
      data: { subdomain: "acme" },
    });
    const tenant = await fetchTenant();
    expect(tenant.subdomain).toBe("acme");
    expect(store.getRawState().tenant.subdomain).toBe("acme");
  });

  test("a 204 means there is no workspace here", async () => {
    // axios gives an empty body as "", which must not be mistaken for a
    // workspace whose subdomain happens to be blank.
    axios.mockResolvedValue({ status: 204, data: "" });
    expect(await fetchTenant()).toBeNull();
    expect(store.getRawState().tenant).toBeNull();
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
});
