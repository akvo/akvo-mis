import { api, store } from "../lib";

// Is this deployment serving one workspace per host?
//
// An empty base domain means one host for everything, and every
// host-aware branch in the app switches itself off. The frontend cannot
// work this out on its own: tenant-info answers 204 both on the base
// domain of a SaaS deployment and on a single-host install, and those
// two need opposite behaviour from the login route.
export const baseDomain = () => window?.appConfig?.baseDomain || "";

// Can this deployment render an embedded dashboard?
//
// False when EMBED_HOST is unset, which is the default. Embedding needs
// an origin of its own — the snippet is third-party markup and must not
// run on ours — and no such origin exists unless somebody configured
// one. The create dialog reads this so it does not offer a kind of
// dashboard that could never be displayed; embedded dashboards that
// already exist stay listed and editable either way.
export const embedEnabled = () => Boolean(window?.appConfig?.embedEnabled);

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

// The main site's host. The port comes from the address the browser is
// already on — local development runs on one and production does not —
// while the domain comes from the configuration, because the host we are
// on may be a workspace, or a workspace that does not exist.
export const baseDomainHost = () => {
  const port = window.location.port ? `:${window.location.port}` : "";
  return baseDomain() ? `${baseDomain()}${port}` : window.location.host;
};
// Where a workspace's app lives. The port comes from the address the
// browser is already on, so a local development port survives the
// redirect and production — which has none — is unaffected.
export const workspaceUrl = (subdomain) => {
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${window.location.protocol}//${subdomain}.${baseDomain()}${port}`;
};

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
      });
      return tenant;
    });
