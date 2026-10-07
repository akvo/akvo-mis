import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import Header from "../Header";
import { store, config } from "../../../lib";

describe("Header component", () => {
  beforeEach(() => {
    store.update((s) => {
      s.isLoggedIn = false;
      s.user = null;
      s.tenant = null;
    });
  });

  test("renders default logo when tenant has no custom logo", () => {
    render(
      <BrowserRouter>
        <Header />
      </BrowserRouter>
    );
    const logoImg = screen.getByRole("img", { name: "Akvo MIS" });
    expect(logoImg).toBeInTheDocument();
    expect(logoImg.getAttribute("src")).toBe(config.siteLogo);
  });

  test("renders tenant custom logo and alt text when available", () => {
    store.update((s) => {
      s.tenant = {
        name: "Ministry of Health",
        logo: "/images/custom-logo.png",
      };
    });

    render(
      <BrowserRouter>
        <Header />
      </BrowserRouter>
    );
    const logoImg = screen.getByRole("img", {
      name: "Ministry of Health Logo",
    });
    expect(logoImg).toBeInTheDocument();
    expect(logoImg.getAttribute("src")).toBe("/images/custom-logo.png");
  });

  test("falls back to default logo on image load error", () => {
    store.update((s) => {
      s.tenant = {
        name: "Broken Logo Tenant",
        logo: "/images/non-existent.png",
      };
    });

    render(
      <BrowserRouter>
        <Header />
      </BrowserRouter>
    );
    const logoImg = screen.getByRole("img", {
      name: "Broken Logo Tenant Logo",
    });
    fireEvent.error(logoImg);
    expect(logoImg.src).toContain(config.siteLogo);
  });
});
