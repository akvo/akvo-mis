import PropTypes from "prop-types";
import LandingHeader from "./LandingHeader";
import LandingFooter from "./LandingFooter";
import "./landing.css";

// Shared public shell for the landing surface (LP-002 D-5): the scoped #landing
// wrapper plus the landing's fixed header (brand + language switch + optional
// CTA) and footer, so the /onboarding wizard feels like one continuous public
// surface with the landing. Composes LandingHeader/LandingFooter rather than
// duplicating them. `showCta` hides the header CTA on pages that are already the
// CTA target (the wizard). The main pads for the 70px fixed header.
const LandingShell = ({ children, showCta = true, showLogin = false }) => (
  <div id="landing">
    <div className="flex min-h-screen flex-col font-sans text-text-secondary antialiased dark:bg-bg-dark dark:text-gray-300">
      <LandingHeader showCta={showCta} showLogin={showLogin} />
      <main className="flex flex-1 flex-col pt-[70px]">{children}</main>
      <LandingFooter />
    </div>
  </div>
);

LandingShell.propTypes = {
  children: PropTypes.node,
  showCta: PropTypes.bool,
  showLogin: PropTypes.bool,
};

export default LandingShell;
