import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { Switch } from "antd";
import { store, uiText } from "../../lib";

// =========================================================
// The public/private control (VIZ-018 D-2a)
// =========================================================
// Lifted out of BuilderInspector so the embedded-dashboard editor,
// which renders no inspector, shows the same control rather than a
// second copy of it. Two copies of a control whose whole purpose is to
// be unambiguous about whether something is on the public internet
// would drift.
//
// It writes immediately rather than joining the dirty state the Save
// button flushes — without that distinction an author would reasonably
// expect Cancel to undo it.
const DashboardVisibilityToggle = ({ isPublic, isPublished, onChange }) => {
  const { language } = store.useState((s) => s);
  const text = useMemo(() => uiText[language.active], [language.active]);

  return (
    <div
      className={`builder-inspector-visibility${
        isPublic ? " builder-inspector-visibility--live" : ""
      }`}
    >
      <div className="builder-inspector-visibility-top">
        <span className="builder-inspector-visibility-title">
          {text.dashboardVisibilityTitle}
        </span>
        <Switch
          size="small"
          role="switch"
          aria-label={text.dashboardVisibilityTitle}
          checked={isPublic}
          disabled={!isPublished}
          onChange={(checked) => {
            onChange(checked);
          }}
        />
      </div>
      <div className="builder-inspector-hint">
        {isPublished
          ? text.dashboardVisibilityHintOn
          : text.dashboardVisibilityHintDraft}
      </div>
    </div>
  );
};

DashboardVisibilityToggle.propTypes = {
  isPublic: PropTypes.bool,
  isPublished: PropTypes.bool,
  onChange: PropTypes.func.isRequired,
};

export default DashboardVisibilityToggle;
