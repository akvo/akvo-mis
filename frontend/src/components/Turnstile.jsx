import { useEffect, useRef } from "react";
import PropTypes from "prop-types";

// Cloudflare Turnstile widget. Renders nothing when no site key is configured
// (the default on most deployments — no captcha at all), so callers can always
// include it and read the token from `onToken`.
const SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js";

const Turnstile = ({ siteKey, onToken, resetSignal }) => {
  const boxRef = useRef(null);
  const idRef = useRef(null);

  // Reset the solved widget when the parent bumps `resetSignal` (e.g. after a
  // failed registration whose single-use token was cleared), so a retry issues
  // a fresh challenge instead of re-sending an empty token. 0 = initial, never
  // resets on mount.
  useEffect(() => {
    if (resetSignal && window.turnstile && idRef.current !== null) {
      window.turnstile.reset(idRef.current);
      onToken("");
    }
  }, [resetSignal, onToken]);

  useEffect(() => {
    if (!siteKey) {
      return () => {};
    }
    let cancelled = false;
    const render = () => {
      if (
        cancelled ||
        !boxRef.current ||
        idRef.current !== null ||
        !window.turnstile
      ) {
        return;
      }
      idRef.current = window.turnstile.render(boxRef.current, {
        sitekey: siteKey,
        callback: (value) => onToken(value),
        "expired-callback": () => onToken(""),
        "error-callback": () => onToken(""),
      });
    };
    if (window.turnstile) {
      render();
    } else {
      const script = document.createElement("script");
      script.src = SRC;
      script.async = true;
      script.onload = render;
      document.head.appendChild(script);
    }
    return () => {
      cancelled = true;
    };
  }, [siteKey, onToken]);

  if (!siteKey) {
    return null;
  }
  return <div ref={boxRef} className="mt-4" />;
};

Turnstile.propTypes = {
  siteKey: PropTypes.string,
  onToken: PropTypes.func.isRequired,
  resetSignal: PropTypes.number,
};

Turnstile.defaultProps = {
  resetSignal: 0,
};

export default Turnstile;
