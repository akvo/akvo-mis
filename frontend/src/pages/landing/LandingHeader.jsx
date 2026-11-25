import { useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { Link } from "react-router-dom";
import { store } from "../../lib";
import { LANGS, resolveLang, brandName, getContent } from "../../lib/i18n";
import "./landing.css";

// The brand + EN/ES/FR language switch + a CTA. Extracted from the landing
// page so the same 70px fixed bar shells every base-domain public route
// (landing, register, find-workspace). The caller must place it inside an
// `id="landing"` element (the Tailwind utilities are scoped to `#landing`).
//
// - `showCta`: whether to show the right-hand button (default true).
// - `cta`: `{ label, href }` to override the landing's own "try it yourself"
//   CTA.
// - `showLogin`: whether to show a "Log in" button beside the language switch
//   (default false). On the base domain there is no single login form, so it
//   goes to `/find-workspace` (the lookup that forwards to a workspace's host).
const LandingHeader = ({ showCta, cta, showLogin }) => {
  const active = store.useState((s) => s.language.active);
  const lang = resolveLang(active);
  const content = getContent("landing", active);
  const [menuOpen, setMenuOpen] = useState(false);
  const triggerRef = useRef(null);

  // akvo-web-style scroll progress: a primary-colour bar along the header's
  // bottom edge that fills as the page scrolls. The app scrolls `document.body`
  // (not the viewport), so a capture-phase listener reads whichever element
  // actually scrolled rather than relying on `window.scrollY`.
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const max = document.body.scrollHeight - window.innerHeight;
      const top =
        window.scrollY ||
        document.body.scrollTop ||
        document.documentElement.scrollTop ||
        0;
      setProgress(max > 0 ? Math.min(top / max, 1) : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, {
      passive: true,
      capture: true,
    });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll, { capture: true });
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  const chooseLang = (code) => {
    store.update((s) => {
      s.language.active = code;
    });
    setMenuOpen(false);
  };

  const closeMenu = () => {
    setMenuOpen(false);
    if (triggerRef.current) {
      triggerRef.current.focus();
    }
  };

  const currentLabel = (LANGS.find((l) => l.code === lang) || LANGS[0]).label;

  const ctaToShow = showCta
    ? cta || { label: content.nav.cta, href: "/" }
    : null;

  return (
    <header className="fixed inset-x-0 top-0 z-[999] border-b border-brand-border/30 bg-white/90 backdrop-blur-sm dark:bg-bg-dark/90">
      <div className="mx-auto flex h-[70px] max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" aria-label={brandName()} className="flex items-center">
          <img
            src="/logo.svg"
            alt={brandName()}
            className="h-8 w-auto dark:invert"
          />
        </Link>
        <div className="flex-1" />
        <div
          className="relative"
          onKeyDown={(e) => {
            if (e.key === "Escape" && menuOpen) {
              closeMenu();
            }
          }}
        >
          <button
            ref={triggerRef}
            type="button"
            aria-haspopup="true"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 border border-brand-border px-3 py-2 text-sm font-semibold text-brand-text dark:text-brand-bright"
          >
            {currentLabel}
            <span aria-hidden="true">▾</span>
          </button>
          {menuOpen ? (
            <>
              <button
                type="button"
                aria-label={content.nav.closeMenu}
                className="fixed inset-0 z-10 cursor-default"
                onClick={() => setMenuOpen(false)}
              />
              <ul className="absolute right-0 z-20 mt-1 min-w-[150px] border border-brand-border bg-white py-1 shadow-lg dark:bg-bg-dark">
                {LANGS.map((l) => (
                  <li key={l.code}>
                    <button
                      type="button"
                      aria-current={l.code === lang}
                      onClick={() => chooseLang(l.code)}
                      className="flex w-full items-center justify-between px-4 py-2 text-left text-sm text-text-secondary hover:bg-brand-light hover:text-brand-text dark:text-gray-300"
                    >
                      <span
                        className={
                          l.code === lang
                            ? "font-semibold text-brand-text dark:text-brand-bright"
                            : ""
                        }
                      >
                        {l.label}
                      </span>
                      {l.code === lang ? (
                        <span className="text-brand-text dark:text-brand-bright">
                          ✓
                        </span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
        {showLogin ? (
          <Link
            to="/find-workspace"
            className="inline-flex border border-brand bg-brand px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-dark"
          >
            {content.nav.login}
          </Link>
        ) : null}
        {ctaToShow ? (
          <Link
            to={ctaToShow.href}
            className="hidden border border-brand bg-brand px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-dark sm:inline-flex"
          >
            {ctaToShow.label}
          </Link>
        ) : null}
      </div>
      <div
        aria-hidden="true"
        className="absolute bottom-0 left-0 h-[3px] w-full origin-left bg-brand transition-transform duration-75 ease-out"
        style={{ transform: `scaleX(${progress})` }}
      />
    </header>
  );
};

LandingHeader.propTypes = {
  showCta: PropTypes.bool,
  cta: PropTypes.shape({
    label: PropTypes.string.isRequired,
    href: PropTypes.string.isRequired,
  }),
  showLogin: PropTypes.bool,
};

LandingHeader.defaultProps = {
  showCta: true,
  showLogin: false,
};

export default LandingHeader;
