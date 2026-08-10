import React, { useState } from "react";
import "../login/style.scss";
import { Row, Col, Form, Input, Button, Typography } from "antd";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../lib";
import { useNotification, useResendActivation } from "../../util/hooks";
import { baseDomainHost } from "../../util/tenant";

const { Title, Text } = Typography;

// Phase 1 of sign-up: just enough to claim a workspace. There is no login
// here — the account is inactive until the emailed link is followed — so the
// form ends on a confirmation state rather than a redirect.
const Register = () => {
  const [loading, setLoading] = useState(false);
  const [sentTo, setSentTo] = useState(null);
  const { notify } = useNotification();
  const { resend, resending } = useResendActivation();
  const [searchParams] = useSearchParams();
  // Registration belongs on the main site, so the suffix is the main
  // site's host — taken from the configuration rather than from the
  // address bar, which was reading back whatever host the browser had
  // wandered onto and offering `<name>.sleman.app.com`. The port still
  // comes from the address bar: local development runs on one and
  // production does not.
  const addressSuffix = `.${baseDomainHost()}`;
  // Arriving from a workspace address that turned out not to exist, the
  // name already typed there is the one being claimed here.
  const suggestedSubdomain = searchParams.get("subdomain") || "";

  const onFinish = (values) => {
    setLoading(true);
    api
      .post("register", {
        email: values.email,
        password: values.password,
        subdomain: values.subdomain,
      })
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

  const onResend = () => {
    resend(sentTo)
      .then(() => {
        notify({
          type: "success",
          message: `Activation email re-sent to ${sentTo}`,
        });
      })
      .catch(() => {
        notify({ type: "error", message: "Could not send the email" });
      });
  };

  if (sentTo) {
    return (
      <div id="login">
        <Row className="wrapper" align="middle">
          <Col span={24} className="right-side">
            <div
              className="login-form-container"
              style={{ textAlign: "center" }}
            >
              <div style={{ fontSize: 46, lineHeight: 1 }}>📬</div>
              <Title level={2}>Check your email</Title>
              <Text type="secondary">
                We sent an activation link to <strong>{sentTo}</strong>. Click
                it to verify your address and finish setting up.
              </Text>
              <div style={{ marginTop: 24 }}>
                <Text type="secondary">
                  Didn&apos;t get it?{" "}
                  <Button
                    type="link"
                    size="small"
                    loading={resending}
                    onClick={onResend}
                    style={{ padding: 0 }}
                  >
                    Resend email
                  </Button>{" "}
                  ·{" "}
                  <Button
                    type="link"
                    size="small"
                    onClick={() => {
                      setSentTo(null);
                    }}
                    style={{ padding: 0 }}
                  >
                    use a different address
                  </Button>
                </Text>
              </div>
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
            <p className="disclaimer">
              Free tier · no credit card. You&apos;ll verify your email next.
            </p>
            <Form
              name="register-form"
              layout="vertical"
              onFinish={onFinish}
              initialValues={{ subdomain: suggestedSubdomain }}
            >
              <Form.Item
                name="email"
                label="Email"
                rules={[
                  {
                    required: true,
                    type: "email",
                    message: "Enter a valid email address.",
                  },
                ]}
              >
                <Input placeholder="you@organisation.org" />
              </Form.Item>
              <Form.Item
                name="password"
                label="Password"
                rules={[
                  { required: true, message: "Password is required" },
                  {
                    min: 8,
                    message: "Password must be at least 8 characters.",
                  },
                ]}
              >
                <Input.Password
                  disabled={loading}
                  placeholder="At least 8 characters"
                />
              </Form.Item>
              <Form.Item
                name="confirm_password"
                label="Confirm password"
                // Validated here rather than server-side: the server only ever
                // receives one password, and a typo caught after the account
                // exists would need a reset to recover from.
                dependencies={["password"]}
                rules={[
                  { required: true, message: "Confirm your password" },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue("password") === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(
                        new Error("The two passwords do not match.")
                      );
                    },
                  }),
                ]}
              >
                <Input.Password
                  disabled={loading}
                  placeholder="Repeat your password"
                />
              </Form.Item>
              <Form.Item
                name="subdomain"
                label="Workspace address"
                extra="Lowercase letters, numbers and hyphens. This becomes your web address and can't be changed later."
                rules={[
                  {
                    required: true,
                    pattern: /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/,
                    message:
                      "Use lowercase letters, numbers and hyphens — no spaces, no leading or trailing hyphen.",
                  },
                ]}
              >
                <Input placeholder="acme" addonAfter={addressSuffix} />
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  shape="round"
                  block
                  loading={loading}
                >
                  Create workspace
                </Button>
              </Form.Item>
              <p className="disclaimer">
                Already have one? <Link to="/login">Sign in</Link>
              </p>
            </Form>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default Register;
