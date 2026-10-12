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
  const [aiAvailable, setAiAvailable] = useState(true);

  const cachedRef = useRef({
    dashboardId: null,
    data: null,
    promptHint: "",
    aiAvailable: true,
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

  // Derive smart, schema-aware suggestion chips from available form family
  const dynamicPromptChips = useMemo(() => {
    if (
      !sources?.forms ||
      !Array.isArray(sources.forms) ||
      sources.forms.length === 0
    ) {
      return PROMPT_CHIPS;
    }

    const chips = [];
    const allQuestions = [];
    let hasGeo = false;
    let hasDate = false;
    let numericCount = 0;
    let hasMonitoring = false;

    sources.forms.forEach((form, fIdx) => {
      if (fIdx > 0 || form.type === "monitoring") {
        hasMonitoring = true;
      }
      if (form.questions && Array.isArray(form.questions)) {
        form.questions.forEach((q) => {
          allQuestions.push(q);
          const qType = String(q.type || "").toLowerCase();
          const qTypeName = String(q.type_name || "").toLowerCase();
          if (qType === "geo" || qType === "5" || qTypeName === "geo") {
            hasGeo = true;
          }
          if (qType === "date" || qType === "9" || qTypeName === "date") {
            hasDate = true;
          }
          if (
            qType === "number" ||
            qType === "autofield" ||
            qType === "3" ||
            qTypeName === "number" ||
            qTypeName === "autofield"
          ) {
            numericCount += 1;
          }
        });
      }
    });

    // 1. Option Question Breakdown
    const optionQuestions = allQuestions.filter((q) => {
      const qType = String(q.type || "").toLowerCase();
      const qTypeName = String(q.type_name || "").toLowerCase();
      return (
        qType === "option" ||
        qType === "single_select" ||
        qType === "1" ||
        qTypeName === "option" ||
        qTypeName === "single_select"
      );
    });

    if (optionQuestions.length > 0) {
      const firstOpt = optionQuestions[0];
      const optLabel = (firstOpt.label || firstOpt.name || "Status").trim();
      const shortLabel =
        optLabel.length > 20 ? `${optLabel.slice(0, 18)}...` : optLabel;
      chips.push(`${shortLabel} Breakdown`);
    }

    // 2. Temporal Trends
    if (hasDate || hasMonitoring) {
      chips.push("Monthly Trends");
    }

    // 3. Geographic Map
    if (hasGeo) {
      chips.push("Geographic Coverage");
    }

    // 4. Metric Correlations
    if (numericCount >= 2) {
      chips.push("Metric Correlations");
    }

    // 5. Monitoring Log Table
    if (hasMonitoring) {
      chips.push("Monitoring Summary");
    }

    // 6. KPIs
    chips.push("Key KPIs");

    if (chips.length <= 1) {
      chips.unshift("Status & Functionality");
    }

    const uniqueChips = Array.from(new Set(chips));
    return uniqueChips.slice(0, 6);
  }, [sources]);

  const fetchSuggestions = useCallback(
    (customHint = null) => {
      if (!dashboardId) {
        return Promise.resolve();
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

      const existingDescriptors = (existingWidgetsRef.current || [])
        .map((w) => ({
          type: w.type || null,
          form:
            typeof w.form !== "undefined" && w.form !== null
              ? Number(w.form)
              : null,
          question:
            typeof w.question !== "undefined" && w.question !== null
              ? Number(w.question)
              : null,
          config: w.config || {},
        }))
        .filter((d) => Boolean(d.type));

      const payload = {
        existing_widget_types: existingTypes,
        existing_widgets: existingDescriptors,
      };

      const hintToUse =
        customHint !== null ? customHint : promptHintRef.current;
      const trimmedHint = (hintToUse || "").trim();
      if (trimmedHint) {
        payload.prompt_hint = trimmedHint;
      }

      return dashboardAi
        .suggestWidgets(dashboardId, payload, controller.signal)
        .then((res) => {
          const list = Array.isArray(res?.data?.suggestions)
            ? res.data.suggestions
            : [];
          const isAiAvail =
            typeof res?.data?.ai_available === "boolean"
              ? res.data.ai_available
              : list.length > 0;

          if (list.length === 0 && !isAiAvail) {
            setAiAvailable(false);
            setSuggestions([]);
            cachedRef.current = {
              dashboardId,
              data: [],
              promptHint: "",
              aiAvailable: false,
            };
            return;
          }

          setAiAvailable(true);
          setSuggestions(list);
          cachedRef.current = {
            dashboardId,
            data: list,
            promptHint: hintToUse || "",
            aiAvailable: true,
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
    [dashboardId]
  );

  // Background prefetch when dashboardId is available, and instant restore when drawer opens
  useEffect(() => {
    if (!dashboardId) {
      return;
    }

    if (cachedRef.current.dashboardId !== dashboardId) {
      cachedRef.current = {
        dashboardId,
        data: null,
        promptHint: "",
        aiAvailable: true,
      };
      setPromptHint("");
      setSuggestions([]);
      setAiAvailable(true);
      fetchSuggestions("");
      return;
    }

    if (visible && cachedRef.current.data !== null) {
      if (typeof cachedRef.current.aiAvailable === "boolean") {
        setAiAvailable(cachedRef.current.aiAvailable);
      }
      if (suggestions.length === 0) {
        setSuggestions(cachedRef.current.data);
        setPromptHint(cachedRef.current.promptHint || "");
      }
    }
  }, [dashboardId, visible, fetchSuggestions, suggestions.length]);

  // Clean up in-flight request on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

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
            disabled={loading}
          >
            Refresh
          </Button>
        </div>
      }
      placement="right"
      width={460}
      visible={visible}
      open={visible}
      onClose={onClose}
      className="ai-suggestion-drawer"
    >
      <div className="ai-suggestion-drawer-body">
        {!aiAvailable ? (
          <div
            className="ai-suggestion-unavailable"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              padding: "60px 24px",
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                backgroundColor: "#f0f5ff",
                border: "1px solid #d6e4ff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: 20,
                color: "#2563eb",
                fontSize: 28,
              }}
            >
              <ThunderboltFilled />
            </div>
            <div
              style={{
                fontSize: 16,
                fontWeight: 600,
                color: "#1e293b",
                marginBottom: 8,
              }}
            >
              AI Suggestions Unavailable
            </div>
            <div
              style={{
                fontSize: 13,
                lineHeight: "1.5",
                color: "#64748b",
                maxWidth: 320,
              }}
            >
              AI widget suggestions require an AI service to be configured.
              Please check your system configuration to enable dynamic widget
              recommendations.
            </div>
          </div>
        ) : (
          <>
            <div className="ai-suggestion-search-box">
              <Input.Search
                placeholder="Ask AI for specific widgets (max 250 chars)..."
                allowClear
                enterButton="Suggest"
                maxLength={250}
                disabled={loading}
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
                {dynamicPromptChips.map((chip) => (
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
                          {sug.col_span
                            ? `${sug.col_span}/24 col`
                            : "Auto width"}
                        </Tag>
                      </div>

                      {qMeta && (
                        <div className="ai-suggestion-source">
                          <span className="ai-suggestion-source-form">
                            {qMeta.formName}
                          </span>
                          <span className="ai-suggestion-source-separator">
                            •
                          </span>
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
          </>
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
