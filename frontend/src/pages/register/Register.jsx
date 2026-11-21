import React, { useEffect, useRef, useState } from "react";
import "../login/style.scss";
import { Row, Col, Form, Input, Select, Button, Typography } from "antd";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../lib";
import { useNotification, useResendActivation } from "../../util/hooks";
import { baseDomainHost } from "../../util/tenant";
import { useTranslation } from "../../lib/i18n";

const { Title, Text } = Typography;

const LANGUAGE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
  { value: "fr", label: "Français" },
];

// Cloudflare's widget is a script and a div, so there is no npm
// dependency here. It loads from this component rather than from
// index.html because index.html is every page of every workspace,
// while this form is one route on the base domain.
const TURNSTILE_SCRIPT =
  "https://challenges.cloudflare.com/turnstile/v0/api.js";

// Keys the API may return in `details` that correspond to inputs on
// this form. Anything else has no field to land on and stays a toast.
const FORM_FIELDS = ["email", "password", "subdomain", "language", "name"];

// Phase 1 of sign-up: just enough to claim a workspace. There is no login
// here — the account is inactive until the emailed link is followed — so the
// form ends on a confirmation state rather than a redirect.
const Register = () => {
  const [loading, setLoading] = useState(false);
  const [sentTo, setSentTo] = useState(null);
  const [form] = Form.useForm();
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

  // Empty on any deployment without a site key, which is the default
  // and means no captcha at all.
  const siteKey = window?.appConfig?.turnstileSiteKey || "";
  const widgetRef = useRef(null);
  const widgetIdRef = useRef(null);
  const [captchaToken, setCaptchaToken] = useState("");
  // Held here rather than in the antd form: FORM_FIELDS drives
  // form.setFields, which needs a registered antd field, and this
  // control is Cloudflare's iframe rather than an Input.
  const [captchaError, setCaptchaError] = useState("");
  const c = useTranslation("register");

  useEffect(() => {
    if (!siteKey) {
      return () => {};
    }
    let cancelled = false;
    const renderWidget = () => {
      if (
        cancelled ||
        !widgetRef.current ||
        widgetIdRef.current !== null ||
        !window.turnstile
      ) {
        return;
      }
      widgetIdRef.current = window.turnstile.render(widgetRef.current, {
        sitekey: siteKey,
        callback: (value) => {
          setCaptchaToken(value);
        },
        // A solved widget whose token has expired looks solved. Clear
        // the token so the next submit is refused by the server with a
        // message, rather than silently sending a stale one.
        "expired-callback": () => {
          setCaptchaToken("");
        },
        "error-callback": () => {
          setCaptchaToken("");
        },
      });
    };
    if (window.turnstile) {
      renderWidget();
    } else {
      const script = document.createElement("script");
      script.src = TURNSTILE_SCRIPT;
      script.async = true;
      script.onload = renderWidget;
      document.head.appendChild(script);
    }
    return () => {
      cancelled = true;
    };
  }, [siteKey]);

  const resetCaptcha = () => {
    if (window.turnstile && widgetIdRef.current !== null) {
      window.turnstile.reset(widgetIdRef.current);
    }
    setCaptchaToken("");
  };

  const onFinish = (values) => {
    setLoading(true);
    setCaptchaError("");
    const payload = {
      email: values.email,
      password: values.password,
      subdomain: values.subdomain,
      language: values.language,
      captcha_token: captchaToken,
    };
    if (values.name && values.name.trim()) {
      payload.name = values.name.trim();
    }
    api
      .post("register", payload)
      .then(() => {
        setSentTo(values.email);
      })
      .catch((err) => {
        // Any 400 means this submit is being retried, and a Turnstile
        // token is single-use, so the widget is reset even when the
        // captcha was not what failed.
        resetCaptcha();
        // A field error belongs under the field. The API answers a 400
        // with {message, details}; `details` is keyed by field name,
        // so anything matching an input on this form is pushed onto
        // it and the toast is kept for errors with nowhere to land.
        const details = err.response?.data?.details || {};
        // The captcha is not an antd field, so its message is rendered
        // from state. Taken out before the mapping below, and treated
        // as handled, so it never also raises a toast.
        const captchaErrors = details.captcha_token;
        if (captchaErrors) {
          setCaptchaError(
            Array.isArray(captchaErrors) ? captchaErrors[0] : captchaErrors
          );
        }
        const fields = Object.entries(details)
          .filter(([name]) => FORM_FIELDS.includes(name))
          .map(([name, errors]) => ({
            name,
            errors: Array.isArray(errors) ? errors : [errors],
          }));
        if (fields.length) {
          form.setFields(fields);
        }
        if (fields.length || captchaErrors) {
          return;
        }
        notify({
          type: "error",
          // `detail` before the generic fallback: a 429 from the
          // throttles carries only `detail`, and it is the part that
          // says waiting will help rather than "Registration failed".
          message:
            err.response?.data?.message ||
            err.response?.data?.detail ||
            c.failed,
        });
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const onResend = () => {
    resend(sentTo)
      .then((res) => {
        // The API answers identically whether or not it sent anything —
        // it will not confirm that an address is registered. Asserting
        // delivery here made an already-activated account, whose resend
        // is a deliberate no-op, look broken.
        notify({
          type: "success",
          message: res?.data?.message || c.sent.resent,
        });
      })
      .catch(() => {
        notify({ type: "error", message: c.sent.resendError });
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
              <Title level={2}>{c.sent.title}</Title>
              <Text type="secondary">
                {c.sent.body.split("{email}").map((part, i) => (
                  <React.Fragment key={i}>
                    {i > 0 ? <strong>{sentTo}</strong> : null}
                    {part}
                  </React.Fragment>
                ))}
              </Text>
              <div style={{ marginTop: 24 }}>
                <Text type="secondary">
                  {c.sent.didntGet}{" "}
                  <Button
                    type="link"
                    size="small"
                    loading={resending}
                    onClick={onResend}
                    style={{ padding: 0 }}
                  >
                    {c.sent.resend}
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
                    {c.sent.useDifferent}
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
            <h1>{c.title}</h1>
            <p className="disclaimer">{c.subtitle}</p>
            <Form
              form={form}
              name="register-form"
              layout="vertical"
              onFinish={onFinish}
              initialValues={{
                subdomain: suggestedSubdomain,
                language: "en",
              }}
            >
              <Form.Item
                name="email"
                label={c.emailLabel}
                rules={[
                  {
                    required: true,
                    type: "email",
                    message: c.emailInvalid,
                  },
                ]}
              >
                <Input placeholder={c.emailPlaceholder} />
              </Form.Item>
              <Form.Item
                name="password"
                label={c.passwordLabel}
                rules={[
                  { required: true, message: c.passwordRequired },
                  {
                    min: 8,
                    message: c.passwordMin,
                  },
                ]}
              >
                <Input.Password
                  disabled={loading}
                  placeholder={c.passwordPlaceholder}
                />
              </Form.Item>
              <Form.Item
                name="confirm_password"
                label={c.confirmLabel}
                // Validated here rather than server-side: the server only ever
                // receives one password, and a typo caught after the account
                // exists would need a reset to recover from.
                dependencies={["password"]}
                rules={[
                  { required: true, message: c.confirmRequired },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue("password") === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error(c.confirmMismatch));
                    },
                  }),
                ]}
              >
                <Input.Password
                  disabled={loading}
                  placeholder={c.confirmPlaceholder}
                />
              </Form.Item>
              <Form.Item
                name="language"
                label={c.languageLabel}
                rules={[
                  {
                    required: true,
                    message: c.languageRequired,
                  },
                ]}
              >
                <Select
                  options={LANGUAGE_OPTIONS}
                  disabled={loading}
                  placeholder={c.languagePlaceholder}
                />
              </Form.Item>
              <Form.Item
                name="name"
                label={c.nameLabel}
                extra={c.nameExtra}
                rules={[
                  { required: false },
                  {
                    max: 255,
                    message: c.nameMax,
                  },
                ]}
              >
                <Input disabled={loading} placeholder={c.namePlaceholder} />
              </Form.Item>
              <Form.Item
                name="subdomain"
                label={c.addressLabel}
                extra={c.addressExtra}
                rules={[
                  {
                    required: true,
                    pattern: /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/,
                    message: c.addressPattern,
                  },
                  {
                    min: 3,
                    message: c.addressMin,
                  },
                ]}
              >
                <Input
                  placeholder={c.addressPlaceholder}
                  addonAfter={addressSuffix}
                />
              </Form.Item>
              {siteKey ? (
                <Form.Item
                  validateStatus={captchaError ? "error" : ""}
                  help={captchaError || null}
                >
                  <div id="turnstile-widget" ref={widgetRef} />
                </Form.Item>
              ) : null}
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  shape="round"
                  block
                  loading={loading}
                >
                  {c.submit}
                </Button>
              </Form.Item>
              <p className="disclaimer">
                {c.haveOne} <Link to="/login">{c.signIn}</Link>
              </p>
            </Form>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default Register;
