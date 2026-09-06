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
  ArrowLeftOutlined as BackToEditIcon,
  EyeOutlined,
  SaveOutlined,
  SendOutlined,
} from "@ant-design/icons";
import { store, uiText } from "../../lib";
import dashboardApi from "../../util/dashboardApi";
import BuilderPalette from "./BuilderPalette";
import BuilderCanvas from "./BuilderCanvas";
import BuilderInspector from "./BuilderInspector";
import EmbedEditor from "./EmbedEditor";
import EmbedFrame from "../../components/dashboard/EmbedFrame";
import DashboardGrid from "../../components/dashboard/DashboardGrid";
import DashboardViewFilters from "../../components/dashboard/DashboardViewFilters";
import { WIDGET_DEFAULTS, defaultMeasure } from "./builderConstants";
import "./builder.scss";
import "./viewer.scss";

let nextTempId = -1;

const EMPTY_FILTERS = {
  from_date: null,
  to_date: null,
  date_question_id: null,
  administration_id: null,
};

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
  // Preview is a mode of this screen, not a different screen. See below.
  const [previewing, setPreviewing] = useState(false);
  const [previewFilters, setPreviewFilters] = useState(EMPTY_FILTERS);
  // Minted per preview, because the markup being previewed is unsaved:
  // there is no published snapshot for the embed host to serve.
  const [previewEmbedUrl, setPreviewEmbedUrl] = useState(null);

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
          // /sources answers 400 for an embed — it has no form family
          // (spec D-7) — so an embed must not ask for one.
          found.kind === "embed"
            ? Promise.resolve({ data: null })
            : dashboardApi.sources(found.id),
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
      // /escalation sends widget.form as `monitoring_form_id` — it is
      // inherently a "registration parent plus its latest monitoring child"
      // query, and returns nothing at all for a registration form. Every
      // other widget type is happy on forms[0], which /sources always leads
      // with; a table is not, so it takes the first monitoring form or none.
      const firstForm =
        type === "table"
          ? sources?.forms?.find((f) => f.type === "monitoring")
          : sources?.forms?.[0];
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
      // Only for a monitoring form. `/sources` leads with the root
      // registration form, so this is usually null — and seeding
      // current_state anyway is what made every new chart widget fail its
      // first save.
      const measure = defaultMeasure(type, firstForm);
      if (measure) {
        newWidget.config.measure = measure;
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
    if (dashboard?.kind === "embed") {
      return {
        name: dashboard?.name,
        description: dashboard?.description || null,
        kind: "embed",
        embed_snippet: dashboard?.embed_snippet,
      };
    }
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
      default_filters: dashboard?.default_filters || {},
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

  // Visibility
  //
  // This writes through its own endpoint rather than folding into
  // `dashboard` state and waiting for Save — see BuilderInspector's
  // visibility block for why that distinction has to be visible to the
  // author. Going private is instant and reversible, so it skips the
  // confirmation that going public requires.
  const handleVisibility = useCallback(
    (nextPublic) => {
      const id = dashboardIdRef.current;
      if (!id) {
        return;
      }
      const apply = () => {
        dashboardApi
          .setVisibility(id, nextPublic)
          .then(() => {
            setDashboard((prev) => ({ ...prev, is_public: nextPublic }));
            message.success(
              nextPublic ? text.dashboardMadePublic : text.dashboardMadePrivate
            );
          })
          .catch(() => {
            message.error(text.dashboardForbidden);
          });
      };
      if (!nextPublic) {
        // Going private is instantly reversible and reduces exposure.
        // Confirming it would train authors to click through the one
        // dialog that matters.
        apply();
        return;
      }
      // `dashboard.widgets` is only ever the snapshot from the initial
      // load (line ~82) — every add/delete/reorder updates the separate
      // `widgets` state instead, which is what actually gets saved and
      // published. Reading `dashboard.widgets` here would freeze this
      // check at whatever the dashboard held when the builder opened.
      const hasRawData = widgets.some((w) => ["table", "map"].includes(w.type));
      Modal.confirm({
        title: text.dashboardMakePublicTitle,
        content: hasRawData
          ? `${text.dashboardMakePublicBody} ${text.dashboardMakePublicRawData}`
          : text.dashboardMakePublicBody,
        okText: text.dashboardMakePublicOk,
        onOk: apply,
      });
    },
    [widgets, text]
  );

  // Preview
  //
  // This used to open /dashboards/:slug in a new tab, which showed the
  // last *published* snapshot: an author who had added three widgets and
  // not pressed Publish saw none of them, and an author of an unpublished
  // draft got a 404. That is not a preview.
  //
  // It now swaps the canvas for the viewer's own renderer, fed from
  // unsaved local state. Same component tree, two entry points — which is
  // what makes "viewer and preview render identically" testable rather
  // than merely asserted.
  // An embed preview has to render through the embed host, exactly as the
  // viewer will (spec D-9) — that frame is the only warning an author gets
  // that a snippet is broken, since a cross-origin frame tells us nothing.
  // The URL is cleared either way, so an edited snippet is never previewed
  // through a stale one, and a failure leaves the frame in its "cannot be
  // shown" state, which is the honest report.
  const handlePreview = useCallback(() => {
    const next = !previewing;
    setSelectedId(null);
    setPreviewing(next);
    setPreviewEmbedUrl(null);
    if (next && dashboard?.kind === "embed" && dashboardIdRef.current) {
      dashboardApi
        .embedPreview(dashboardIdRef.current, dashboard.embed_snippet || "")
        .then((res) => setPreviewEmbedUrl(res.data.embed_url))
        .catch(() => {});
    }
  }, [previewing, dashboard]);

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

  const isEmbed = dashboard?.kind === "embed";

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
          {previewing && (
            <span className="dashboard-view-badge">
              {text.dashboardPreview}
            </span>
          )}
        </div>
        <div className="builder-toolbar-right">
          <Button
            icon={previewing ? <BackToEditIcon /> : <EyeOutlined />}
            shape="round"
            onClick={handlePreview}
          >
            {previewing ? text.dashboardBackToEditing : text.dashboardPreview}
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

      {/* Body — the editing surface, or the viewer's own renderer */}
      {previewing ? (
        /* The embed modifier has to match DashboardViewer's exactly.
           Without it this element is `flex: 1; overflow-y: auto` with no
           `display: flex`, so `.dashboard-embed-frame { flex: 1 1 auto }`
           never applies and the frame collapses to its 480px min-height.
           Spec D-9 makes Preview the whole mitigation for an embed we
           cannot verify loaded, so an author sizing a vendor report here
           must be looking at the published page's height, not another. */
        <div
          className={`dashboard-view-content${
            isEmbed ? " dashboard-view-content-embed" : ""
          }`}
        >
          <div className="dashboard-view-header">
            <div className="dashboard-view-header-inner">
              <div className="dashboard-view-title">{dashboard.name}</div>
              {dashboard.description && (
                <div className="dashboard-view-desc">
                  {dashboard.description}
                </div>
              )}
            </div>
          </div>

          {isEmbed ? (
            <EmbedFrame
              src={previewEmbedUrl}
              title={dashboard.name || "Embedded dashboard"}
            />
          ) : (
            <>
              <DashboardViewFilters
                defaultFilters={dashboard.default_filters}
                value={previewFilters}
                onChange={setPreviewFilters}
              />

              {/* Local, unsaved widgets — the whole point of a preview. The
                  same component the viewer renders, with no prop telling it
                  which caller it has. */}
              <DashboardGrid
                widgets={widgets}
                filters={previewFilters}
                rootFormId={dashboard.root_form?.id}
              />
            </>
          )}
        </div>
      ) : (
        <div className="builder-body">
          {isEmbed ? (
            <EmbedEditor
              name={dashboard.name}
              description={dashboard.description || ""}
              snippet={dashboard.embed_snippet}
              isPublic={Boolean(dashboard?.is_public)}
              isPublished={dashboard?.status === "published"}
              onDashboardChange={handleDashboardChange}
              onVisibilityChange={handleVisibility}
            />
          ) : (
            <>
              <BuilderPalette onAdd={handleAdd} />
              <BuilderCanvas
                widgets={widgets}
                selectedId={selectedId}
                dashboardName={dashboard.name}
                dashboardDesc={dashboard.description || ""}
                // The canvas is unfiltered on purpose: the chips above it are
                // not controls, and an author sizing a widget wants the whole
                // family, not a slice of it. Preview is where the filter bar
                // becomes real.
                filters={EMPTY_FILTERS}
                rootFormId={dashboard.root_form?.id}
                defaultFilters={dashboard.default_filters}
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
                isPublic={Boolean(dashboard?.is_public)}
                isPublished={dashboard?.status === "published"}
                onWidgetChange={handleWidgetChange}
                onDashboardChange={handleDashboardChange}
                onVisibilityChange={handleVisibility}
                errorMessage={widgetError}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default DashboardBuilder;
