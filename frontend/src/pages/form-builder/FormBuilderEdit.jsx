import React, {
  useState,
  useRef,
  useEffect,
  useMemo,
  useCallback,
} from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Drawer,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tag,
} from "antd";
import { HistoryOutlined } from "@ant-design/icons";
import WebformEditor from "akvo-react-form-editor";
import "akvo-react-form-editor/dist/index.css";
import { Breadcrumbs } from "../../components";
import { api, store, uiText } from "../../lib";
import { editorToApi, apiToEditor } from "../../lib/form-builder-transform";
import { useNotification } from "../../util/hooks";
import "./style.scss";

const draftKey = (formId) => `form-builder-draft-${formId}`;

const FormBuilderEdit = () => {
  const { formId } = useParams();
  const { notify } = useNotification();

  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [unpublishing, setUnpublishing] = useState(false);
  const [initialValue, setInitialValue] = useState(null);
  const [formStatus, setFormStatus] = useState(null);
  const [formVersion, setFormVersion] = useState(null);
  const [formLatestVersion, setFormLatestVersion] = useState(null);
  const [draftRestored, setDraftRestored] = useState(false);

  // Version history drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [versions, setVersions] = useState([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [activatingId, setActivatingId] = useState(null);

  const draftTimerRef = useRef(null);

  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const pagePath = [
    { title: "Control Center", link: "/control-center" },
    {
      title: text.menuFormBuilder,
      link: "/control-center/form-builder",
    },
    { title: "Edit Form" },
  ];

  const loadForm = useCallback(
    (skipDraftCheck) => {
      return api.get(`/manage/forms/${formId}`).then((res) => {
        const apiData = res.data;
        setFormStatus(apiData.status);
        setFormVersion(apiData.version);
        setFormLatestVersion(apiData.latest_version);

        if (!skipDraftCheck) {
          const raw = localStorage.getItem(draftKey(formId));
          if (raw) {
            try {
              const draft = JSON.parse(raw);
              if (draft.savedAt > (apiData.published_at || "")) {
                setInitialValue(draft.value);
                setDraftRestored(true);
                return;
              }
            } catch (_e) {
              // ignore malformed draft
            }
          }
        }
        setInitialValue(apiToEditor(apiData));
      });
    },
    [formId]
  );

  useEffect(() => {
    loadForm(false).catch((err) => {
      console.error("Failed to load form", err);
      setInitialValue({});
    });

    return () => {
      if (draftTimerRef.current) {
        clearTimeout(draftTimerRef.current);
      }
    };
  }, [loadForm]);

  const loadVersions = () => {
    setVersionsLoading(true);
    api
      .get(`/manage/forms/${formId}/versions`)
      .then((res) => {
        setVersions(res.data);
      })
      .catch((err) => {
        console.error("Failed to load versions", err);
      })
      .finally(() => {
        setVersionsLoading(false);
      });
  };

  const openDrawer = () => {
    setDrawerOpen(true);
    loadVersions();
  };

  const onSave = (editorOutput) => {
    if (draftTimerRef.current) {
      clearTimeout(draftTimerRef.current);
    }
    draftTimerRef.current = setTimeout(() => {
      localStorage.setItem(
        draftKey(formId),
        JSON.stringify({
          value: editorOutput,
          savedAt: new Date().toISOString(),
        })
      );
    }, 2000);

    setSaving(true);
    const payload = editorToApi(editorOutput);
    api
      .put(`/manage/forms/${formId}`, payload)
      .then((res) => {
        localStorage.removeItem(draftKey(formId));
        setFormLatestVersion(res.data.latest_version);
        setFormVersion(res.data.version);
        setFormStatus(res.data.status);
        notify({ type: "success", message: "Form saved" });
      })
      .catch((err) => {
        const msg = err.response?.data?.message || "Failed to save form";
        notify({ type: "error", message: msg });
      })
      .finally(() => {
        setSaving(false);
      });
  };

  const onPublish = () => {
    setPublishing(true);
    api
      .post(`/manage/forms/${formId}/publish`, {})
      .then((res) => {
        setFormStatus(res.data.status);
        setFormVersion(res.data.version);
        setFormLatestVersion(res.data.latest_version);
        notify({ type: "success", message: "Form published" });
      })
      .catch((err) => {
        const msg = err.response?.data?.message || "Failed to publish form";
        notify({ type: "error", message: msg });
      })
      .finally(() => {
        setPublishing(false);
      });
  };

  const onUnpublish = () => {
    setUnpublishing(true);
    api
      .post(`/manage/forms/${formId}/unpublish`, {})
      .then((res) => {
        setFormStatus(res.data.status);
        setFormVersion(res.data.version);
        setFormLatestVersion(res.data.latest_version);
        notify({ type: "success", message: "Form unpublished" });
      })
      .catch((err) => {
        const msg = err.response?.data?.message || "Failed to unpublish form";
        notify({ type: "error", message: msg });
      })
      .finally(() => {
        setUnpublishing(false);
      });
  };

  const onActivateVersion = (versionId, versionNumber) => {
    setActivatingId(versionId);
    api
      .post(`/manage/forms/${formId}/activate/${versionId}`, {})
      .then((res) => {
        setFormStatus(res.data.status);
        setFormVersion(res.data.version);
        setFormLatestVersion(res.data.latest_version);
        notify({
          type: "success",
          message: `Version ${versionNumber} is now active. Reloading editor…`,
        });
        setDrawerOpen(false);
        localStorage.removeItem(draftKey(formId));
        setInitialValue(null);
        return loadForm(true);
      })
      .catch((err) => {
        const msg = err.response?.data?.message || "Failed to activate version";
        notify({ type: "error", message: msg });
      })
      .finally(() => {
        setActivatingId(null);
      });
  };

  const infoBannerText = useMemo(() => {
    if (formStatus !== "published") {
      return null;
    }
    if (formLatestVersion > formVersion) {
      return `Changes saved as snapshot v${formLatestVersion}. Click Publish to activate.`;
    }
    return "Editing a published form creates a new version snapshot. Click Publish to activate it.";
  }, [formStatus, formVersion, formLatestVersion]);

  const versionColumns = [
    {
      title: "Version",
      dataIndex: "version",
      key: "version",
      render: (v, record) => (
        <Space>
          {`v${v}`}
          {record.is_active && <Tag color="green">Active</Tag>}
        </Space>
      ),
    },
    {
      title: "Published At",
      dataIndex: "published_at",
      key: "published_at",
      render: (v) => (v ? new Date(v).toLocaleString() : "—"),
    },
    {
      title: "Published By",
      dataIndex: "published_by",
      key: "published_by",
      render: (v) => v || "—",
    },
    {
      title: "Actions",
      key: "actions",
      render: (_, record) => {
        if (record.is_active) {
          return null;
        }
        return (
          <Popconfirm
            title={`Activate version ${record.version}?`}
            description="This will replace the current active schema. The editor will reload."
            onConfirm={() => {
              onActivateVersion(record.id, record.version);
            }}
            okText="Activate"
            cancelText="Cancel"
          >
            <Button
              size="small"
              loading={activatingId === record.id}
              disabled={activatingId !== null && activatingId !== record.id}
            >
              Set Active
            </Button>
          </Popconfirm>
        );
      },
    },
  ];

  if (initialValue === null) {
    return (
      <div style={{ textAlign: "center", paddingTop: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  const hasPendingSnapshot = formLatestVersion > formVersion;
  const showPublish = formStatus === "draft" || hasPendingSnapshot;
  const showUnpublish = formStatus === "published";
  const hasVersionHistory = formStatus === "published" || versions.length > 0;

  return (
    <div id="form-builder-edit">
      <div className="description-container">
        <Breadcrumbs pagePath={pagePath} />
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              marginTop: 16,
              marginBottom: 8,
            }}
          >
            <Space>
              {hasVersionHistory && (
                <Button
                  icon={<HistoryOutlined />}
                  onClick={openDrawer}
                  disabled={saving || publishing || unpublishing}
                >
                  Versions
                </Button>
              )}
              {showPublish && (
                <Button
                  type="primary"
                  loading={publishing}
                  disabled={saving || unpublishing}
                  onClick={onPublish}
                >
                  Publish
                </Button>
              )}
              {showUnpublish && (
                <Popconfirm
                  title="Unpublish this form?"
                  description="The form will no longer be available for data collection."
                  onConfirm={onUnpublish}
                  okText="Unpublish"
                  cancelText="Cancel"
                >
                  <Button
                    loading={unpublishing}
                    disabled={saving || publishing}
                  >
                    Unpublish
                  </Button>
                </Popconfirm>
              )}
            </Space>
          </div>

          {draftRestored && (
            <Alert
              type="info"
              message="Draft restored from local storage"
              closable
              style={{ marginBottom: 8 }}
              onClose={() => {
                setDraftRestored(false);
              }}
            />
          )}
          {infoBannerText && (
            <Alert
              type="info"
              message={infoBannerText}
              style={{ marginBottom: 8 }}
              showIcon
            />
          )}

          <div style={{ marginTop: 8 }}>
            <WebformEditor
              initialValue={initialValue}
              onSave={saving ? null : onSave}
            />
          </div>
        </div>
      </div>

      <Drawer
        title="Version History"
        width={640}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
        }}
        extra={
          <Button size="small" onClick={loadVersions} loading={versionsLoading}>
            Refresh
          </Button>
        }
      >
        <Table
          columns={versionColumns}
          dataSource={versions}
          rowKey="id"
          loading={versionsLoading}
          pagination={false}
          size="small"
          locale={{ emptyText: "No published versions yet" }}
        />
      </Drawer>
    </div>
  );
};

export default FormBuilderEdit;
