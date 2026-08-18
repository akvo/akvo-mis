import React, { useState, useMemo } from "react";
import { Form, Input, Button, notification, Alert } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { api, store, uiText } from "../../../lib";
import { useNotification, useResendActivation } from "../../../util/hooks";
import { reloadData } from "../../../util/form";
import { onBaseDomainHost } from "../../../util/tenant";

const LoginForm = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [unverifiedEmail, setUnverifiedEmail] = useState(null);
  const { notify } = useNotification();
  const { resend, resending } = useResendActivation();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  // Sign-up belongs to the main site — a workspace already exists, and
  // its login page has nothing to offer someone without an account. Read
  // from the host rather than from the tenant in the store, which is
  // null both before the lookup answers (so the link appeared and then
  // vanished on every load) and on a workspace that does not exist.
  const showRegister = onBaseDomainHost();
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const onFinish = (values) => {
    setLoading(true);
    api
      .post("login", {
        email: values.email,
        password: values.password,
      })
      .then((res) => {
        // The server's AUTH_TOKEN cookie carries the expiry the browser
        // enforces; nothing here records it a second time.
        api.setToken(res.data.token);
        if (res.data.forms.length === 0 && !res.data?.is_superuser) {
          notification.open({
            message: text.contactAdmin,
            description: text.formAssignmentError,
          });
        }
        store.update((s) => {
          s.isLoggedIn = true;
          s.selectedForm = null;
          s.user = res.data;
        });
        reloadData(res.data);
        setLoading(false);
        navigate("/control-center");
      })
      .catch((err) => {
        if (err.response.status === 401 || err.response.status === 400) {
          setLoading(false);
          // The backend flags a correct password on an account that never
          // followed its activation link. Offering the resend here is the
          // difference between a dead end and a way forward.
          if (err.response?.data?.unverified) {
            setUnverifiedEmail(values.email);
          }
          notify({
            type: "error",
            message: err.response?.data?.message,
          });
        }
      });
  };

  const onResend = () => {
    resend(unverifiedEmail)
      .then(() => {
        setUnverifiedEmail(null);
        notify({
          type: "success",
          message: "Activation email sent — check your inbox",
        });
      })
      .catch(() => {
        notify({ type: "error", message: "Could not send the email" });
      });
  };

  return (
    <Form
      name="login-form"
      layout="vertical"
      initialValues={{
        remember: true,
      }}
      onFinish={onFinish}
    >
      <Form.Item
        name="email"
        label="Email Address"
        rules={[
          {
            required: true,
            message: text.usernameRequired,
          },
        ]}
      >
        <Input placeholder="Email" />
      </Form.Item>
      <Form.Item
        name="password"
        label="Password"
        disabled={loading}
        rules={[
          {
            required: true,
            message: text.passwordRequired,
          },
        ]}
      >
        <Input.Password disabled={loading} placeholder="Password" />
      </Form.Item>
      {unverifiedEmail && (
        <Alert
          type="warning"
          showIcon
          message="This account has not been activated yet"
          description={
            <Button
              type="link"
              size="small"
              loading={resending}
              onClick={onResend}
              style={{ padding: 0 }}
            >
              Resend the activation email
            </Button>
          }
          style={{ marginBottom: "1rem" }}
        />
      )}
      <Form.Item>
        <Link className="login-form-forgot" to="/forgot-password">
          Recover Password
        </Link>
      </Form.Item>
      {showRegister && (
        <Form.Item>
          <Link className="login-form-forgot" to="/register">
            Create an account
          </Link>
        </Form.Item>
      )}
      <Form.Item>
        <Link className="login-form-forgot" to="/register">
          Create an account
        </Link>
      </Form.Item>
      <Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          shape="round"
          loading={loading}
        >
          Log in
        </Button>
      </Form.Item>
      <p className="disclaimer">{text.accountDisclaimer}</p>
    </Form>
  );
};

export default LoginForm;
