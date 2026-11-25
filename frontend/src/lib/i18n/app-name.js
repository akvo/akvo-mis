// Brand identifiers — the same in every language, so they live here once
// rather than in each locale file. window.appConfig comes from the
// /config.js bootstrap script, read while the bundle is still evaluating;
// dereference defensively so a missing config.js degrades to a default
// name instead of taking the app down.
export const appName = window?.appConfig?.name || "Akvo MIS";
export const apkName = window?.appConfig?.apkName || appName;
