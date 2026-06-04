import React, {
  useState,
  useRef,
  useEffect,
  useMemo,
  useCallback,
} from "react";
import { useParams } from "react-router-dom";
import { Button, Popconfirm, Space, Spin } from "antd";
import { HistoryOutlined } from "@ant-design/icons";
import WebformEditor from "akvo-react-form-editor";
import "akvo-react-form-editor/dist/index.css";
import { Breadcrumbs } from "../../components";
import { api, store, uiText } from "../../lib";
import { editorToApi, apiToEditor } from "../../lib/form-builder-transform";
import { useNotification } from "../../util/hooks";
import { FormEditorBanners, VersionHistoryDrawer } from "./components";
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
  const [previewLoadingId, setPreviewLoadingId] = useState(null);
  const [previewingVersion, setPreviewingVersion] = useState(null);

  const draftTimerRef = useRef(null);

  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const pagePath = [
    { title: text.controlCenter, link: "/control-center" },
    {
      title: text.menuFormBuilder,
      link: "/control-center/form-builder",
    },
    { title: text.formBuilderEditTitle },
  ];

  const loadForm = useCallback(
    (skipDraftCheck) => {
      return api.get(`/manage/forms/${formId}`).then((res) => {
        const apiData = res.data;
        setFormStatus(apiData.status);
        setFormVersion(apiData.version);
        setFormLatestVersion(apiData.latest_version);
        setInitialValue(apiToEditor(apiData));

        if (!skipDraftCheck) {
          const raw = localStorage.getItem(draftKey(formId));
          if (raw) {
            try {
              const draft = JSON.parse(raw);
              // Reject draft if it was saved against a different form version
              const versionStale =
                typeof draft.formVersion !== "undefined" &&
                draft.formVersion !== apiData.version;
              if (
                !versionStale &&
                draft.savedAt > (apiData.published_at || "")
              ) {
                setInitialValue(draft.value);
                setDraftRestored(true);
                return;
              }
              if (versionStale) {
                localStorage.removeItem(draftKey(formId));
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
          formVersion,
        })
      );
    }, 2000);

    setSaving(true);
    const payload = editorToApi(editorOutput);
    api
      .put(`/manage/forms/${formId}?allow_delete=true`, payload)
      .then((res) => {
        setPreviewingVersion(null);
        localStorage.removeItem(draftKey(formId));
        setFormLatestVersion(res.data.latest_version);
        setFormVersion(res.data.version);
        setFormStatus(res.data.status);
        notify({ type: "success", message: text.formBuilderSaveSuccess });
      })
      .catch((err) => {
        const msg = err.response?.data?.message || text.formBuilderSaveError;
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
        notify({ type: "success", message: text.formBuilderPublishSuccess });
      })
      .catch((err) => {
        const msg = err.response?.data?.message || text.formBuilderPublishError;
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
        notify({ type: "success", message: text.formBuilderUnpublishSuccess });
      })
      .catch((err) => {
        const msg =
          err.response?.data?.message || text.formBuilderUnpublishError;
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
          message: text.formBuilderVersionActivated(versionNumber),
        });
        setDrawerOpen(false);
        setPreviewingVersion(null);
        localStorage.removeItem(draftKey(formId));
        setInitialValue(null);
        return loadForm(true);
      })
      .catch((err) => {
        const msg =
          err.response?.data?.message || text.formBuilderActivateError;
        notify({ type: "error", message: msg });
      })
      .finally(() => {
        setActivatingId(null);
      });
  };

  const onPreview = (record) => {
    setPreviewLoadingId(record.id);
    const prevValue = initialValue;
    setInitialValue(null);
    api
      .get(`/manage/forms/${formId}/versions/${record.id}`)
      .then((res) => {
        const schema = res.data.schema;
        setInitialValue(
          apiToEditor({
            ...schema,
            id: Number(formId),
            status: formStatus,
            latest_version: formLatestVersion,
            active_version_id: null,
          })
        );
        setPreviewingVersion({ id: record.id, version: record.version });
        setDrawerOpen(false);
      })
      .catch((err) => {
        const msg = err.response?.data?.message || text.formBuilderPreviewError;
        notify({ type: "error", message: msg });
        setInitialValue(prevValue);
      })
      .finally(() => {
        setPreviewLoadingId(null);
      });
  };

  const onResetDraft = () => {
    localStorage.removeItem(draftKey(formId));
    setDraftRestored(false);
    setInitialValue(null);
    loadForm(true);
  };

  const onExitPreview = () => {
    setPreviewingVersion(null);
    setInitialValue(null);
    loadForm(true);
  };

  const infoBannerText = useMemo(() => {
    if (formStatus !== "published") {
      return null;
    }
    if (formLatestVersion > formVersion) {
      return text.formBuilderSnapshotPending(formLatestVersion);
    }
    return text.formBuilderPublishedInfo;
  }, [formStatus, formVersion, formLatestVersion, text]);

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
                  {text.formBuilderVersionsButton}
                </Button>
              )}
              {showPublish && (
                <Button
                  type="primary"
                  loading={publishing}
                  disabled={saving || unpublishing}
                  onClick={onPublish}
                >
                  {text.formBuilderPublishButton}
                </Button>
              )}
              {showUnpublish && (
                <Popconfirm
                  title={text.formBuilderUnpublishTitle}
                  description={text.formBuilderUnpublishDesc}
                  onConfirm={onUnpublish}
                  okText={text.formBuilderUnpublishButton}
                  cancelText={text.cancelButton}
                >
                  <Button
                    loading={unpublishing}
                    disabled={saving || publishing}
                  >
                    {text.formBuilderUnpublishButton}
                  </Button>
                </Popconfirm>
              )}
            </Space>
          </div>

          <FormEditorBanners
            draftRestored={draftRestored}
            onDismissDraft={() => {
              setDraftRestored(false);
            }}
            onResetDraft={onResetDraft}
            previewingVersion={previewingVersion}
            onExitPreview={onExitPreview}
            infoBannerText={infoBannerText}
            text={text}
          />

          <div style={{ marginTop: 8 }}>
            <WebformEditor
              initialValue={initialValue}
              onSave={saving ? null : onSave}
            />
          </div>
        </div>
      </div>

      <VersionHistoryDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
        }}
        versions={versions}
        loading={versionsLoading}
        onRefresh={loadVersions}
        activatingId={activatingId}
        previewLoadingId={previewLoadingId}
        onActivate={onActivateVersion}
        onPreview={onPreview}
        text={text}
      />
    </div>
  );
};

export default FormBuilderEdit;
