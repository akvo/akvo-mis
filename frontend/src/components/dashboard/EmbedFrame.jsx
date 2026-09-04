import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { store, uiText } from "../../lib";

// =========================================================
// The embedded dashboard's frame (VIZ-019 D-4a, D-4b)
// =========================================================
// The author's snippet is never rendered by this application. It is
// served as its own document from EMBED_HOST — a host that is not ours —
// and this component only frames it.
//
// It cannot run in our origin: that is cross-site scripting against every
// visitor of a public page, and AUTH_TOKEN is a cookie without HttpOnly,
// so a snippet could read the session straight out of document.cookie.
//
// An earlier version of this feature tried the other obvious answer —
// `srcdoc` in a frame sandboxed *without* `allow-same-origin`, giving the
// markup an opaque origin. It does isolate the snippet, and it also stops
// it working: measured against both vendors this feature exists for,
// Tableau's API fetches are refused by CORS because they carry
// `Origin: null`, and Power BI's own frame, which inherits the sandbox,
// cannot reach its storage.
//
// So `allow-same-origin` is present here, and is REQUIRED rather than
// merely tolerated: a sandbox without it would force the opaque origin
// back. It is safe for one reason only — the document is cross-origin to
// this page, so the origin it grants is the embed host's, never ours.
//
// That reverses which mistake to guard against. It is no longer "never
// add a token"; it is: NEVER POINT THIS FRAME AT OUR OWN ORIGIN. With
// `allow-same-origin` set, a same-origin src would hand the snippet this
// page's DOM and cookies — precisely what the separate host prevents.
// `sameOrigin()` below refuses that, and a test asserts it.
//
// `allow-top-navigation` is still withheld, so framed content cannot
// navigate the visitor's tab away from this page.
export const EMBED_SANDBOX =
  "allow-scripts allow-same-origin allow-popups " +
  "allow-popups-to-escape-sandbox allow-forms allow-downloads";

// An unparseable src counts as same-origin: the safe reading of "I cannot
// tell where this points" is "do not frame it".
const sameOrigin = (src) => {
  try {
    return new URL(src, window.location.href).origin === window.location.origin;
  } catch (e) {
    return true;
  }
};

const EmbedFrame = ({ src, title }) => {
  const { language } = store.useState((s) => s);
  const text = useMemo(() => uiText[language.active], [language.active]);

  // No src means EMBED_HOST is unconfigured for this deployment. Say so
  // plainly; the one thing we must not do is fall back to rendering the
  // markup here.
  if (!src || sameOrigin(src)) {
    return (
      <div className="dashboard-embed-frame">
        <p>{text.dashboardEmbedUnavailable}</p>
      </div>
    );
  }

  return (
    <div className="dashboard-embed-frame">
      <iframe title={title} sandbox={EMBED_SANDBOX} src={src} allowFullScreen />
    </div>
  );
};

EmbedFrame.propTypes = {
  src: PropTypes.string,
  title: PropTypes.string.isRequired,
};

export default EmbedFrame;
