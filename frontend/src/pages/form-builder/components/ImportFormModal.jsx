import React, { useState, useEffect, useCallback } from "react";
import {
  Modal,
  Upload,
  Alert,
  Radio,
  Select,
  Button,
  Space,
  Spin,
  Result,
  Typography,
} from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../../../lib";

const { Dragger } = Upload;
const { Text } = Typography;

const MAX_FILE_SIZE_MB = 5;
const POLL_INTERVAL_MS = 2500;

const IssueList = ({ issues, type, title }) => {
  if (!issues || issues.length === 0) {
    return null;
  }
  return (
    <Alert
      type={type}
      showIcon
      style={{ marginBottom: 12 }}
      message={title}
      description={
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {issues.map((issue, idx) => (
            <li key={idx}>
              {issue.path ? <Text code>{issue.path}</Text> : null}{" "}
              {issue.message}
            </li>
          ))}
        </ul>
      }
    />
  );
};

const ImportFormModal = ({ open, onClose, onImported, text }) => {
  const navigate = useNavigate();

  // step: upload | review | importing | done | failed
  const [step, setStep] = useState("upload");
  const [file, setFile] = useState(null);
  const [preflight, setPreflight] = useState(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [errors, setErrors] = useState([]);
  const [mode, setMode] = useState("create_or_update");
  const [parentId, setParentId] = useState(null);
  const [parentOptions, setParentOptions] = useState([]);
  const [taskId, setTaskId] = useState(null);
  const [importedForm, setImportedForm] = useState(null);

  const resetState = useCallback(() => {
    setStep("upload");
    setFile(null);
    setPreflight(null);
    setPreflightLoading(false);
    setErrors([]);
    setMode("create_or_update");
    setParentId(null);
    setTaskId(null);
    setImportedForm(null);
  }, []);

  useEffect(() => {
    if (open) {
      resetState();
    }
  }, [open, resetState]);

  const searchParentForms = useCallback((search) => {
    const params = new URLSearchParams({ type: "registration", page: 1 });
    if (search) {
      params.set("search", search);
    }
    api
      .get(`/manage/forms?${params.toString()}`)
      .then((res) => {
        setParentOptions(
          (res.data.data || []).map((f) => ({ value: f.id, label: f.name }))
        );
      })
      .catch(() => {
        setParentOptions([]);
      });
  }, []);

  const runPreflight = (selectedFile) => {
    setPreflightLoading(true);
    setErrors([]);
    const formData = new FormData();
    formData.append("file", selectedFile);
    api
      .post("/manage/forms/import/preflight", formData)
      .then((res) => {
        setPreflight(res.data);
        setFile(selectedFile);
        if (res.data?.match?.exists) {
          setMode("create_or_update");
        }
        if (res.data?.parent?.resolved?.id) {
          setParentId(res.data.parent.resolved.id);
          setParentOptions([
            {
              value: res.data.parent.resolved.id,
              label: res.data.parent.resolved.name,
            },
          ]);
        } else if (res.data?.parent?.required) {
          searchParentForms("");
        }
        setStep("review");
      })
      .catch((err) => {
        const data = err?.response?.data;
        if (data && Array.isArray(data.errors)) {
          setErrors(data.errors);
        } else {
          setErrors([
            {
              code: "preflight_failed",
              message: data?.message || text.formBuilderImportPreflightError,
            },
          ]);
        }
      })
      .finally(() => {
        setPreflightLoading(false);
      });
  };

  const beforeUpload = (selectedFile) => {
    if (!selectedFile.name.toLowerCase().endsWith(".json")) {
      setErrors([
        { code: "invalid_file", message: text.formBuilderImportInvalidFile },
      ]);
      return Upload.LIST_IGNORE;
    }
    if (selectedFile.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setErrors([
        {
          code: "file_too_large",
          message: text.formBuilderImportFileTooLarge(MAX_FILE_SIZE_MB),
        },
      ]);
      return Upload.LIST_IGNORE;
    }
    runPreflight(selectedFile);
    return false;
  };

  const onConfirmImport = () => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mode", mode);
    if (preflight?.parent?.required && parentId) {
      formData.append("parent_id", parentId);
    }
    setStep("importing");
    api
      .post("/manage/forms/import", formData)
      .then((res) => {
        setTaskId(res.data.task_id);
      })
      .catch((err) => {
        const data = err?.response?.data;
        setErrors(
          Array.isArray(data?.errors)
            ? data.errors
            : [
                {
                  code: "import_failed",
                  message: data?.message || text.formBuilderImportFailed,
                },
              ]
        );
        setStep("failed");
      });
  };

  // Poll job status while importing
  useEffect(() => {
    if (step !== "importing" || !taskId) {
      return () => {};
    }
    const interval = setInterval(() => {
      api
        .get(`/manage/forms/import/status/${taskId}`)
        .then((res) => {
          const { status, form, errors: jobErrors } = res.data;
          if (status === "done") {
            setImportedForm(form);
            setStep("done");
            if (onImported) {
              onImported();
            }
          } else if (status === "failed") {
            setErrors(
              Array.isArray(jobErrors)
                ? jobErrors
                : [
                    {
                      code: "import_failed",
                      message: text.formBuilderImportFailed,
                    },
                  ]
            );
            setStep("failed");
          }
        })
        .catch(() => {
          // transient polling error — keep polling
        });
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [step, taskId, onImported, text]);

  const parentMissing = preflight?.parent?.required && !parentId;
  const matchExists = preflight?.match?.exists;

  const renderUploadStep = () => (
    <>
      <IssueList
        issues={errors}
        type="error"
        title={text.formBuilderImportErrorsTitle}
      />
      <Spin spinning={preflightLoading}>
        <Dragger
          accept=".json"
          multiple={false}
          showUploadList={false}
          beforeUpload={beforeUpload}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">{text.formBuilderImportDraggerText}</p>
          <p className="ant-upload-hint">
            {text.formBuilderImportDraggerHint(MAX_FILE_SIZE_MB)}
          </p>
        </Dragger>
      </Spin>
    </>
  );

  const renderReviewStep = () => (
    <>
      <p>
        <strong>{text.formBuilderImportFormLabel}:</strong>{" "}
        {preflight?.form?.name} (ID: {preflight?.form?.id})
      </p>
      <IssueList
        issues={preflight?.warnings}
        type="warning"
        title={text.formBuilderImportWarningsTitle}
      />
      {matchExists && (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message={text.formBuilderImportUpdateTitle(
              preflight.match.form?.name
            )}
            description={text.formBuilderImportUpdateDesc(
              preflight.match.form?.submission_count || 0
            )}
          />
          {preflight.match.name_mismatch && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message={text.formBuilderImportNameMismatchWarning}
            />
          )}
          <Radio.Group
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            style={{ marginBottom: 12 }}
          >
            <Space direction="vertical">
              <Radio value="create_or_update">
                {text.formBuilderImportModeUpdate}
              </Radio>
              <Radio value="create_copy">
                {text.formBuilderImportModeCopy}
              </Radio>
            </Space>
          </Radio.Group>
        </>
      )}
      {preflight?.parent?.required && (
        <div style={{ marginBottom: 12 }}>
          <p style={{ marginBottom: 4 }}>
            <strong>{text.formBuilderImportParentLabel}</strong>
          </p>
          {parentMissing && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 8 }}
              message={text.formBuilderImportParentRequired}
            />
          )}
          <Select
            showSearch
            allowClear
            filterOption={false}
            style={{ width: "100%" }}
            placeholder={text.formBuilderImportParentPlaceholder}
            value={parentId}
            options={parentOptions}
            onSearch={searchParentForms}
            onChange={(val) => setParentId(val || null)}
          />
        </div>
      )}
      <Space>
        <Button
          type="primary"
          disabled={parentMissing}
          onClick={onConfirmImport}
        >
          {text.formBuilderImportConfirmButton}
        </Button>
        <Button onClick={resetState}>
          {text.formBuilderImportRetryButton}
        </Button>
      </Space>
    </>
  );

  const renderImportingStep = () => (
    <div style={{ textAlign: "center", padding: "32px 0" }}>
      <Spin size="large" />
      <p style={{ marginTop: 16 }}>{text.formBuilderImportInProgress}</p>
    </div>
  );

  const renderDoneStep = () => (
    <Result
      status="success"
      title={text.formBuilderImportSuccess}
      subTitle={
        importedForm
          ? `${importedForm.name || ""} (${importedForm.action || ""})`
          : null
      }
      extra={[
        importedForm?.id ? (
          <Button
            key="editor"
            type="primary"
            onClick={() => {
              navigate(`/control-center/form-builder/${importedForm.id}/edit`);
            }}
          >
            {text.formBuilderImportOpenEditor}
          </Button>
        ) : null,
        <Button key="close" onClick={onClose}>
          {text.formBuilderImportCloseButton}
        </Button>,
      ].filter(Boolean)}
    />
  );

  const renderFailedStep = () => (
    <>
      <Result status="error" title={text.formBuilderImportFailed} />
      <IssueList
        issues={errors}
        type="error"
        title={text.formBuilderImportErrorsTitle}
      />
      <Space>
        <Button type="primary" onClick={resetState}>
          {text.formBuilderImportRetryButton}
        </Button>
        <Button onClick={onClose}>{text.formBuilderImportCloseButton}</Button>
      </Space>
    </>
  );

  const stepRenderers = {
    upload: renderUploadStep,
    review: renderReviewStep,
    importing: renderImportingStep,
    done: renderDoneStep,
    failed: renderFailedStep,
  };

  return (
    <Modal
      title={text.formBuilderImportModalTitle}
      open={open}
      onCancel={onClose}
      footer={null}
      maskClosable={step !== "importing"}
      closable={step !== "importing"}
      destroyOnClose
    >
      {stepRenderers[step]()}
    </Modal>
  );
};

export default ImportFormModal;
