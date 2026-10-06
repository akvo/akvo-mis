import { api, store } from "../lib";

// Is this deployment serving one workspace per host?
//
// An empty base domain means one host for everything, and every
// host-aware branch in the app switches itself off. The frontend cannot
// work this out on its own: tenant-info answers 204 both on the base
// domain of a SaaS deployment and on a single-host install, and those
// two need opposite behaviour from the login route.
export const baseDomain = () => window?.appConfig?.baseDomain || "";

// Is the browser on the main site itself, rather than on a workspace?
//
// Read off the address bar, and deliberately not off the tenant lookup:
// an unknown workspace resolves to no tenant exactly as the base domain
// does, so a lookup cannot tell the two apart. Conflating them is what
// let the sign-up form render on `sleman.app.com` and offer addresses
// ending in `.sleman.app.com`. A deployment with no base domain has one
// host, and it is this one.
export const onBaseDomainHost = () => {
  const base = baseDomain().toLowerCase();
  if (!base) {
    return true;
  }
  const host = window.location.hostname.toLowerCase();
  return host === base || host === `www.${base}`;
};

// The label the platform console answers on, under the base domain.
// Configured per deployment, so a site that already serves something at
// admin.<domain> can move the console. The frontend cannot read the
// Django setting, so it arrives through config.js -- and falls back to
// "admin" when it does not, because regenerating config.js is a deploy
// step that gets missed and a console that stops recognising its own
// host is a blank page.
export const adminSubdomain = () =>
  (window?.appConfig?.adminSubdomain || "admin").toLowerCase();

// Is the browser on the platform console?
//
// Note the default differs from onBaseDomainHost deliberately. With no
// base domain that helper answers true, because a single-host install
// *is* the base domain — but a single-host install is one workspace and
// has no console, so this one answers false.
export const onAdminHost = () => {
  const base = baseDomain().toLowerCase();
  if (!base) {
    return false;
  }
  return (
    window.location.hostname.toLowerCase() === `${adminSubdomain()}.${base}`
  );
};

// The port comes from the address the browser is already on, so a local
// development port survives every redirect below and production — which
// has none — is unaffected. The domain never does: the host we are on
// may be a workspace, or a workspace that does not exist.
const port = () => (window.location.port ? `:${window.location.port}` : "");

// The main site's host.
export const baseDomainHost = () =>
  baseDomain() ? `${baseDomain()}${port()}` : window.location.host;

// Where a workspace's app lives.
export const workspaceUrl = (subdomain) =>
  `${window.location.protocol}//${subdomain}.${baseDomain()}${port()}`;

// A page on the platform console, which lives on its own host rather
// than a workspace's. Not baseDomainUrl: the main site is where people
// sign up, and it has no console on it.
export const adminUrl = (path = "") =>
  `${window.location.protocol}//${adminSubdomain()}.${baseDomain()}` +
  `${port()}${path}`;

// A page on the main site. Every way out of a workspace that does not
// exist leads here, and it is a different origin, so these are real
// navigations rather than router links.
export const baseDomainUrl = (path = "") =>
  `${window.location.protocol}//${baseDomainHost()}${path}`;

// The workspace this page is being served for. A 204 leaves it null,
// which is the answer that means "no workspace here" — the base domain,
// or a deployment that has none.
//
// A 404 is a different answer: the middleware refusing a host it does
// not serve. That is the one case where "there is no workspace" is a
// fact rather than a failure to find out, so it is recorded separately —
// any other failure (offline, 5xx) leaves the question open and is
// treated as the tenant-less case, the pre-login page being the safe
// place to be wrong.
export const fetchTenant = () =>
  api
    .get("tenant-info")
    .then(
      (res) => ({ tenant: res.data || null, missing: false }),
      (err) => ({ tenant: null, missing: err?.response?.status === 404 })
    )
    .then(({ tenant, missing }) => {
      store.update((s) => {
        s.tenant = tenant;
        s.tenantMissing = missing;
        s.tenantLoaded = true;
        if (tenant && tenant.language) {
          s.language.active = tenant.language;
        }
      });
      if (tenant && tenant.name) {
        document.title = `Akvo MIS - ${tenant.name}`;
      } else {
        document.title = "Akvo MIS";
      }
      return tenant;
    });
