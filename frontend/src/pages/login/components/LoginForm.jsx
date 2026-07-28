import React, { useState, useMemo } from "react";
import { Form, Input, Button, notification } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { useCookies } from "react-cookie";
import { api, store, uiText } from "../../../lib";
import { useNotification } from "../../../util/hooks";
import { reloadData } from "../../../util/form";

const LoginForm = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [, setCookie] = useCookies(["expiration_time"]);
  const { notify } = useNotification();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
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
        api.setToken(res.data.token);
        setCookie("expiration_time", res.data?.expiration_time);
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
          notify({
            type: "error",
            message: err.response?.data?.message,
          });
        }
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
      <Form.Item>
        <Link className="login-form-forgot" to="/forgot-password">
          Recover Password
        </Link>
      </Form.Item>
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
