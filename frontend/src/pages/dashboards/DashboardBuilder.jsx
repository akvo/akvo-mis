import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button, Modal, Spin, message } from "antd";
import {
  ArrowLeftOutlined,
  EyeOutlined,
  SaveOutlined,
  SendOutlined,
} from "@ant-design/icons";
import { store, uiText } from "../../lib";
import dashboardApi from "../../util/dashboardApi";
import BuilderPalette from "./BuilderPalette";
import BuilderCanvas from "./BuilderCanvas";
import BuilderInspector from "./BuilderInspector";
import { WIDGET_DEFAULTS } from "./builderConstants";
import "./builder.scss";

let nextTempId = -1;

const DashboardBuilder = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [dashboard, setDashboard] = useState(null);
  const [widgets, setWidgets] = useState([]);
  const [sources, setSources] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [widgetError, setWidgetError] = useState(null);

  const dashboardIdRef = useRef(null);

  // Load dashboard and sources
  useEffect(() => {
    setLoading(true);
    // We need to first get the dashboard list to find the ID from slug
    dashboardApi
      .list()
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : [];
        const found = list.find((d) => d.slug === slug);
        if (!found) {
          message.error(text.errorSomething || "Dashboard not found");
          navigate("/control-center/dashboard");
          return Promise.reject(new Error("not found"));
        }
        dashboardIdRef.current = found.id;
        return Promise.all([
          dashboardApi.get(found.id),
          dashboardApi.sources(found.id),
        ]);
      })
      .then(([detailRes, sourcesRes]) => {
        const d = detailRes.data;
        setDashboard(d);
        setWidgets(d.widgets || []);
        setSources(sourcesRes.data);
      })
      .catch(() => {
        // error already handled or navigation happened
      })
      .finally(() => {
        setLoading(false);
      });
  }, [slug, navigate, text]);

  const selectedWidget = useMemo(
    () => widgets.find((w) => w.id === selectedId) || null,
    [widgets, selectedId]
  );

  // Add widget
  const handleAdd = useCallback(
    (type) => {
      nextTempId -= 1;
      const defaults = WIDGET_DEFAULTS[type] || {};
      const firstForm = sources?.forms?.[0];
      const newWidget = {
        id: nextTempId,
        order: widgets.length + 1,
        type,
        col_span: defaults.col_span || 24,
        title: "",
        color: defaults.color || null,
        form: type !== "section_title" && firstForm ? firstForm.id : null,
        question: null,
        config: { ...(defaults.config || {}) },
      };
      // Default measure for monitoring forms
      if (
        firstForm?.type === "monitoring" &&
        type !== "section_title" &&
        type !== "table"
      ) {
        newWidget.config.measure = "current_state";
      }
      setWidgets((prev) => [...prev, newWidget]);
      setSelectedId(newWidget.id);
      setDirty(true);
    },
    [widgets.length, sources]
  );

  // Select widget
  const handleSelect = useCallback((id) => {
    setSelectedId(id);
    setWidgetError(null);
  }, []);

  const handleDeselect = useCallback(() => {
    setSelectedId(null);
    setWidgetError(null);
  }, []);

  // Move widget
  const handleMove = useCallback((idx, dir) => {
    setWidgets((prev) => {
      const arr = [...prev];
      const toIdx = idx + dir;
      if (toIdx < 0 || toIdx >= arr.length) {
        return arr;
      }
      const tmp = arr[idx];
      arr[idx] = arr[toIdx];
      arr[toIdx] = tmp;
      return arr;
    });
    setDirty(true);
  }, []);

  // Delete widget
  const handleDelete = useCallback(
    (id) => {
      setWidgets((prev) => prev.filter((w) => w.id !== id));
      if (selectedId === id) {
        setSelectedId(null);
      }
      setDirty(true);
    },
    [selectedId]
  );

  // Reorder (drag & drop)
  const handleReorder = useCallback((fromIdx, toIdx) => {
    setWidgets((prev) => {
      const arr = [...prev];
      const [moved] = arr.splice(fromIdx, 1);
      arr.splice(toIdx, 0, moved);
      return arr;
    });
    setDirty(true);
  }, []);

  // Update widget from inspector
  const handleWidgetChange = useCallback((updated) => {
    setWidgets((prev) => prev.map((w) => (w.id === updated.id ? updated : w)));
    setDirty(true);
    setWidgetError(null);
  }, []);

  // Update dashboard metadata
  const handleDashboardChange = useCallback((field, value) => {
    setDashboard((prev) => ({ ...prev, [field]: value }));
    setDirty(true);
  }, []);

  // Build PUT payload
  const buildPayload = useCallback(() => {
    const orderedWidgets = widgets.map((w, i) => ({
      id: w.id < 0 ? null : w.id,
      order: i + 1,
      type: w.type,
      col_span: w.col_span,
      title: w.title || null,
      color: w.color || null,
      form: w.form || null,
      question: w.question || null,
      config: w.config || {},
    }));
    return {
      name: dashboard?.name,
      description: dashboard?.description || null,
      default_filters: dashboard?.default_filters || {
        date: { enabled: true },
        administration: { enabled: true },
      },
      widgets: orderedWidgets,
    };
  }, [widgets, dashboard]);

  // Save
  const handleSave = useCallback(() => {
    const id = dashboardIdRef.current;
    if (!id) {
      return;
    }
    setSaving(true);
    setWidgetError(null);
    dashboardApi
      .update(id, buildPayload())
      .then(() => {
        message.success(text.dashboardSaved || "Dashboard saved");
        setDirty(false);
      })
      .catch((err) => {
        if (err?.response?.status === 400) {
          const data = err.response.data;
          if (typeof data?.widget_index === "number") {
            const badWidget = widgets[data.widget_index];
            if (badWidget) {
              setSelectedId(badWidget.id);
              setWidgetError(data.message || "Validation error");
            }
          } else {
            message.error(data?.message || "Validation error");
          }
        } else if (err?.response?.status === 403) {
          message.error(
            text.dashboardForbidden ||
              "You no longer have permission to perform this action."
          );
        } else {
          message.error(text.errorSomething || "Something went wrong");
        }
      })
      .finally(() => {
        setSaving(false);
      });
  }, [buildPayload, text, widgets]);

  // Publish
  const handlePublish = useCallback(() => {
    const id = dashboardIdRef.current;
    if (!id) {
      return;
    }

    const doPublish = () => {
      setPublishing(true);
      const saveFirst = dirty
        ? dashboardApi.update(id, buildPayload())
        : Promise.resolve();
      saveFirst
        .then(() => dashboardApi.publish(id))
        .then(() => {
          message.success(text.dashboardPublished || "Dashboard published");
          setDirty(false);
          setDashboard((prev) => ({ ...prev, status: "published" }));
        })
        .catch((err) => {
          if (err?.response?.status === 403) {
            message.error(
              text.dashboardForbidden ||
                "You no longer have permission to perform this action."
            );
          } else {
            message.error(text.errorSomething || "Something went wrong");
          }
        })
        .finally(() => {
          setPublishing(false);
        });
    };

    if (dashboard?.status === "published") {
      Modal.confirm({
        title: "Re-publish dashboard?",
        content:
          "This will update the published version visible to all viewers.",
        okText: "Publish",
        onOk: doPublish,
      });
    } else {
      doPublish();
    }
  }, [dirty, buildPayload, dashboard?.status, text]);

  // Preview
  const handlePreview = useCallback(() => {
    window.open(`/dashboards/${slug}`, "_blank");
  }, [slug]);

  // Unsaved changes prompt
  useEffect(() => {
    if (!dirty) {
      return () => {};
    }
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => {
      window.removeEventListener("beforeunload", handler);
    };
  }, [dirty]);

  if (loading) {
    return (
      <div className="builder-loading">
        <Spin size="large" />
      </div>
    );
  }

  if (!dashboard) {
    return null;
  }

  const statusLabel =
    dashboard.status === "published"
      ? text.published || "Published"
      : text.draft || "Draft";
  const statusClass = dashboard.status === "published" ? "published" : "draft";

  return (
    <div className="builder-shell">
      {/* Toolbar */}
      <div className="builder-toolbar">
        <div className="builder-toolbar-left">
          <button
            className="builder-back-btn"
            onClick={() => {
              if (dirty) {
                Modal.confirm({
                  title: "Unsaved changes",
                  content: "You have unsaved changes. Leave without saving?",
                  okText: "Leave",
                  okType: "danger",
                  cancelText: "Stay",
                  onOk: () => navigate("/control-center/dashboard"),
                });
              } else {
                navigate("/control-center/dashboard");
              }
            }}
          >
            <ArrowLeftOutlined />
          </button>
          <input
            className="builder-name-input"
            value={dashboard.name || ""}
            onChange={(e) => handleDashboardChange("name", e.target.value)}
            placeholder="Untitled dashboard"
          />
          <span
            className={`builder-status-badge builder-status-badge--${statusClass}`}
          >
            {statusLabel}
          </span>
        </div>
        <div className="builder-toolbar-right">
          <Button icon={<EyeOutlined />} shape="round" onClick={handlePreview}>
            {text.preview || "Preview"}
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            shape="round"
            loading={saving}
            onClick={handleSave}
          >
            {text.dashboardSave || "Save dashboard"}
          </Button>
          <Button
            icon={<SendOutlined />}
            shape="round"
            loading={publishing}
            onClick={handlePublish}
          >
            {text.publish || "Publish"}
          </Button>
        </div>
      </div>

      {/* Body */}
      <div className="builder-body">
        <BuilderPalette onAdd={handleAdd} />
        <BuilderCanvas
          widgets={widgets}
          selectedId={selectedId}
          dashboardName={dashboard.name}
          dashboardDesc={dashboard.description || ""}
          onSelect={handleSelect}
          onDeselect={handleDeselect}
          onMove={handleMove}
          onDelete={handleDelete}
          onReorder={handleReorder}
        />
        <BuilderInspector
          widget={selectedWidget}
          sources={sources}
          dashboardName={dashboard.name}
          dashboardDesc={dashboard.description || ""}
          defaultFilters={dashboard.default_filters}
          onWidgetChange={handleWidgetChange}
          onDashboardChange={handleDashboardChange}
          errorMessage={widgetError}
        />
      </div>
    </div>
  );
};

export default DashboardBuilder;
