import React, { useEffect, useRef, useState } from "react";
import "../login/style.scss";
import { Row, Col, Button, Form, Input, Result, Spin } from "antd";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useCookies } from "react-cookie";
import { api, store } from "../../lib";
import { useNotification } from "../../util/hooks";
import { reloadData } from "../../util/form";

// The landing page for the emailed activation link. It consumes the token,
// adopts the session the backend hands back, and moves straight on to the
// configuration form — the link is the only thing standing between sign-up
// and a usable workspace, so there is nothing to confirm here.
const Activate = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const [, setCookie] = useCookies(["expiration_time"]);
  const [failed, setFailed] = useState(false);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const { notify } = useNotification();

  // Fire exactly once. `setCookie` and `navigate` are not guaranteed to keep
  // their identity between renders, so an effect that merely lists them as
  // dependencies re-runs when this component sets its own state — which here
  // would mean POSTing the activation again on every render.
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
        setCookie("expiration_time", res.data?.expiration_time);
        store.update((s) => {
          s.isLoggedIn = true;
          s.selectedForm = null;
          s.user = res.data;
        });
        reloadData(res.data);
        navigate("/configure");
      },
      () => {
        setFailed(true);
      }
    );
  }, [token, navigate, setCookie]);

  const onResend = (values) => {
    setResending(true);
    api
      .post("register/resend-activation", { email: values.email })
      .then(() => {
        setResent(true);
      })
      .catch(() => {
        notify({ type: "error", message: "Could not send the email" });
      })
      .finally(() => {
        setResending(false);
      });
  };

  if (!failed) {
    return (
      <div id="login">
        <Row className="wrapper" align="middle" justify="center">
          <Col>
            <Spin size="large" tip="Activating your account…" />
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
            {resent ? (
              <Result
                status="success"
                title="Activation email sent"
                subTitle="Check your inbox for a fresh link."
                extra={
                  <Link to="/login">
                    <Button type="primary" shape="round">
                      Back to login
                    </Button>
                  </Link>
                }
              />
            ) : (
              <>
                <h1>This link has expired</h1>
                <p>
                  Activation links are valid for seven days. Enter your email
                  address and we will send a new one.
                </p>
                <Form
                  name="resend-activation-form"
                  layout="vertical"
                  onFinish={onResend}
                >
                  <Form.Item
                    name="email"
                    label="Email Address"
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
                  <Form.Item>
                    <Button
                      type="primary"
                      htmlType="submit"
                      shape="round"
                      loading={resending}
                    >
                      Resend activation email
                    </Button>
                  </Form.Item>
                </Form>
                <p className="disclaimer">
                  <Link to="/login">Back to login</Link>
                </p>
              </>
            )}
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default Activate;
