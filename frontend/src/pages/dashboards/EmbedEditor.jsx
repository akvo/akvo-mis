import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { Form, Input } from "antd";
import { store, uiText } from "../../lib";
import DashboardVisibilityToggle from "./DashboardVisibilityToggle";

// =========================================================
// The embedded dashboard's editor (VIZ-019)
// =========================================================
// An embed has no widgets, so there is no palette, canvas or inspector
// to render — only the handful of settings that make up the dashboard.
const EmbedEditor = ({
  name,
  description,
  snippet,
  isPublic,
  isPublished,
  onDashboardChange,
  onVisibilityChange,
}) => {
  const { language } = store.useState((s) => s);
  const text = useMemo(() => uiText[language.active], [language.active]);

  return (
    <div className="builder-embed-editor">
      <div className="builder-embed-editor-inner">
        <Form layout="vertical">
          <Form.Item label={text.dashboardNameLabel}>
            <Input
              value={name || ""}
              onChange={(e) => onDashboardChange("name", e.target.value)}
            />
          </Form.Item>
          <Form.Item label="Description">
            <Input.TextArea
              rows={2}
              value={description || ""}
              onChange={(e) => onDashboardChange("description", e.target.value)}
            />
          </Form.Item>
          <Form.Item
            label={text.dashboardEmbedLabel}
            extra={text.dashboardEmbedHint}
          >
            <Input.TextArea
              rows={8}
              value={snippet || ""}
              placeholder={text.dashboardEmbedPlaceholder}
              onChange={(e) =>
                onDashboardChange("embed_snippet", e.target.value)
              }
            />
          </Form.Item>
        </Form>
        <DashboardVisibilityToggle
          isPublic={isPublic}
          isPublished={isPublished}
          onChange={onVisibilityChange}
        />
      </div>
    </div>
  );
};

EmbedEditor.propTypes = {
  name: PropTypes.string,
  description: PropTypes.string,
  snippet: PropTypes.string,
  isPublic: PropTypes.bool,
  isPublished: PropTypes.bool,
  onDashboardChange: PropTypes.func.isRequired,
  onVisibilityChange: PropTypes.func.isRequired,
};

export default EmbedEditor;
