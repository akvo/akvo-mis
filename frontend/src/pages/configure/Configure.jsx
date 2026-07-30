import React, { useState } from "react";
import "../login/style.scss";
import { Row, Col, Form, Input, Button, Alert } from "antd";
import { Navigate, useNavigate } from "react-router-dom";
import { api, store } from "../../lib";
import { useNotification } from "../../util/hooks";
import { fetchLevels } from "../../util/level";

// Phase 2: mandatory, and the only screen an unconfigured workspace can
// reach. It names the registrant and creates the hierarchy's top tier plus
// the unit that sits at it, so the root is named properly from birth rather
// than carrying the subdomain as a placeholder.
const Configure = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const { notify } = useNotification();
  const { user: authUser } = store.useState((s) => s);

  // Reached without a session, or after the work is already done: both are
  // wrong turns rather than states this form should render.
  if (!authUser) {
    return <Navigate to="/login" />;
  }
  if (authUser.configured) {
    return <Navigate to="/control-center" />;
  }

  const onFinish = (values) => {
    setLoading(true);
    api
      .post("register/configure", values)
      .then((res) => {
        store.update((s) => {
          s.user = res.data;
        });
        // The tenant now has exactly one level; manage-levels is where they
        // add the tiers below it, so send them straight there.
        fetchLevels().then(() => {
          navigate("/control-center/master-data/levels");
        });
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

  return (
    <div id="login">
      <Row className="wrapper" align="middle">
        <Col span={24} className="right-side">
          <div className="login-form-container">
            <h1>Set up your workspace</h1>
            <Alert
              type="info"
              showIcon
              message="This is a one-off step. Your workspace is not usable until it is done."
              style={{ marginBottom: "1rem" }}
            />
            <Form name="configure-form" layout="vertical" onFinish={onFinish}>
              <Form.Item
                name="first_name"
                label="First Name"
                rules={[{ required: true, message: "First name is required" }]}
              >
                <Input placeholder="First Name" />
              </Form.Item>
              <Form.Item
                name="last_name"
                label="Last Name"
                rules={[{ required: true, message: "Last name is required" }]}
              >
                <Input placeholder="Last Name" />
              </Form.Item>
              <Form.Item
                name="level_0_name"
                label="Name of your top administrative level"
                extra="What you call the widest tier of your hierarchy — for example National, Country or Region. You can add the tiers below it next."
                rules={[
                  { required: true, message: "A level name is required" },
                ]}
              >
                <Input placeholder="National" />
              </Form.Item>
              <Form.Item
                name="root_unit_name"
                label="Name of your top administrative unit"
                extra="The actual place or organisation at that tier — for example Kenya. All of your data will sit beneath it."
                rules={[{ required: true, message: "A unit name is required" }]}
              >
                <Input placeholder="Kenya" />
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  shape="round"
                  loading={loading}
                >
                  Save and continue
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
