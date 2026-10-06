import React, { useMemo, useState } from "react";
import PropTypes from "prop-types";
import { Modal, Button, Upload, Space, Typography, Popconfirm } from "antd";
import {
  UploadOutlined,
  DeleteOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import { api, config, store, uiText } from "../../lib";
import { useNotification } from "../../util/hooks";
import { fetchTenant } from "../../util/tenant";

const { Text } = Typography;

const BrandingModal = ({ open, onClose }) => {
  const { language, tenant } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);
  const { notify } = useNotification();

  const [uploading, setUploading] = useState(false);
  const [removing, setRemoving] = useState(false);

  const beforeUpload = (file) => {
    const allowedTypes = [
      "image/png",
      "image/jpeg",
      "image/jpg",
      "image/svg+xml",
    ];
    const isAllowed = allowedTypes.includes(file.type);
    const isLt2M = file.size / (1024 * 1024) <= 2;
    if (!isAllowed) {
      notify({
        type: "error",
        message: "Only PNG, JPG, JPEG, and SVG files are allowed.",
      });
      return Upload.LIST_IGNORE;
    }
    if (!isLt2M) {
      notify({
        type: "error",
        message: "Image must be smaller than 2MB.",
      });
      return Upload.LIST_IGNORE;
    }
    return true;
  };

  const handleUpload = ({ file, onSuccess, onError }) => {
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    api
      .post("upload/logo", formData)
      .then((uploadRes) => {
        const filePath = uploadRes.data.file.startsWith("http")
          ? new URL(uploadRes.data.file).pathname
          : uploadRes.data.file;
        return api.put("tenant/branding", { logo: filePath }).then((res) => {
          setUploading(false);
          store.update((s) => {
            if (s.tenant) {
              s.tenant.logo = res.data.logo;
            }
          });
          fetchTenant();
          notify({
            type: "success",
            message: text.brandingUploadSuccess,
          });
          onSuccess(res.data);
        });
      })
      .catch((err) => {
        setUploading(false);
        notify({
          type: "error",
          message: err.response?.data?.message || text.brandingUploadError,
        });
        onError(err);
      });
  };

  const handleRemove = () => {
    setRemoving(true);
    api
      .delete("tenant/branding")
      .then(() => {
        setRemoving(false);
        store.update((s) => {
          if (s.tenant) {
            s.tenant.logo = null;
          }
        });
        fetchTenant();
        notify({
          type: "success",
          message: text.brandingRemoveSuccess,
        });
      })
      .catch((err) => {
        setRemoving(false);
        notify({
          type: "error",
          message: err.response?.data?.message || text.brandingRemoveError,
        });
      });
  };

  return (
    <Modal
      title={text.brandingModalTitle}
      visible={open}
      onCancel={onClose}
      footer={null}
    >
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 140,
            height: 140,
            background: "#fafafa",
            border: "1px solid #d9d9d9",
            borderRadius: 8,
            padding: 8,
            marginBottom: 12,
          }}
        >
          <img
            src={tenant?.logo || config.siteLogo}
            alt="Workspace Logo"
            style={{
              maxWidth: "100%",
              maxHeight: "100%",
              objectFit: "contain",
            }}
            onError={(e) => {
              e.target.onerror = null;
              e.target.src = config.siteLogo;
            }}
          />
        </div>
        <div>
          <Text type="secondary">
            {tenant?.logo ? text.brandingCurrentLogo : text.brandingNoLogo}
          </Text>
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <Text type="secondary">{text.brandingLogoHint}</Text>
      </div>

      <Space>
        <Upload
          name="file"
          showUploadList={false}
          beforeUpload={beforeUpload}
          customRequest={handleUpload}
          accept=".png,.jpg,.jpeg,.svg,image/png,image/jpeg,image/svg+xml"
        >
          <Button
            type="primary"
            icon={uploading ? <LoadingOutlined /> : <UploadOutlined />}
            loading={uploading}
          >
            {text.brandingUploadBtn}
          </Button>
        </Upload>

        {Boolean(tenant?.logo) && (
          <Popconfirm
            title="Are you sure you want to remove the custom logo?"
            onConfirm={handleRemove}
            okText="Yes"
            cancelText="No"
          >
            <Button
              danger
              icon={removing ? <LoadingOutlined /> : <DeleteOutlined />}
              loading={removing}
            >
              {text.brandingRemoveBtn}
            </Button>
          </Popconfirm>
        )}
      </Space>
    </Modal>
  );
};

BrandingModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};

export default BrandingModal;
