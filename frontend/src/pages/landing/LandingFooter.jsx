import { brandName, useTranslation } from "../../lib/i18n";
import "./landing.css";

// Brand + tagline + footer links. Extracted from the landing page so the same
// footer shells the base-domain public routes (register, find-workspace). The
// caller must place it inside an `id="landing"` element (the Tailwind utilities
// are scoped to `#landing`).
const LandingFooter = () => {
  const content = useTranslation("landing");

  return (
    <footer className="border-t border-gray-200 bg-bg-primary px-4 py-8 dark:border-white/10 dark:bg-bg-dark sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4">
        <span className="font-title text-lg font-bold text-text-primary dark:text-white">
          {brandName()}
        </span>
        <span className="text-sm text-text-muted dark:text-gray-400">
          {content.footer.tagline}
        </span>
        <div className="flex-1" />
        <nav
          aria-label={content.footer.navLabel}
          className="flex gap-6 text-sm"
        >
          {content.footer.links.map((link) => (
            <a
              key={link.label}
              className="text-text-muted hover:text-brand-text dark:text-gray-400"
              href={link.href}
            >
              {link.label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
};

export default LandingFooter;
