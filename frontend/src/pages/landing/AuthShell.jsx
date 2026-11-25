import PropTypes from "prop-types";
import HeroDotField from "./HeroDotField";
import "./landing.css";

// Shared backdrop for the public auth pages — login, reset password, workspace
// finder, email activation and workspace-not-found — so they match the
// onboarding wizard: the same deep-indigo field with the autonomous dot grid,
// and no footer. The background is defined ONLY here, so a future change is one
// edit.
//
// Only the backdrop sits inside `#landing` (it needs the scoped brand-* Tailwind
// for `bg-brand-deep`, and holds the dot canvas); it is positioned as an
// absolute layer. The page's card renders in `children` OUTSIDE `#landing`, so
// the `#landing` reset (which neutralises <button> and strips borders) never
// reaches the antd form. The `.auth-shell*` layout + the `#login` override live
// in pages/login/style.scss, where the app's variables and `.body` are in scope.
const AuthShell = ({ children }) => (
  <div className="auth-shell">
    <div id="landing" className="auth-shell-bg" aria-hidden="true">
      {/* bg-brand-deep must be on a DESCENDANT of #landing: the scoped Tailwind
          selector is `#landing .bg-brand-deep`, which the #landing element
          itself does not match. */}
      <div className="relative h-full overflow-hidden bg-brand-deep">
        <HeroDotField interactive={false} />
      </div>
    </div>
    <div className="auth-shell-content">{children}</div>
  </div>
);

AuthShell.propTypes = {
  children: PropTypes.node,
};

export default AuthShell;
