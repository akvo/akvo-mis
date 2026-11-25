import React, { useEffect, useMemo, useRef, useState } from "react";
import "../login/style.scss";
import { Row, Col, Button, Form, Input, Spin, Typography } from "antd";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, store, uiText } from "../../lib";
import { useNotification, useResendActivation } from "../../util/hooks";
import { reloadData } from "../../util/form";
import { fetchLevels } from "../../util/level";
import AuthShell from "../landing/AuthShell";

const { Title, Text } = Typography;

// The landing page for the emailed activation link. It consumes the token and
// adopts the session the backend hands back, then confirms before handing off
// to configuration — the confirmation is the only moment the registrant is
// told their address is verified, so it is worth a screen of its own.
const Activate = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const [verified, setVerified] = useState(false);
  // null while verifying, then "expired" (the API rejected the token)
  // or "error" (we never got an answer).
  const [failed, setFailed] = useState(null);
  const [resent, setResent] = useState(false);
  const { notify } = useNotification();
  const { resend, resending } = useResendActivation();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  // Fire exactly once. Listing dependencies is not enough on its own: an
  // effect that re-runs when this component sets its own state would POST the
  // activation again on every render.
  const started = useRef(false);
  useEffect(() => {
    if (started.current) {
      return;
    }
    started.current = true;
    // LP-002 B5: an onboarding-wizard sign-up staged its answers on the tenant
    // (res.data.onboarding); configure the workspace automatically from them and
    // drop the visitor into the control center. Any failure falls back to the
    // manual /configure form (no regression). Defined inside the effect so it is
    // not an extra dependency.
    const autoConfigure = (meta, user) => {
      const parts = (meta.adminName || user.name || "").trim().split(/\s+/);
      const firstName = (parts.shift() || user.name || "Admin").slice(0, 50);
      const lastName = (parts.join(" ") || "-").slice(0, 50);
      api
        .post("register/configure", {
          first_name: firstName,
          last_name: lastName,
          level_0_name: "Country",
          root_unit_name: meta.place,
          organisation: meta.org || "",
        })
        .then((res) => {
          store.update((s) => {
            s.user = res.data;
          });
          reloadData(res.data);
          // App's levels request can finish before configure creates level 0,
          // leaving the store's hierarchy empty until a reload; refresh it now,
          // as the manual Configure page does after a successful save.
          fetchLevels();
          navigate("/control-center");
        })
        .catch(() => {
          navigate("/configure");
        });
    };
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
        const meta = res.data.onboarding || {};
        if (!res.data.configured && meta.place) {
          autoConfigure(meta, res.data);
        } else {
          setVerified(true);
        }
      },
      (err) => {
        // Only a 400 means the link itself is bad. An unreachable
        // backend or an unresolved workspace is a different problem,
        // and blaming the link sends the visitor to a resend that
        // cannot help them.
        setFailed(err?.response?.status === 400 ? "expired" : "error");
      }
    );
  }, [token, navigate]);

  const onResend = (values) => {
    resend(values.email)
      .then(() => {
        setResent(true);
      })
      .catch(() => {
        notify({ type: "error", message: text.couldNotSendEmail });
      });
  };

  const frame = (children) => (
    <AuthShell>
      <div id="login">
        <Row className="wrapper" align="middle">
          <Col span={24} className="right-side">
            <div
              className="login-form-container"
              style={{ textAlign: "center" }}
            >
              {children}
            </div>
          </Col>
        </Row>
      </div>
    </AuthShell>
  );

  if (verified) {
    return frame(
      <>
        <div style={{ fontSize: 46, lineHeight: 1, color: "#52c41a" }}>✓</div>
        <Title level={2}>{text.activateVerifiedTitle}</Title>
        <Text type="secondary">{text.activateVerifiedDesc}</Text>
        <Button
          type="primary"
          shape="round"
          block
          style={{ marginTop: 24 }}
          onClick={() => {
            navigate("/configure");
          }}
        >
          {text.activateContinueSetup}
        </Button>
      </>
    );
  }

  if (!failed) {
    return frame(
      <>
        <Spin size="large" />
        <Title level={2} style={{ marginTop: 16 }}>
          {text.activateVerifying}
        </Title>
      </>
    );
  }

  if (resent) {
    return frame(
      <>
        <div style={{ fontSize: 46, lineHeight: 1, color: "#52c41a" }}>✓</div>
        <Title level={2}>{text.activateCheckInboxTitle}</Title>
        <Text type="secondary">{text.activateCheckInboxDesc}</Text>
        <Link to="/login">
          <Button type="primary" shape="round" block style={{ marginTop: 24 }}>
            {text.backToLogin}
          </Button>
        </Link>
      </>
    );
  }

  if (failed === "error") {
    return frame(
      <>
        <div style={{ fontSize: 46, lineHeight: 1, color: "#ff4d4f" }}>!</div>
        <Title level={2}>{text.activateErrorTitle}</Title>
        <Text type="secondary">{text.activateErrorDesc}</Text>
        <Button
          type="primary"
          shape="round"
          block
          style={{ marginTop: 24 }}
          onClick={() => {
            window.location.reload();
          }}
        >
          {text.activateTryAgain}
        </Button>
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
            <h1 style={{ textAlign: "center" }}>{text.activateExpiredTitle}</h1>
            <p className="disclaimer">{text.activateExpiredDesc}</p>
            <Form
              name="resend-activation-form"
              layout="vertical"
              onFinish={onResend}
            >
              {/* The address has to be asked for: an unreadable token yields
                  no account to look it up from. */}
              <Form.Item
                name="email"
                label={text.userEmail}
                rules={[
                  {
                    required: true,
                    type: "email",
                    message: text.valEmail,
                  },
                ]}
              >
                <Input placeholder={text.activateEmailPlaceholder} />
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  shape="round"
                  block
                  loading={resending}
                >
                  {text.loginResendActivation}
                </Button>
              </Form.Item>
              <p className="disclaimer">
                <Link to="/login">{text.backToLogin}</Link>
              </p>
            </Form>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default Activate;
