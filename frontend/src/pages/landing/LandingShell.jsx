import { useState } from "react";
import { Link } from "react-router-dom";
import PropTypes from "prop-types";
import { store } from "../../lib";
import {
  getLandingContent,
  LANDING_LANGS,
  resolveLang,
  brandName,
} from "./content";
import "./landing.css";

// Shared public shell for the landing surface (LP-002 D-5): the scoped #landing
// wrapper, the sticky header (brand + language switch + optional CTA) and the
// footer. Both the landing page and the /onboarding wizard render inside it so
// they feel like one continuous public surface. `showCta` hides the header CTA
// on pages that are already the CTA target (the wizard).
const LandingShell = ({ children, showCta = true }) => {
  const active = store.useState((s) => s.language.active);
  const lang = resolveLang(active);
  const content = getLandingContent(lang);
  const [menuOpen, setMenuOpen] = useState(false);

  const chooseLang = (code) => {
    store.update((s) => {
      s.language.active = code;
    });
    setMenuOpen(false);
  };

  const currentLabel = (
    LANDING_LANGS.find((l) => l.code === lang) || LANDING_LANGS[0]
  ).label;

  return (
    <div id="landing">
      <div className="flex min-h-screen flex-col font-sans text-text-secondary antialiased dark:bg-bg-dark dark:text-gray-300">
        <header className="sticky top-0 z-30 border-b border-akvo-border/30 bg-white/90 backdrop-blur-sm dark:bg-bg-dark/90">
          <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-4 sm:px-6 lg:px-8">
            <Link
              to="/"
              className="font-title text-xl font-bold text-text-primary dark:text-white"
            >
              {brandName()}
            </Link>
            <div className="flex-1" />
            <div className="relative">
              <button
                type="button"
                aria-haspopup="listbox"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((v) => !v)}
                className="flex items-center gap-2 border border-akvo-border px-3 py-2 text-sm font-semibold text-akvo-text dark:text-akvo-bright"
              >
                {currentLabel}
                <span aria-hidden="true">▾</span>
              </button>
              {menuOpen ? (
                <>
                  <button
                    type="button"
                    aria-label="Close language menu"
                    className="fixed inset-0 z-10 cursor-default"
                    onClick={() => setMenuOpen(false)}
                  />
                  <ul
                    role="listbox"
                    className="absolute right-0 z-20 mt-1 min-w-[150px] border border-akvo-border bg-white py-1 shadow-lg dark:bg-bg-dark"
                  >
                    {LANDING_LANGS.map((l) => (
                      <li key={l.code}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={l.code === lang}
                          onClick={() => chooseLang(l.code)}
                          className="flex w-full items-center justify-between px-4 py-2 text-left text-sm text-text-secondary hover:bg-akvo-light hover:text-akvo-text dark:text-gray-300"
                        >
                          <span
                            className={
                              l.code === lang
                                ? "font-semibold text-akvo-text dark:text-akvo-bright"
                                : ""
                            }
                          >
                            {l.label}
                          </span>
                          {l.code === lang ? (
                            <span className="text-akvo-text dark:text-akvo-bright">
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
            {showCta ? (
              <Link
                to="/onboarding"
                className="hidden border border-akvo bg-akvo px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-akvo-dark sm:inline-flex"
              >
                {content.nav.cta}
              </Link>
            ) : null}
          </div>
        </header>

        <main className="flex flex-1 flex-col">{children}</main>

        <footer className="border-t border-gray-200 bg-bg-primary px-4 py-8 dark:border-white/10 dark:bg-bg-dark sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4">
            <span className="font-title text-lg font-bold text-text-primary dark:text-white">
              {brandName()}
            </span>
            <span className="text-sm text-text-muted dark:text-gray-400">
              {content.footer.tagline}
            </span>
            <div className="flex-1" />
            <nav className="flex gap-6 text-sm">
              {content.footer.links.map((link) => (
                <a
                  key={link.label}
                  className="text-text-muted hover:text-akvo-text dark:text-gray-400"
                  href={link.href}
                >
                  {link.label}
                </a>
              ))}
            </nav>
          </div>
        </footer>
      </div>
    </div>
  );
};

LandingShell.propTypes = {
  children: PropTypes.node,
  showCta: PropTypes.bool,
};

export default LandingShell;
