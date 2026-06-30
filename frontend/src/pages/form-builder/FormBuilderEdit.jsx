import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useParams } from "react-router-dom";
import { Button, Popconfirm, Space } from "antd";
import { HistoryOutlined, DownloadOutlined } from "@ant-design/icons";
import WebformEditor from "akvo-react-form-editor";
import "akvo-react-form-editor/dist/index.css";
import { Breadcrumbs } from "../../components";
import {
  api,
  store,
  uiText,
  QUESTION_TYPES,
  ARF_CASCASE_URLS,
} from "../../lib";
import { useNotification } from "../../util/hooks";
import { fetchPublishedForms } from "../../util/form";
import { FormEditorBanners, VersionHistoryDrawer } from "./components";
import "./style.scss";
import { Can } from "../../components/can";

const regExpFilename = /filename="(?<filename>.*)"/;

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

  // Version history drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [versions, setVersions] = useState([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [activatingId, setActivatingId] = useState(null);
  const [previewLoadingId, setPreviewLoadingId] = useState(null);
  const [previewingVersion, setPreviewingVersion] = useState(null);
  const [loading, setLoading] = useState(true);

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

  const loadForm = useCallback(async () => {
    const res = await api.get(`/manage/forms/${formId}`);
    const apiData = res.data;
    setFormStatus(apiData.status);
    setFormVersion(apiData.version);
    setFormLatestVersion(apiData.latest_version);
    setInitialValue(apiData);
    setLoading(false);
  }, [formId]);

  useEffect(() => {
    loadForm();
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
    setSaving(true);
    api
      .put(`/manage/forms/${formId}?allow_delete=true`, editorOutput)
      .then((res) => {
        setPreviewingVersion(null);
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
        // Refresh the published-forms global store so dropdowns/dashboards
        // pick up the newly published form without a full page reload.
        fetchPublishedForms();
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
        // Refresh the published-forms global store so the unpublished form
        // is removed from dropdowns/dashboards without a full page reload.
        fetchPublishedForms();
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

  const onActivateVersion = async (versionId, versionNumber) => {
    try {
      setActivatingId(versionId);
      const res = await api.post(
        `/manage/forms/${formId}/activate/${versionId}`,
        {}
      );
      setFormStatus(res.data.status);
      setFormVersion(res.data.version);
      setFormLatestVersion(res.data.latest_version);
      notify({
        type: "success",
        message: text.formBuilderVersionActivated(versionNumber),
      });
      setDrawerOpen(false);
      setPreviewingVersion(null);
      setLoading(true);
      setInitialValue(null);
      setActivatingId(null);
      await loadForm();
      // Refresh the published-forms global store so the newly activated
      // version's content propagates to dropdowns/dashboards.
      fetchPublishedForms();
    } catch (err) {
      setActivatingId(null);
      const msg = err.response?.data?.message || text.formBuilderActivateError;
      notify({ type: "error", message: msg });
    }
  };

  const onPreview = (record) => {
    setPreviewLoadingId(record.id);
    const prevValue = initialValue;
    setLoading(true);
    setInitialValue(null);
    api
      .get(`/manage/forms/${formId}/versions/${record.id}`)
      .then((res) => {
        const schema = res.data.schema;
        setInitialValue({
          ...schema,
          id: Number(formId),
          status: formStatus,
          latest_version: formLatestVersion,
          active_version_id: null,
        });
        setPreviewingVersion({ id: record.id, version: record.version });
        setDrawerOpen(false);
        setLoading(false);
      })
      .catch((err) => {
        const msg = err.response?.data?.message || text.formBuilderPreviewError;
        notify({ type: "error", message: msg });
        setInitialValue(prevValue);
        setLoading(false);
      })
      .finally(() => {
        setPreviewLoadingId(null);
      });
  };

  const onExitPreview = async () => {
    setPreviewingVersion(null);
    setLoading(true);
    setInitialValue(null);
    await loadForm();
  };

  const onExport = () => {
    api
      .get(`/manage/forms/${formId}/export`, { responseType: "blob" })
      .then((res) => {
        const contentDispositionHeader = res.headers["content-disposition"];
        const filename = regExpFilename.exec(contentDispositionHeader)?.groups
          ?.filename;
        if (!filename) {
          notify({ type: "error", message: text.formBuilderExportError });
          return;
        }
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => {
        notify({ type: "error", message: text.formBuilderExportError });
      });
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
              <Button
                icon={<DownloadOutlined />}
                onClick={onExport}
                disabled={saving || publishing || unpublishing}
              >
                {text.formBuilderExportButton}
              </Button>

              {hasVersionHistory && (
                <Can I="publish" a="form-builder">
                  <Button
                    icon={<HistoryOutlined />}
                    onClick={openDrawer}
                    disabled={saving || publishing || unpublishing}
                  >
                    {text.formBuilderVersionsButton}
                  </Button>
                </Can>
              )}
              {showPublish && (
                <Can I="publish" a="form-builder">
                  <Button
                    type="primary"
                    loading={publishing}
                    disabled={saving || unpublishing}
                    onClick={onPublish}
                  >
                    {text.formBuilderPublishButton}
                  </Button>
                </Can>
              )}
              {showUnpublish && (
                <Can I="publish" a="form-builder">
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
                </Can>
              )}
            </Space>
          </div>

          <FormEditorBanners
            previewingVersion={previewingVersion}
            onExitPreview={onExitPreview}
            infoBannerText={infoBannerText}
            text={text}
          />

          <div style={{ marginTop: 8 }}>
            <WebformEditor
              initialValue={loading ? {} : initialValue}
              onSave={saving ? null : onSave}
              limitQuestionType={Object.keys(QUESTION_TYPES)}
              settingCascadeURL={ARF_CASCASE_URLS}
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
