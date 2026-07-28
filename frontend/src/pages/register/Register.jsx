import React, { useState } from "react";
import "../login/style.scss";
import { Row, Col, Form, Input, Button } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { useCookies } from "react-cookie";
import { api, store } from "../../lib";
import { useNotification } from "../../util/hooks";
import { reloadData } from "../../util/form";

const Register = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [, setCookie] = useCookies(["expiration_time"]);
  const { notify } = useNotification();

  const onFinish = (values) => {
    setLoading(true);
    api
      .post("register", {
        email: values.email,
        password: values.password,
        first_name: values.first_name,
        last_name: values.last_name,
        subdomain: values.subdomain,
      })
      .then((res) => {
        // Mirror the login success path: token, expiry cookie, store.
        api.setToken(res.data.token);
        setCookie("expiration_time", res.data?.expiration_time);
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
        setLoading(false);
        notify({
          type: "error",
          message: err.response?.data?.message || "Registration failed",
        });
      });
  };

  return (
    <div id="login">
      <Row className="wrapper" align="middle">
        <Col span={24} className="right-side">
          <div className="login-form-container">
            <h1>Create your workspace</h1>
            <Form name="register-form" layout="vertical" onFinish={onFinish}>
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
