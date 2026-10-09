const getMatomoConfig = () => {
  const url =
    process.env.REACT_APP_MATOMO_URL || window?.appConfig?.matomoUrl || "";
  const siteId =
    process.env.REACT_APP_MATOMO_SITE_ID ||
    (window?.appConfig?.matomoSiteId
      ? String(window.appConfig.matomoSiteId)
      : "");
  const dimTenant = parseInt(
    process.env.REACT_APP_MATOMO_DIM_TENANT ||
      window?.appConfig?.matomoDimTenant ||
      "1",
    10
  );
  const dimSubdomain = parseInt(
    process.env.REACT_APP_MATOMO_DIM_SUBDOMAIN ||
      window?.appConfig?.matomoDimSubdomain ||
      "2",
    10
  );

  return {
    url: url ? (url.endsWith("/") ? url : `${url}/`) : "",
    siteId,
    dimTenant,
    dimSubdomain,
  };
};

export const initMatomo = () => {
  const { url, siteId } = getMatomoConfig();
  if (!url || !siteId) {
    return false;
  }

  if (typeof window === "undefined") {
    return false;
  }

  window._paq = window._paq || [];

  if (document.getElementById("matomo-tracker-script")) {
    return true;
  }

  window._paq.push(["setTrackerUrl", `${url}matomo.php`]);
  window._paq.push(["setSiteId", siteId]);

  const script = document.createElement("script");
  script.id = "matomo-tracker-script";
  script.type = "text/javascript";
  script.async = true;
  script.src = `${url}matomo.js`;

  const firstScript = document.getElementsByTagName("script")[0];
  if (firstScript && firstScript.parentNode) {
    firstScript.parentNode.insertBefore(script, firstScript);
  } else if (document.head) {
    document.head.appendChild(script);
  }

  return true;
};

export const setTenantDimensions = (options = {}) => {
  if (typeof window === "undefined" || !window._paq) {
    return;
  }
  const { dimTenant, dimSubdomain } = getMatomoConfig();
  const { tenantName, subdomain } = options;

  if (tenantName) {
    window._paq.push(["setCustomDimension", dimTenant, tenantName]);
  } else {
    window._paq.push(["deleteCustomDimension", dimTenant]);
  }

  if (subdomain) {
    window._paq.push(["setCustomDimension", dimSubdomain, subdomain]);
  } else {
    window._paq.push(["deleteCustomDimension", dimSubdomain]);
  }
};

export const trackPageView = (customUrl) => {
  if (typeof window === "undefined" || !window._paq) {
    return;
  }

  if (customUrl) {
    window._paq.push(["setCustomUrl", customUrl]);
  }
  if (document && document.title) {
    window._paq.push(["setDocumentTitle", document.title]);
  }
  window._paq.push(["trackPageView"]);
  window._paq.push(["enableLinkTracking"]);
};

export const resetCustomDimensions = () => {
  if (typeof window === "undefined" || !window._paq) {
    return;
  }
  const { dimTenant, dimSubdomain } = getMatomoConfig();
  window._paq.push(["deleteCustomDimension", dimTenant]);
  window._paq.push(["deleteCustomDimension", dimSubdomain]);
};
