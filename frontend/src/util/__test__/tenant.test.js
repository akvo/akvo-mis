import axios from "axios";
import { baseDomain, fetchTenant, workspaceUrl } from "../tenant";
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

  test("fetchTenant stores the workspace this host serves", async () => {
    axios.mockResolvedValue({
      status: 200,
      data: { subdomain: "acme", name: "Kenya" },
    });
    const tenant = await fetchTenant();
    expect(tenant.name).toBe("Kenya");
    expect(store.getRawState().tenant.subdomain).toBe("acme");
  });

  test("a 204 means there is no workspace here", async () => {
    // axios gives an empty body as "", which must not be mistaken for a
    // workspace with a blank name.
    axios.mockResolvedValue({ status: 204, data: "" });
    expect(await fetchTenant()).toBeNull();
    expect(store.getRawState().tenant).toBeNull();
  });

  test("a failed request leaves no workspace rather than throwing", async () => {
    axios.mockRejectedValue(new Error("network"));
    expect(await fetchTenant()).toBeNull();
  });
});
