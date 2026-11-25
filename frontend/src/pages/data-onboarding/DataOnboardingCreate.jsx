import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Upload } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { Breadcrumbs } from "../../components";
import { api, store, uiText } from "../../lib";

const DataOnboardingCreate = () => {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const { active: activeLang } = store.useState((s) => s.language);
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const pagePath = [
    { title: text.controlCenter, link: "/control-center" },
    { title: text.menuFormBuilder, link: "/control-center/form-builder" },
    {
      title: text.dataOnboardingHistory,
      link: "/control-center/data-onboarding",
    },
    { title: text.formBuilderDataOnboardingButton },
  ];

  const onUpload = (file) => {
    const formData = new FormData();
    formData.append("file", file);
    setUploading(true);
    setError(null);
    api
      .post("/data-onboarding", formData)
      .then((res) => {
        navigate(`/control-center/data-onboarding/${res.data.id}`);
      })
      .catch((err) => {
        setError(err.response?.data?.message || text.dataOnboardingFailed);
        setUploading(false);
      });
    // The file is sent above, not by antd's own uploader.
    return false;
  };

  return (
    <div id="data-onboarding-create">
      <div className="description-container">
        <Breadcrumbs pagePath={pagePath} />
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          {error && (
            <Alert
              type="error"
              showIcon
              message={error}
              style={{ marginBottom: 16 }}
            />
          )}
          <Upload.Dragger
            accept=".csv,.xlsx"
            multiple={false}
            showUploadList={false}
            disabled={uploading}
            beforeUpload={onUpload}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">{text.dataOnboardingUploadHint}</p>
          </Upload.Dragger>
        </div>
      </div>
    </div>
  );
};

export default DataOnboardingCreate;
