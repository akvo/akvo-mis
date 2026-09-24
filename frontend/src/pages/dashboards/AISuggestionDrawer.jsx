import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import PropTypes from "prop-types";
import {
  Drawer,
  Input,
  Button,
  Alert,
  Empty,
  Tag,
  Skeleton,
  message,
} from "antd";
import {
  ThunderboltFilled,
  ReloadOutlined,
  PlusOutlined,
  BulbOutlined,
  CheckOutlined,
  BarChartOutlined,
  PieChartOutlined,
  LineChartOutlined,
  TableOutlined,
  GlobalOutlined,
  DashboardOutlined,
  ClearOutlined,
  AppstoreAddOutlined,
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

const typeIconComponent = {
  kpi: <DashboardOutlined />,
  bar: <BarChartOutlined />,
  line: <LineChartOutlined />,
  pie: <PieChartOutlined />,
  table: <TableOutlined />,
  map: <GlobalOutlined />,
};

const PROMPT_CHIPS = [
  "Status & Functionality",
  "Monthly Trends",
  "Geographic Coverage",
  "Key KPIs",
];

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
    data: null,
    promptHint: "",
  });

  const abortControllerRef = useRef(null);
  const promptHintRef = useRef("");
  promptHintRef.current = promptHint;

  const existingWidgetsRef = useRef(existingWidgets);
  existingWidgetsRef.current = existingWidgets;

  // Derive which suggestions are currently present in existingWidgets
  const addedIndices = useMemo(() => {
    const set = new Set();
    if (!Array.isArray(existingWidgets) || !Array.isArray(suggestions)) {
      return set;
    }
    const usedWidgetIds = new Set();
    suggestions.forEach((sug, idx) => {
      const matchIndex = existingWidgets.findIndex((w, wIdx) => {
        const widgetKey =
          typeof w?.id !== "undefined" && w?.id !== null ? w.id : `idx_${wIdx}`;
        if (usedWidgetIds.has(widgetKey)) {
          return false;
        }
        if (!w || w.type !== sug.type) {
          return false;
        }
        if (typeof sug.question !== "undefined" && sug.question !== null) {
          if (String(w.question) !== String(sug.question)) {
            return false;
          }
        }
        if (typeof sug.form !== "undefined" && sug.form !== null) {
          if (String(w.form) !== String(sug.form)) {
            return false;
          }
        }
        if (sug.title && w.title) {
          if (w.title.trim().toLowerCase() !== sug.title.trim().toLowerCase()) {
            return false;
          }
        }
        return true;
      });

      if (matchIndex !== -1) {
        const matchedWidget = existingWidgets[matchIndex];
        const widgetKey =
          typeof matchedWidget?.id !== "undefined" && matchedWidget?.id !== null
            ? matchedWidget.id
            : `idx_${matchIndex}`;
        usedWidgetIds.add(widgetKey);
        set.add(idx);
      }
    });
    return set;
  }, [existingWidgets, suggestions]);

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

      const existingTypes = (existingWidgetsRef.current || [])
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
          cachedRef.current = {
            dashboardId,
            data: list,
            promptHint: hintToUse || "",
          };
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
    [dashboardId, visible]
  );

  // Auto-load default recommendations when drawer opens, and retain existing suggestions across open/close
  useEffect(() => {
    if (visible && dashboardId) {
      if (cachedRef.current.dashboardId !== dashboardId) {
        cachedRef.current = {
          dashboardId,
          data: null,
          promptHint: "",
        };
        setPromptHint("");
        setSuggestions([]);
        fetchSuggestions("");
        return;
      }

      if (cachedRef.current.data !== null) {
        if (suggestions.length === 0) {
          setSuggestions(cachedRef.current.data);
          setPromptHint(cachedRef.current.promptHint || "");
        }
        return;
      }

      if (suggestions.length === 0) {
        fetchSuggestions("");
      }
    } else if (!visible && abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, [visible, dashboardId, fetchSuggestions, suggestions.length]);

  const handleSearch = useCallback(
    (value) => {
      setPromptHint(value);
      fetchSuggestions(value);
    },
    [fetchSuggestions]
  );

  const handleReset = useCallback(() => {
    setPromptHint("");
    fetchSuggestions("");
  }, [fetchSuggestions]);

  const handleAddWidget = useCallback(
    (sug) => {
      onAddWidget(sug);
      message.success(`Added "${sug.title || "Widget"}" to dashboard`);
    },
    [onAddWidget]
  );

  const handleAddAll = useCallback(() => {
    let count = 0;
    suggestions.forEach((sug, idx) => {
      if (!addedIndices.has(idx)) {
        onAddWidget(sug);
        count += 1;
      }
    });
    if (count > 0) {
      message.success(
        `Added ${count} widget${count > 1 ? "s" : ""} to dashboard`
      );
    }
  }, [addedIndices, onAddWidget, suggestions]);

  const getTypeMeta = useCallback((type) => {
    const meta = WIDGET_TYPES.find((wt) => wt.type === type);
    return meta || { label: type, iconBg: "#f0f1f4" };
  }, []);

  const hasCustomHint = Boolean(
    (promptHint && promptHint.trim()) ||
      (cachedRef.current?.promptHint && cachedRef.current.promptHint.trim())
  );

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
            placeholder="Ask AI for specific widgets (max 250 chars)..."
            allowClear
            enterButton="Suggest"
            maxLength={250}
            value={promptHint}
            onChange={(e) => {
              const val = e.target.value;
              setPromptHint(val);
              if (!val && cachedRef.current.promptHint) {
                handleReset();
              }
            }}
            onSearch={handleSearch}
            loading={loading}
          />
          {promptHint && (
            <div className="ai-suggestion-char-count">
              {promptHint.length} / 250
            </div>
          )}
          <div className="ai-suggestion-chips">
            <span className="ai-suggestion-chips-label">Try:</span>
            {PROMPT_CHIPS.map((chip) => (
              <Tag
                key={chip}
                className="ai-suggestion-chip"
                onClick={() => handleSearch(chip)}
              >
                {chip}
              </Tag>
            ))}
          </div>
          {hasCustomHint && (
            <div className="ai-suggestion-reset-link">
              <Button
                type="link"
                size="small"
                icon={<ClearOutlined />}
                onClick={handleReset}
              >
                Reset to default recommendations
              </Button>
            </div>
          )}
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
          <div className="ai-suggestion-skeleton-list">
            {[1, 2, 3].map((key) => (
              <div
                key={key}
                className="ai-suggestion-card ai-suggestion-skeleton-card"
              >
                <Skeleton
                  active
                  title={{ width: "60%" }}
                  paragraph={{ rows: 2, width: ["90%", "40%"] }}
                />
              </div>
            ))}
          </div>
        ) : suggestions.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No recommendations available. Try clicking Refresh or entering a custom prompt above."
          />
        ) : (
          <div className="ai-suggestion-list">
            {suggestions.length > 1 && (
              <div className="ai-suggestion-list-header">
                <span className="ai-suggestion-count">
                  {suggestions.length} Suggested Widgets
                </span>
                <Button
                  size="small"
                  type="link"
                  icon={<AppstoreAddOutlined />}
                  onClick={handleAddAll}
                  disabled={addedIndices.size === suggestions.length}
                >
                  {addedIndices.size === suggestions.length
                    ? "All Added"
                    : `Add All (${suggestions.length - addedIndices.size})`}
                </Button>
              </div>
            )}
            {suggestions.map((sug, idx) => {
              const meta = getTypeMeta(sug.type);
              const qMeta = questionMap[`${sug.form}_${sug.question}`];
              const isAdded = addedIndices.has(idx);

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
                      {typeIconComponent[sug.type] || null}
                      <span>{typeIconMap[sug.type] || sug.type}</span>
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
                      type={isAdded ? "default" : "primary"}
                      size="small"
                      disabled={isAdded}
                      icon={
                        isAdded ? (
                          <CheckOutlined style={{ color: "#52c41a" }} />
                        ) : (
                          <PlusOutlined />
                        )
                      }
                      onClick={() => handleAddWidget(sug)}
                    >
                      {isAdded ? "Added" : "Add to Dashboard"}
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
