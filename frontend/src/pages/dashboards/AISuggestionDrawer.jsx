import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import PropTypes from "prop-types";
import { Drawer, Input, Button, Spin, Alert, Empty, Tag } from "antd";
import {
  ThunderboltFilled,
  ReloadOutlined,
  PlusOutlined,
  BulbOutlined,
} from "@ant-design/icons";
import dashboardAi from "../../util/dashboardAi";
import { WIDGET_TYPES } from "./builderConstants";

const typeIconMap = {
  kpi: "KPI",
  bar: "Bar",
  line: "Line",
  pie: "Pie",
  scatter: "Scatter",
  table: "Table",
  map: "Map",
  section_title: "Title",
};

const AISuggestionDrawer = ({
  visible,
  onClose,
  dashboardId,
  existingWidgets,
  sources,
  onAddWidget,
}) => {
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [error, setError] = useState(null);
  const [promptHint, setPromptHint] = useState("");

  const cachedRef = useRef({
    dashboardId: null,
    widgetsLength: 0,
    data: null,
  });

  const abortControllerRef = useRef(null);
  const promptHintRef = useRef("");
  promptHintRef.current = promptHint;

  // Helper map for question and form labels
  const questionMap = useMemo(() => {
    const map = {};
    if (sources?.forms && Array.isArray(sources.forms)) {
      sources.forms.forEach((form) => {
        if (form.questions && Array.isArray(form.questions)) {
          form.questions.forEach((q) => {
            map[`${form.id}_${q.id}`] = {
              formName: form.name,
              questionLabel: q.label,
            };
          });
        }
      });
    }
    return map;
  }, [sources]);

  const fetchSuggestions = useCallback(
    (customHint = null) => {
      if (!dashboardId || !visible) {
        return;
      }

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setLoading(true);
      setError(null);

      const existingTypes = (existingWidgets || [])
        .map((w) => w.type)
        .filter(Boolean);

      const payload = {
        existing_widget_types: existingTypes,
      };

      const hintToUse =
        customHint !== null ? customHint : promptHintRef.current;
      const trimmedHint = (hintToUse || "").trim();
      if (trimmedHint) {
        payload.prompt_hint = trimmedHint;
      }

      dashboardAi
        .suggestWidgets(dashboardId, payload, controller.signal)
        .then((res) => {
          const list = Array.isArray(res?.data?.suggestions)
            ? res.data.suggestions
            : [];
          setSuggestions(list);
          if (!trimmedHint) {
            cachedRef.current = {
              dashboardId,
              widgetsLength: existingWidgets?.length || 0,
              data: list,
            };
          }
        })
        .catch((err) => {
          if (err?.name === "CanceledError" || err?.name === "AbortError") {
            return;
          }
          setError(
            err?.response?.data?.message ||
              "Failed to load AI suggestions. Please try again or refine your prompt."
          );
        })
        .finally(() => {
          setLoading(false);
        });
    },
    [dashboardId, visible, existingWidgets]
  );

  // Auto-load default recommendations when drawer opens, without re-triggering on promptHint changes
  useEffect(() => {
    if (visible && dashboardId) {
      const isCached =
        cachedRef.current.dashboardId === dashboardId &&
        cachedRef.current.widgetsLength === (existingWidgets?.length || 0) &&
        cachedRef.current.data !== null;

      if (isCached) {
        setSuggestions(cachedRef.current.data);
      } else {
        fetchSuggestions("");
      }
    } else if (!visible && abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, [visible, dashboardId, existingWidgets?.length, fetchSuggestions]);

  const handleSearch = useCallback(
    (value) => {
      setPromptHint(value);
      fetchSuggestions(value);
    },
    [fetchSuggestions]
  );

  const getTypeMeta = useCallback((type) => {
    const meta = WIDGET_TYPES.find((wt) => wt.type === type);
    return meta || { label: type, iconBg: "#f0f1f4" };
  }, []);

  return (
    <Drawer
      title={
        <div className="ai-suggestion-drawer-header">
          <div className="ai-suggestion-drawer-title">
            <ThunderboltFilled style={{ color: "#1890ff", marginRight: 8 }} />
            AI Widget Recommendations
          </div>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => fetchSuggestions(promptHint)}
            loading={loading}
          >
            Refresh
          </Button>
        </div>
      }
      placement="right"
      width={460}
      open={visible}
      onClose={onClose}
      className="ai-suggestion-drawer"
    >
      <div className="ai-suggestion-drawer-body">
        <div className="ai-suggestion-search-box">
          <Input.Search
            placeholder="Ask AI for specific widgets (e.g. 'Focus on population')..."
            allowClear
            enterButton="Suggest"
            value={promptHint}
            onChange={(e) => setPromptHint(e.target.value)}
            onSearch={handleSearch}
            loading={loading}
          />
        </div>

        {error && (
          <Alert
            type="warning"
            showIcon
            message={error}
            style={{ marginBottom: 16 }}
            closable
            onClose={() => setError(null)}
          />
        )}

        {loading ? (
          <div className="ai-suggestion-loading">
            <Spin tip="Generating intelligent recommendations..." />
          </div>
        ) : suggestions.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No recommendations available. Try clicking Refresh or entering a custom prompt above."
          />
        ) : (
          <div className="ai-suggestion-list">
            {suggestions.map((sug, idx) => {
              const meta = getTypeMeta(sug.type);
              const qMeta = questionMap[`${sug.form}_${sug.question}`];

              return (
                <div
                  key={`${sug.type}_${sug.question || idx}_${idx}`}
                  className="ai-suggestion-card"
                >
                  <div className="ai-suggestion-card-header">
                    <span
                      className="ai-suggestion-type-badge"
                      style={{ background: meta.iconBg }}
                    >
                      {typeIconMap[sug.type] || sug.type}
                    </span>
                    <span className="ai-suggestion-title">
                      {sug.title || meta.label}
                    </span>
                    <Tag className="ai-suggestion-col-tag">
                      {sug.col_span ? `${sug.col_span}/24 col` : "Auto width"}
                    </Tag>
                  </div>

                  {qMeta && (
                    <div className="ai-suggestion-source">
                      <span className="ai-suggestion-source-form">
                        {qMeta.formName}
                      </span>
                      <span className="ai-suggestion-source-separator">•</span>
                      <span className="ai-suggestion-source-question">
                        {qMeta.questionLabel}
                      </span>
                    </div>
                  )}

                  {sug.rationale && (
                    <div className="ai-suggestion-rationale">
                      <BulbOutlined className="ai-suggestion-rationale-icon" />
                      <span>{sug.rationale}</span>
                    </div>
                  )}

                  <div className="ai-suggestion-card-footer">
                    <Button
                      type="primary"
                      size="small"
                      icon={<PlusOutlined />}
                      onClick={() => onAddWidget(sug)}
                    >
                      Add to Dashboard
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Drawer>
  );
};

AISuggestionDrawer.propTypes = {
  visible: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  dashboardId: PropTypes.number,
  existingWidgets: PropTypes.array,
  sources: PropTypes.object,
  onAddWidget: PropTypes.func.isRequired,
};

export default AISuggestionDrawer;
