import React, { useState } from "react";
import "../login/style.scss";
import { Row, Col, Form, Input, Button, Result } from "antd";
import { Link } from "react-router-dom";
import { api } from "../../lib";
import { useNotification } from "../../util/hooks";

// Phase 1 of sign-up: just enough to claim a workspace. There is no login
// here — the account is inactive until the emailed link is followed — so the
// form ends on a confirmation state rather than a redirect.
const Register = () => {
  const [loading, setLoading] = useState(false);
  const [sentTo, setSentTo] = useState(null);
  const { notify } = useNotification();

  const onFinish = (values) => {
    setLoading(true);
    api
      .post("register", values)
      .then(() => {
        setSentTo(values.email);
      })
      .catch((err) => {
        notify({
          type: "error",
          message: err.response?.data?.message || "Registration failed",
        });
      })
      .finally(() => {
        setLoading(false);
      });
  };

  if (sentTo) {
    return (
      <div id="login">
        <Row className="wrapper" align="middle">
          <Col span={24} className="right-side">
            <div className="login-form-container">
              <Result
                status="success"
                title="Check your email"
                subTitle={`We sent an activation link to ${sentTo}. Follow it to finish setting up your workspace.`}
                extra={
                  <Link to="/login">
                    <Button type="primary" shape="round">
                      Back to login
                    </Button>
                  </Link>
                }
              />
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
          <div className="login-form-container">
            <h1>Create your workspace</h1>
            <Form name="register-form" layout="vertical" onFinish={onFinish}>
              <Form.Item
                name="email"
                label="Email Address"
                extra="We will send an activation link to this address"
                rules={[
                  {
                    required: true,
                    type: "email",
                    message: "A valid email is required",
                  },
                ]}
              >
                <Input placeholder="Email" />
              </Form.Item>
              <Form.Item
                name="password"
                label="Password"
                rules={[{ required: true, message: "Password is required" }]}
              >
                <Input.Password disabled={loading} placeholder="Password" />
              </Form.Item>
              <Form.Item
                name="subdomain"
                label="Subdomain"
                extra="Lowercase letters, digits and hyphens only"
                rules={[
                  {
                    required: true,
                    pattern: /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/,
                    message:
                      "Use lowercase letters, digits and hyphens; no leading or trailing hyphen",
                  },
                ]}
              >
                <Input placeholder="your-organisation" />
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  shape="round"
                  loading={loading}
                >
                  Register
                </Button>
              </Form.Item>
              <p className="disclaimer">
                <Link to="/login">Already have an account? Log in</Link>
              </p>
            </Form>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default Register;
