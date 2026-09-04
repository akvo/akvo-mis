import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import EmbedFrame, { EMBED_SANDBOX } from "../EmbedFrame";

// jsdom serves the page from http://localhost, so anything else is a
// different origin as far as these tests are concerned.
const EMBED = "http://embed.example.com/api/v1/embed/sometoken";

describe("EmbedFrame sandbox", () => {
  // The snippet runs as its own document on EMBED_HOST. `allow-same-origin`
  // is REQUIRED here, not merely tolerated: without it the browser forces
  // an opaque origin, and both vendors this feature exists for fail there
  // (Tableau's fetches are refused by CORS as `Origin: null`, Power BI
  // cannot reach its storage). It is safe only because the document is
  // cross-origin, so the origin it grants is the embed host's, not ours.
  it("grants same-origin, which the separate host makes safe", () => {
    expect(EMBED_SANDBOX).toContain("allow-scripts");
    expect(EMBED_SANDBOX).toContain("allow-same-origin");
  });

  it("never grants top navigation", () => {
    expect(EMBED_SANDBOX).not.toContain("allow-top-navigation");
    render(<EmbedFrame src={EMBED} title="Sales" />);
    expect(screen.getByTitle("Sales").getAttribute("sandbox")).not.toContain(
      "allow-top-navigation"
    );
  });

  it("grants exactly the tokens a BI embed needs", () => {
    expect(EMBED_SANDBOX).toBe(
      "allow-scripts allow-same-origin allow-popups " +
        "allow-popups-to-escape-sandbox allow-forms allow-downloads"
    );
  });

  it("puts the sandbox on the rendered iframe", () => {
    render(<EmbedFrame src={EMBED} title="Sales" />);
    expect(screen.getByTitle("Sales")).toHaveAttribute(
      "sandbox",
      EMBED_SANDBOX
    );
  });
});

// With `allow-same-origin` set, pointing this frame at our own origin
// would hand the snippet this page's DOM and cookies — exactly what the
// separate embed host exists to prevent. This is the security regression
// test for the feature, and it replaces the old "never allow-same-origin"
// one, which was correct only while the frame used srcdoc.
describe("EmbedFrame refuses a src it must not frame", () => {
  it("frames a cross-origin embed URL", () => {
    render(<EmbedFrame src={EMBED} title="Sales" />);
    expect(screen.getByTitle("Sales")).toHaveAttribute("src", EMBED);
  });

  it("refuses an absolute URL on our own origin", () => {
    render(
      <EmbedFrame src="http://localhost/api/v1/embed/tok" title="Sales" />
    );
    expect(screen.queryByTitle("Sales")).not.toBeInTheDocument();
  });

  it("refuses a relative URL, which is our origin by definition", () => {
    render(<EmbedFrame src="/api/v1/embed/tok" title="Sales" />);
    expect(screen.queryByTitle("Sales")).not.toBeInTheDocument();
  });

  it("refuses an unparseable src rather than guessing", () => {
    render(<EmbedFrame src="http://[bad" title="Sales" />);
    expect(screen.queryByTitle("Sales")).not.toBeInTheDocument();
  });

  it("reports plainly when embedding is unconfigured", () => {
    render(<EmbedFrame src={null} title="Sales" />);
    expect(screen.queryByTitle("Sales")).not.toBeInTheDocument();
    expect(screen.getByText(/not configured/i)).toBeInTheDocument();
  });
});

describe("EmbedFrame never parses author markup", () => {
  it("renders no snippet content into our own document", () => {
    // The markup only ever exists inside the cross-origin document the
    // frame loads. Nothing about the author's HTML is parsed here.
    const { container } = render(<EmbedFrame src={EMBED} title="Sales" />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("tableau-viz")).toBeNull();
    expect(container.innerHTML).not.toContain("srcdoc");
  });
});
