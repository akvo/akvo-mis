import React, { useRef, useState } from "react";
import "../login/style.scss";
import {
  Row,
  Col,
  Form,
  Input,
  Button,
  Alert,
  Steps,
  Tag,
  Typography,
  Upload,
} from "antd";
import { UploadOutlined, LoadingOutlined } from "@ant-design/icons";
import { Navigate, useNavigate } from "react-router-dom";
import { api, store, validateLogoFile, LOGO_ACCEPT_TYPES } from "../../lib";
import { useNotification } from "../../util/hooks";
import { fetchLevels } from "../../util/level";

const { Title, Text } = Typography;

// Phase 2: mandatory, and the only screen an unconfigured workspace can reach.
// It names the registrant and creates the hierarchy's top tier plus the unit
// that sits at it, so the root is named properly from birth rather than
// carrying the subdomain as a placeholder.
const Configure = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(null);
  const [logoFileList, setLogoFileList] = useState([]);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const justFinished = useRef(false);
  // Watched rather than mirrored into state: the preview is what makes the
  // tier/unit distinction concrete before the names are committed, and the
  // form already holds those values.
  const [form] = Form.useForm();
  const level0Name = Form.useWatch("level_0_name", form);
  const rootUnitName = Form.useWatch("root_unit_name", form);
  const { notify } = useNotification();
  const { user: authUser } = store.useState((s) => s);

  const beforeUpload = (file) => {
    if (!validateLogoFile(file, notify)) {
      return Upload.LIST_IGNORE;
    }
    return true;
  };

  const handleLogoUpload = ({ file, onSuccess, onError }) => {
    setUploadingLogo(true);
    const formData = new FormData();
    formData.append("file", file);
    api
      .post("upload/logo", formData)
      .then((res) => {
        setUploadingLogo(false);
        const filePath = res.data.file.startsWith("http")
          ? new URL(res.data.file).pathname
          : res.data.file;
        form.setFieldsValue({ logo: filePath });
        const thumbUrl =
          typeof window !== "undefined" && window.URL?.createObjectURL
            ? window.URL.createObjectURL(file)
            : filePath;
        setLogoFileList([
          {
            uid: "-1",
            name: file.name,
            status: "done",
            url: filePath,
            thumbUrl,
          },
        ]);
        store.update((s) => {
          if (s.tenant) {
            s.tenant.logo = filePath;
          }
        });
        onSuccess(res.data);
      })
      .catch((err) => {
        setUploadingLogo(false);
        notify({
          type: "error",
          message: err.response?.data?.message || "Failed to upload logo",
        });
        onError(err);
      });
  };

  const handleLogoRemove = () => {
    form.setFieldsValue({ logo: null });
    setLogoFileList([]);
    store.update((s) => {
      if (s.tenant) {
        s.tenant.logo = null;
      }
    });
  };

  // Reached without a session, or after the work is already done: both are
  // wrong turns rather than states this form should render.
  if (!authUser) {
    return <Navigate to="/login" />;
  }
  // A ref, not the `done` state below. Saving marks the workspace configured
  // and updates the store, which re-renders this component before the state
  // that records completion has been set — so a state flag would still read
  // as "arrived here already configured" and bounce the person who just
  // filled the form out to the dashboard, past the hand-off to level
  // management. A ref is written the moment the response lands.
  if (authUser.configured && !justFinished.current) {
    return <Navigate to="/control-center" />;
  }

  const onFinish = (values) => {
    setLoading(true);
    api
      .post("register/configure", values)
      .then((res) => {
        justFinished.current = true;
        store.update((s) => {
          s.user = res.data;
          if (s.tenant && values.logo) {
            s.tenant.logo = values.logo;
          }
        });
        setDone({
          firstName: values.first_name,
          level0: values.level_0_name,
          root: values.root_unit_name,
        });
        // The tenant's levels have changed; refreshing the store is not
        // something the confirmation should wait on.
        fetchLevels();
      })
      .catch((err) => {
        setLoading(false);
        notify({
          type: "error",
          message:
            err.response?.data?.message || "Could not save your workspace",
        });
      });
  };

  if (done) {
    return (
      <div id="login">
        <Row className="wrapper" align="middle">
          <Col span={24} className="right-side">
            <div
              className="login-form-container wide"
              style={{ textAlign: "center" }}
            >
              <div style={{ fontSize: 46, lineHeight: 1 }}>🎉</div>
              <Title level={2}>You&apos;re all set</Title>
              <Text type="secondary">
                Welcome, {done.firstName}. Your workspace is ready with{" "}
                <strong>
                  {done.level0}: {done.root}
                </strong>{" "}
                at the top. Next, add the tiers beneath it.
              </Text>
              <Button
                type="primary"
                shape="round"
                block
                style={{ marginTop: 24 }}
                onClick={() => {
                  navigate("/control-center/master-data/levels");
                }}
              >
                Continue to Level management →
              </Button>
            </div>
          </Col>
        </Row>
      </div>
    );
  }

  return (
    <div id="login">
      <Row className="wrapper" align="middle">
        <Col span={24} className="right-side">
          <div className="login-form-container wide">
            {/* Labels sit under their dots rather than beside them: four
                steps beside their dots truncate ("Configu…") at any width
                this card can reasonably take. `responsive` is off so the
                indicator cannot flip to a full vertical stack mid-layout. */}
            <Steps
              size="small"
              current={2}
              responsive={false}
              labelPlacement="vertical"
              style={{ marginBottom: 28 }}
              items={[
                { title: "Sign up" },
                { title: "Verify email" },
                { title: "Configure project" },
                { title: "Dashboard" },
              ]}
            />
            <h1>Set up your project</h1>
            <p className="disclaimer">
              This names your administrative hierarchy. You can add deeper tiers
              afterwards; these two top-level names are set once here.
            </p>
            <Form
              form={form}
              name="configure-form"
              layout="vertical"
              onFinish={onFinish}
            >
              <Row gutter={14}>
                <Col span={12}>
                  <Form.Item
                    name="first_name"
                    label="First name"
                    rules={[{ required: true, message: "Required" }]}
                  >
                    <Input placeholder="Jane" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="last_name"
                    label="Last name"
                    rules={[{ required: true, message: "Required" }]}
                  >
                    <Input placeholder="Doe" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item
                name="level_0_name"
                label="Top level name"
                extra="The label for your highest administrative tier — e.g. Country, National, or Region. Not a place, a tier."
                rules={[
                  { required: true, message: "Give your top tier a name." },
                ]}
              >
                <Input placeholder="Country" />
              </Form.Item>
              <Form.Item
                name="root_unit_name"
                label="Top unit name"
                extra="Your single top unit at that tier — e.g. Kenya. Everything you upload later sits under it."
                rules={[{ required: true, message: "Name your top unit." }]}
              >
                <Input placeholder="Kenya" />
              </Form.Item>
              <Form.Item
                name="logo"
                label="Workspace logo"
                extra="Optional. PNG, JPG, or JPEG up to 2MB. Displayed in the top navigation and login page."
              >
                <Upload
                  name="file"
                  listType="picture"
                  maxCount={1}
                  fileList={logoFileList}
                  beforeUpload={beforeUpload}
                  customRequest={handleLogoUpload}
                  onRemove={handleLogoRemove}
                  accept={LOGO_ACCEPT_TYPES}
                >
                  {logoFileList.length < 1 && (
                    <Button
                      icon={
                        uploadingLogo ? <LoadingOutlined /> : <UploadOutlined />
                      }
                      loading={uploadingLogo}
                    >
                      Upload logo
                    </Button>
                  )}
                </Upload>
              </Form.Item>

              <Alert
                type="info"
                showIcon
                message="Preview — this is the hierarchy you're creating:"
                style={{ marginBottom: 8 }}
              />
              <div
                style={{
                  background: "#fafafa",
                  border: "1px solid #f0f0f0",
                  padding: "14px 16px",
                  marginBottom: 24,
                }}
              >
                <div>
                  <Tag>Level 0</Tag>
                  <strong>{level0Name || "—"}</strong>
                </div>
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary" style={{ marginRight: 8 }}>
                    └ top unit
                  </Text>
                  <strong>{rootUnitName || "—"}</strong>
                </div>
              </div>

              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  shape="round"
                  block
                  loading={loading}
                >
                  Finish setup
                </Button>
              </Form.Item>
            </Form>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default Configure;
