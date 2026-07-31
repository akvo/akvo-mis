import { clearLegacySessionExpiry } from "../date";

// `expiration_time` was a third source of truth for session validity, written
// by JS with no path — so it bound itself to whichever page wrote it, and a
// copy under one path shadowed the value at "/" on read. One expired session
// then locked the account out for good. Nothing reads it any more; this only
// has to remove copies an older build left in a browser.
describe("clearLegacySessionExpiry", () => {
  afterEach(() => {
    clearLegacySessionExpiry();
  });

  test("removes a copy stored at the root", () => {
    document.cookie = "expiration_time=2020-01-01T00:00:00+00:00; path=/";
    expect(document.cookie).toContain("expiration_time");

    clearLegacySessionExpiry();

    expect(document.cookie).not.toContain("expiration_time");
  });

  test("leaves the session cookie alone", () => {
    // The one the server sets and the browser expires on its own.
    document.cookie = "AUTH_TOKEN=still.here; path=/";

    clearLegacySessionExpiry();

    expect(document.cookie).toContain("AUTH_TOKEN=still.here");
  });
});
