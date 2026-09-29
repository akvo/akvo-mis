import React from "react";
import { render, screen } from "@testing-library/react";
import { CookiesProvider } from "react-cookie";
import InspectionBanner from "../InspectionBanner";
import { store } from "../../../lib";
import "@testing-library/jest-dom";

// A token whose only claim that matters here is `exp`. The banner reads
// the end time out of the cookie, so an assertion about it has to put a
// real one there.
const tokenExpiringAt = (date) => {
  const payload = btoa(JSON.stringify({ exp: Math.floor(date / 1000) }));
  return `header.${payload}.signature`;
};

const renderBanner = () =>
  render(
    <CookiesProvider>
      <InspectionBanner />
    </CookiesProvider>
  );

describe("InspectionBanner", () => {
  beforeEach(() => {
    document.cookie = "AUTH_TOKEN=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    store.update((s) => {
      s.user = null;
      s.tenant = null;
    });
  });

  it("renders nothing for an ordinary session", () => {
    store.update((s) => {
      s.user = { id: 1, is_superuser: true };
      s.tenant = { subdomain: "acme" };
    });
    const { container } = renderBanner();
    expect(container).toBeEmptyDOMElement();
  });

  it("names the workspace and says the session is read only", () => {
    store.update((s) => {
      s.user = { id: 2, is_inspecting: true };
      s.tenant = { subdomain: "acme" };
    });
    renderBanner();
    expect(screen.getByText("acme")).toBeInTheDocument();
    expect(screen.getByText(/read only/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /exit inspection/i })
    ).toBeInTheDocument();
  });

  it("says when the session ends", () => {
    const ends = new Date();
    ends.setHours(14, 30, 0, 0);
    document.cookie = `AUTH_TOKEN=${tokenExpiringAt(ends.getTime())}`;
    store.update((s) => {
      s.user = { id: 3, is_inspecting: true };
      s.tenant = { subdomain: "acme" };
    });
    renderBanner();
    const expected = ends.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    expect(
      screen.getByText(new RegExp(`ends ${expected}`))
    ).toBeInTheDocument();
  });

  it("survives a token it cannot read", () => {
    document.cookie = "AUTH_TOKEN=not-a-jwt";
    store.update((s) => {
      s.user = { id: 4, is_inspecting: true };
      s.tenant = { subdomain: "acme" };
    });
    renderBanner();
    expect(screen.getByText(/read only/i)).toBeInTheDocument();
    expect(screen.queryByText(/ends/i)).not.toBeInTheDocument();
  });
});
