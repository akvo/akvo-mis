import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { store } from "../../lib";
import {
  getLandingContent,
  LANDING_LANGS,
  resolveLang,
  brandName,
} from "./content";
import HeroShowcase from "./HeroShowcase";
import HeroDotField from "./HeroDotField";
import Reveal from "./Reveal";
import ScrollRevealText from "./ScrollRevealText";
import "./landing.css";

const ICON_PATHS = {
  offline:
    "M7 4h10a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Zm3 14h4",
  hierarchy: "M12 3v4m0 0-5 3m5-3 5 3M4 14h4m8 0h4M6 19v-5m12 5v-5M10 19v-5",
  ai: "M4 20V5m0 15h16M7 16l3.5-4 3 2.5L20 7.5",
  free: "M12 3.5l2.3 4.7 5.2.8-3.8 3.7.9 5.2-4.6-2.4-4.6 2.4.9-5.2L4.5 9l5.2-.8L12 3.5Z",
};

const renderIcon = (key) => (
  <svg
    viewBox="0 0 24 24"
    width="22"
    height="22"
    fill="none"
    aria-hidden="true"
  >
    <path
      d={ICON_PATHS[key] || ICON_PATHS.free}
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const CTA_CLASS = {
  primary:
    "inline-flex items-center justify-center gap-2 border border-akvo bg-akvo px-5 py-3 text-base font-semibold text-white transition-colors hover:border-akvo-dark hover:bg-akvo-dark",
  outline:
    "inline-flex items-center justify-center gap-2 border border-akvo-border bg-white/60 px-5 py-3 text-base font-semibold text-akvo-text transition-colors hover:bg-akvo-light dark:bg-transparent dark:text-akvo-bright",
  onDark:
    "inline-flex items-center justify-center gap-2 border border-white/60 bg-transparent px-5 py-3 text-base font-semibold text-white transition-colors hover:bg-white/10",
};

const renderCta = (cta, variant) => {
  if (!cta || !cta.href) {
    return null;
  }
  const className = CTA_CLASS[variant] || CTA_CLASS.primary;
  if (cta.href.startsWith("/")) {
    return (
      <Link to={cta.href} className={className}>
        {cta.label}
      </Link>
    );
  }
  return (
    <a className={className} href={cta.href}>
      {cta.label}
    </a>
  );
};

const useDocumentMeta = (title, description) => {
  useEffect(() => {
    if (title) {
      document.title = title;
    }
    if (description) {
      let tag = document.querySelector('meta[name="description"]');
      if (!tag) {
        tag = document.createElement("meta");
        tag.setAttribute("name", "description");
        document.head.appendChild(tag);
      }
      tag.setAttribute("content", description);
    }
  }, [title, description]);
};

const Landing = () => {
  const active = store.useState((s) => s.language.active);
  const lang = resolveLang(active);
  const content = getLandingContent(lang);
  const [menuOpen, setMenuOpen] = useState(false);
  useDocumentMeta(content.site.title, content.site.description);

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
      <div className="font-sans text-text-secondary antialiased dark:bg-bg-dark dark:text-gray-300">
        <header className="sticky top-0 z-30 border-b border-akvo-border/30 bg-white/90 backdrop-blur-sm dark:bg-bg-dark/90">
          <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-4 sm:px-6 lg:px-8">
            <span className="font-title text-xl font-bold text-text-primary dark:text-white">
              {brandName()}
            </span>
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
            <Link
              to="/register"
              className="hidden border border-akvo bg-akvo px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-akvo-dark sm:inline-flex"
            >
              {content.nav.cta}
            </Link>
          </div>
        </header>

        {/* Hero */}
        <section className="relative overflow-hidden bg-akvo-deep px-4 pb-16 pt-20 sm:px-6 md:pb-24 md:pt-28 lg:px-8">
          <HeroDotField />
          <div className="relative z-10 mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-2">
            <div>
              <span className="mb-4 inline-block rounded-full bg-akvo px-4 py-1.5 text-sm font-semibold text-white">
                {content.hero.badge}
              </span>
              <h1 className="font-title text-[32px] font-normal leading-[40px] tracking-[-0.4px] text-white sm:text-[40px] sm:leading-[48px] md:text-[60px] md:leading-[72px] md:tracking-[-1.2px]">
                {content.hero.title}
              </h1>
              <p className="mt-4 max-w-2xl text-base font-semibold leading-6 text-[#D4E2F7] md:text-xl md:leading-7">
                {content.hero.lead}
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                {renderCta(content.hero.primaryCta, "primary")}
                {renderCta(content.hero.secondaryCta, "onDark")}
              </div>
            </div>
            {content.hero.demo ? (
              <HeroShowcase demo={content.hero.demo} />
            ) : null}
          </div>
        </section>

        {/* Free band */}
        <section className="bg-akvo px-4 py-10 text-white sm:px-6 lg:px-8">
          <Reveal className="mx-auto max-w-7xl">
            <h2 className="font-title text-[26px] font-normal leading-tight text-white md:text-[34px]">
              {content.freeBand.title}
            </h2>
            <p className="mt-2 max-w-3xl text-base leading-relaxed text-white/90">
              {content.freeBand.body}
            </p>
          </Reveal>
        </section>

        {/* How it works */}
        <section className="bg-bg-primary px-4 py-16 dark:bg-bg-dark md:py-24 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <ScrollRevealText
              as="h2"
              text={content.howItWorks.heading}
              className="font-title text-[28px] font-normal leading-[34px] tracking-[-0.4px] text-akvo-text dark:text-akvo-bright md:text-[40px] md:leading-[48px]"
            />
            <p className="mt-2 max-w-2xl text-lg text-text-muted dark:text-gray-400">
              {content.howItWorks.subtitle}
            </p>
            <ol className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
              {content.howItWorks.steps.map((step, i) => (
                <Reveal
                  as="li"
                  key={step.title}
                  delay={i * 0.08}
                  className="rounded-xl border border-akvo-border/40 bg-bg-secondary p-6 dark:border-white/10 dark:bg-white/5"
                >
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-akvo font-title text-base text-white">
                    {i + 1}
                  </span>
                  <h3 className="mt-4 text-xl font-bold text-text-primary dark:text-white">
                    {step.title}
                  </h3>
                  <p className="mt-2 text-base leading-relaxed text-text-muted dark:text-gray-400">
                    {step.body}
                  </p>
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        {/* Why */}
        <section className="bg-bg-secondary px-4 py-16 dark:bg-white/5 md:py-24 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <ScrollRevealText
              as="h2"
              text={content.why.heading}
              className="font-title text-[28px] font-normal leading-[34px] tracking-[-0.4px] text-akvo-text dark:text-akvo-bright md:text-[40px] md:leading-[48px]"
            />
            <p className="mt-2 max-w-2xl text-lg text-text-muted dark:text-gray-400">
              {content.why.subtitle}
            </p>
            <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
              {content.why.cards.map((card, i) => (
                <Reveal
                  key={card.title}
                  delay={i * 0.08}
                  className="rounded-xl border border-akvo-border/40 bg-white p-8 dark:border-white/10 dark:bg-bg-dark"
                >
                  <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-akvo-light text-akvo-text">
                    {renderIcon(card.icon)}
                  </div>
                  <h3 className="text-xl font-bold text-text-primary dark:text-white">
                    {card.title}
                  </h3>
                  <p className="mt-3 text-base leading-relaxed text-text-muted dark:text-gray-400">
                    {card.body}
                  </p>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* Benchmark */}
        <section className="bg-bg-primary px-4 py-16 dark:bg-bg-dark md:py-24 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <ScrollRevealText
              as="h2"
              text={content.benchmark.heading}
              className="font-title text-[28px] font-normal leading-[34px] tracking-[-0.4px] text-akvo-text dark:text-akvo-bright md:text-[40px] md:leading-[48px]"
            />
            <p className="mt-2 max-w-2xl text-lg text-text-muted dark:text-gray-400">
              {content.benchmark.subtitle}
            </p>
            <Reveal className="mt-8 w-0 min-w-full overflow-x-auto rounded-xl border border-gray-200 dark:border-white/10">
              <table className="w-full min-w-[640px] text-left text-[15px]">
                <thead className="bg-bg-secondary text-text-primary dark:bg-white/5 dark:text-white">
                  <tr>
                    {content.benchmark.columns.map((col) => (
                      <th
                        key={col.key}
                        scope="col"
                        className={
                          col.highlight
                            ? "border-x-2 border-akvo-border bg-akvo-light px-4 py-3 font-semibold text-akvo-text"
                            : "px-4 py-3 font-semibold"
                        }
                      >
                        {col.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-white/10">
                  {content.benchmark.rows.map((row) => (
                    <tr key={row.capability}>
                      <th
                        scope="row"
                        className="px-4 py-3 font-semibold text-text-primary dark:text-white"
                      >
                        {row.capability}
                      </th>
                      <td className="px-4 py-3">{row.kobo}</td>
                      <td className="border-x-2 border-akvo-border bg-akvo-light px-4 py-3 font-semibold text-text-primary">
                        {row.akvo}
                      </td>
                      <td className="px-4 py-3">{row.dhis2}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Reveal>
            <p className="mt-4 max-w-3xl text-sm text-text-muted dark:text-gray-400">
              {content.benchmark.caption}
            </p>
          </div>
        </section>

        {/* Partner + final CTA */}
        <section className="bg-bg-secondary px-4 py-16 dark:bg-white/5 md:py-24 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <Reveal className="relative overflow-hidden rounded-2xl bg-akvo-deep px-6 py-12 text-center text-white md:px-16 md:py-20">
              <h2 className="font-title text-[28px] font-normal leading-[34px] tracking-[-0.4px] text-white md:text-[40px] md:leading-[48px]">
                {content.partner.title}
              </h2>
              <p className="mx-auto mt-3 max-w-2xl text-lg leading-relaxed text-white/90">
                {content.partner.body}
              </p>
              <div className="mt-8 flex justify-center">
                {renderCta(content.partner.cta, "onDark")}
              </div>
            </Reveal>
            <Reveal className="mt-16 text-center">
              <h2 className="font-title text-[30px] font-normal leading-tight text-text-primary dark:text-white md:text-[44px]">
                {content.finalCta.title}
              </h2>
              <p className="mt-3 text-lg text-text-muted dark:text-gray-400">
                {content.finalCta.body}
              </p>
              <div className="mt-8 flex justify-center">
                {renderCta(content.finalCta.cta, "primary")}
              </div>
            </Reveal>
          </div>
        </section>

        {/* Footer */}
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

export default Landing;
