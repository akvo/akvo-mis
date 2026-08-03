import { api, store } from "../lib";

// Is this deployment serving one workspace per host?
//
// An empty base domain means one host for everything, and every
// host-aware branch in the app switches itself off. The frontend cannot
// work this out on its own: tenant-info answers 204 both on the base
// domain of a SaaS deployment and on a single-host install, and those
// two need opposite behaviour from the login route.
export const baseDomain = () => window?.appConfig?.baseDomain || "";

// Where a workspace's app lives. The port comes from the address the
// browser is already on, so a local development port survives the
// redirect and production — which has none — is unaffected.
export const workspaceUrl = (subdomain) => {
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${window.location.protocol}//${subdomain}.${baseDomain()}${port}`;
};

// The workspace this page is being served for. A 204 leaves it null,
// which is the answer that means "no workspace here" — the base domain,
// or a deployment that has none. A failed request is treated the same
// way: the pre-login page is the safe place to be wrong.
export const fetchTenant = () =>
  api
    .get("tenant-info")
    .then(
      (res) => res.data || null,
      () => null
    )
    .then((tenant) => {
      store.update((s) => {
        s.tenant = tenant;
        s.tenantLoaded = true;
      });
      return tenant;
    });
