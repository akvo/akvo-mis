import React, { useEffect, useRef, useState } from "react";
import "../login/style.scss";
import { Row, Col, Button, Form, Input, Spin, Typography } from "antd";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, store } from "../../lib";
import { useNotification, useResendActivation } from "../../util/hooks";
import { reloadData } from "../../util/form";

const { Title, Text } = Typography;

// The landing page for the emailed activation link. It consumes the token and
// adopts the session the backend hands back, then confirms before handing off
// to configuration — the confirmation is the only moment the registrant is
// told their address is verified, so it is worth a screen of its own.
const Activate = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const [verified, setVerified] = useState(false);
  const [failed, setFailed] = useState(false);
  const [resent, setResent] = useState(false);
  const { notify } = useNotification();
  const { resend, resending } = useResendActivation();

  // Fire exactly once. Listing dependencies is not enough on its own: an
  // effect that re-runs when this component sets its own state would POST the
  // activation again on every render.
  const started = useRef(false);
  useEffect(() => {
    if (started.current) {
      return;
    }
    started.current = true;
    // Two-argument then, not .catch: only a rejected *request* means the link
    // is bad. A .catch here would also swallow anything thrown while adopting
    // the session, and tell an already-activated user their link had expired —
    // sending them to ask for another one they do not need.
    api.post("register/activate", { token }).then(
      (res) => {
        // Same session shape as login, so the app is fully signed in.
        api.setToken(res.data.token);
        store.update((s) => {
          s.isLoggedIn = true;
          s.selectedForm = null;
          s.user = res.data;
        });
        reloadData(res.data);
        setVerified(true);
      },
      () => {
        setFailed(true);
      }
    );
  }, [token]);

  const onResend = (values) => {
    resend(values.email)
      .then(() => {
        setResent(true);
      })
      .catch(() => {
        notify({ type: "error", message: "Could not send the email" });
      });
  };

  const frame = (children) => (
    <div id="login">
      <Row className="wrapper" align="middle">
        <Col span={24} className="right-side">
          <div className="login-form-container" style={{ textAlign: "center" }}>
            {children}
          </div>
        </Col>
      </Row>
    </div>
  );

  if (verified) {
    return frame(
      <>
        <div style={{ fontSize: 46, lineHeight: 1, color: "#52c41a" }}>✓</div>
        <Title level={2}>Email verified</Title>
        <Text type="secondary">
          Your account is active. One quick step left — tell us about your
          project.
        </Text>
        <Button
          type="primary"
          shape="round"
          block
          style={{ marginTop: 24 }}
          onClick={() => {
            navigate("/configure");
          }}
        >
          Continue to setup →
        </Button>
      </>
    );
  }

  if (!failed) {
    return frame(
      <>
        <Spin size="large" />
        <Title level={2} style={{ marginTop: 16 }}>
          Verifying your email…
        </Title>
      </>
    );
  }

  if (resent) {
    return frame(
      <>
        <div style={{ fontSize: 46, lineHeight: 1, color: "#52c41a" }}>✓</div>
        <Title level={2}>Check your inbox</Title>
        <Text type="secondary">
          If that account still needs activating, a fresh link is on its way.
        </Text>
        <Link to="/login">
          <Button type="primary" shape="round" block style={{ marginTop: 24 }}>
            Back to login
          </Button>
        </Link>
      </>
    );
  }

  return (
    <div id="login">
      <Row className="wrapper" align="middle">
        <Col span={24} className="right-side">
          <div className="login-form-container">
            <div
              style={{
                fontSize: 46,
                lineHeight: 1,
                color: "#faad14",
                textAlign: "center",
              }}
            >
              ⏱
            </div>
            <h1 style={{ textAlign: "center" }}>This link has expired</h1>
            <p className="disclaimer">
              Activation links are valid for 7 days. Request a fresh one and
              we&apos;ll email it right away.
            </p>
            <Form
              name="resend-activation-form"
              layout="vertical"
              onFinish={onResend}
            >
              {/* The address has to be asked for: an unreadable token yields
                  no account to look it up from. */}
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
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  shape="round"
                  block
                  loading={resending}
                >
                  Resend activation email
                </Button>
              </Form.Item>
              <p className="disclaimer">
                <Link to="/login">Back to login</Link>
              </p>
            </Form>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default Activate;
