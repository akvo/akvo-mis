import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Alert, Button, Modal, Spin, message } from "antd";
import {
  PlusOutlined,
  EditOutlined,
  EyeOutlined,
  DeleteOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { store, uiText } from "../../lib";
import { AbilityContext } from "../../components/can";
import dashboardApi from "../../util/dashboardApi";
import CreateDashboardModal from "./CreateDashboardModal";
import "./style.scss";

const handleApiError = (err, text) => {
  if (err?.response?.status === 403) {
    message.error(
      text.dashboardForbidden ||
        "You no longer have permission to perform this action."
    );
    return;
  }
  message.error(text.errorSomething || "Something went wrong");
};

const DashboardList = () => {
  const [dashboards, setDashboards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [createVisible, setCreateVisible] = useState(false);
  const navigate = useNavigate();
  const ability = useContext(AbilityContext);
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const canCreate =
    ability.can("manage", "dashboard") || ability.can("create", "dashboard");
  const canEdit =
    ability.can("manage", "dashboard") || ability.can("edit", "dashboard");
  const canDelete =
    ability.can("manage", "dashboard") || ability.can("delete", "dashboard");

  const fetchDashboards = useCallback(() => {
    setLoading(true);
    setForbidden(false);
    dashboardApi
      .list()
      .then((res) => {
        setDashboards(Array.isArray(res.data) ? res.data : []);
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          setForbidden(true);
        }
        setDashboards([]);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchDashboards();
  }, [fetchDashboards]);

  const handleCreate = useCallback(
    (created) => {
      setCreateVisible(false);
      message.success(text.dashboardCreated || "Dashboard created");
      navigate(`/control-center/dashboard/${created.slug}`);
    },
    [navigate, text]
  );

  const handleDelete = useCallback(
    (id, name) => {
      Modal.confirm({
        title: text.dashboardDeleteConfirm || "Delete this dashboard?",
        icon: <ExclamationCircleOutlined />,
        content: name,
        okText: text.delete || "Delete",
        okType: "danger",
        cancelText: text.cancel || "Cancel",
        onOk: () =>
          dashboardApi
            .destroy(id)
            .then(() => {
              message.success(text.dashboardDeleted || "Dashboard deleted");
              setDashboards((prev) => prev.filter((d) => d.id !== id));
            })
            .catch((err) => {
              handleApiError(err, text);
            }),
      });
    },
    [text]
  );

  const formatDate = useCallback((dateStr) => {
    if (!dateStr) {
      return "";
    }
    // Backend returns DD-MM-YYYY HH:MM:SS — convert to YYYY-MM-DD for parsing
    const parts = dateStr.match(/^(\d{2})-(\d{2})-(\d{4})/);
    const d = parts
      ? new Date(`${parts[3]}-${parts[2]}-${parts[1]}`)
      : new Date(dateStr);
    if (isNaN(d.getTime())) {
      return "";
    }
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }, []);

  if (loading) {
    return (
      <div className="dashboards-page">
        <div className="dashboards-loading">
          <Spin size="large" />
        </div>
      </div>
    );
  }

  return (
    <div className="dashboards-page">
      <div className="dashboards-container">
        <div className="dashboards-header">
          <div>
            <h2 className="dashboards-title">
              {text.dashboardListTitle || "My dashboards"}
            </h2>
            <p className="dashboards-subtitle">
              {text.dashboardListSubtitle ||
                "Build and manage your custom data dashboards."}
            </p>
          </div>
          {canCreate && (
            <Button
              type="primary"
              shape="round"
              icon={<PlusOutlined />}
              onClick={() => setCreateVisible(true)}
            >
              {text.dashboardNew || "New dashboard"}
            </Button>
          )}
        </div>

        {forbidden && (
          <Alert
            type="warning"
            showIcon
            message={
              text.dashboardForbidden ||
              "You no longer have permission to perform this action."
            }
            style={{ marginBottom: 20 }}
          />
        )}

        {dashboards.length === 0 && !forbidden ? (
          <div className="dashboards-empty">
            <div className="dashboards-empty-icon">
              <svg width="46" height="46" viewBox="0 0 24 24" fill="none">
                <rect
                  x="3"
                  y="4"
                  width="8"
                  height="8"
                  rx="1.5"
                  stroke="#1651b6"
                  strokeWidth="1.6"
                />
                <rect
                  x="13"
                  y="4"
                  width="8"
                  height="5"
                  rx="1.5"
                  stroke="#1651b6"
                  strokeWidth="1.6"
                />
                <rect
                  x="13"
                  y="11"
                  width="8"
                  height="9"
                  rx="1.5"
                  stroke="#1651b6"
                  strokeWidth="1.6"
                />
                <rect
                  x="3"
                  y="14"
                  width="8"
                  height="6"
                  rx="1.5"
                  stroke="#1651b6"
                  strokeWidth="1.6"
                />
              </svg>
            </div>
            <h3>{text.dashboardEmptyTitle || "No dashboards yet"}</h3>
            <p>
              {text.dashboardEmptyDesc ||
                "Create your first custom dashboard to visualise data from your forms."}
            </p>
            {canCreate && (
              <Button
                type="primary"
                shape="round"
                icon={<PlusOutlined />}
                onClick={() => setCreateVisible(true)}
              >
                {text.dashboardNew || "New dashboard"}
              </Button>
            )}
          </div>
        ) : (
          <div className="dashboards-grid">
            {dashboards.map((d) => (
              <div key={d.id} className="dashboard-card">
                {canDelete && (
                  <button
                    className="dashboard-card-delete dashboard-btn-icon dashboard-btn-icon--danger"
                    title={text.delete || "Delete"}
                    aria-label={text.delete || "Delete"}
                    onClick={() => handleDelete(d.id, d.name)}
                  >
                    <DeleteOutlined />
                  </button>
                )}
                <div className="dashboard-card-body">
                  <div className="dashboard-card-name-row">
                    <span className="dashboard-card-name">{d.name}</span>
                    <span
                      className={`dashboard-card-badge dashboard-card-badge--${d.status}`}
                    >
                      {d.status === "published"
                        ? text.published || "Published"
                        : text.draft || "Draft"}
                    </span>
                    {/* Reports visibility only — the switch that sets it lives
                        in the settings panel (Task 11). Blue rather than
                        green: green is already the lifecycle badge above, and
                        two green badges would read as one axis, not two. */}
                    <span
                      className={`dashboard-visibility-badge dashboard-visibility-badge--${
                        d.is_public ? "public" : "private"
                      }`}
                      aria-label={text.dashboardVisibilityTitle}
                    >
                      {d.is_public
                        ? text.dashboardVisibilityPublic
                        : text.dashboardVisibilityPrivate}
                    </span>
                  </div>
                  <div className="dashboard-card-desc">{d.description}</div>
                </div>
                <div className="dashboard-card-footer">
                  <div className="dashboard-card-meta">
                    {d.kind === "embed" ? (
                      /* "0 widgets" would be true and useless. */
                      <span>{text.dashboardEmbedBadge}</span>
                    ) : (
                      <>
                        {(d.widgets || []).length} {text.widgets || "widgets"}{" "}
                      </>
                    )}
                    &middot; {formatDate(d.updated || d.created)}
                  </div>
                  <div className="dashboard-card-actions">
                    <button
                      className="dashboard-btn-preview"
                      onClick={() => navigate(`/dashboards/${d.slug}`)}
                    >
                      <EyeOutlined />
                      {text.dashboardPreview || "Preview"}
                    </button>
                    {canEdit && (
                      <button
                        className="dashboard-btn-edit"
                        onClick={() =>
                          navigate(`/control-center/dashboard/${d.slug}`)
                        }
                      >
                        <EditOutlined />
                        {text.edit || "Edit"}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <CreateDashboardModal
        visible={createVisible}
        onCancel={() => setCreateVisible(false)}
        onCreate={handleCreate}
      />
    </div>
  );
};

export default DashboardList;
