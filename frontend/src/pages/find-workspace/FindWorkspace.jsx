import React from "react";
import "../login/style.scss";
import { Row, Col, Form, Input, Button } from "antd";
import { Link } from "react-router-dom";
import { baseDomain, workspaceUrl } from "../../util/tenant";
import { useTranslation } from "../../lib/i18n";

// The main site has no workspace, so it cannot sign anyone in — the
// backend refuses a login here. What it can do is send someone to the
// right address.
//
// No lookup call: asking the server "does this workspace exist?" would
// hand an anonymous visitor a way to enumerate every customer. Sending
// the browser there instead costs nothing and lets the workspace's own
// host answer, which for a wrong guess is the WorkspaceNotFound page —
// it reveals only what the guesser already typed, and offers the way
// back here as well as the way on to sign-up.
const FindWorkspace = () => {
  const c = useTranslation("findWorkspace");
  const onFinish = ({ subdomain }) => {
    window.location.href = workspaceUrl(subdomain.trim().toLowerCase());
  };

  return (
    <div id="login">
      <Row className="wrapper" align="middle">
        <Col span={24} className="right-side">
          <div className="login-form-container">
            <h1>{c.title}</h1>
            <p className="disclaimer">{c.subtitle}</p>
            <Form name="find-workspace" layout="vertical" onFinish={onFinish}>
              <Form.Item
                name="subdomain"
                label={c.addressLabel}
                rules={[{ required: true, message: c.addressRequired }]}
              >
                <Input
                  placeholder={c.addressPlaceholder}
                  addonAfter={`.${baseDomain()}`}
                />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" shape="round" block>
                  {c.submit}
                </Button>
              </Form.Item>
              <p className="disclaimer">
                {c.noWorkspace} <Link to="/onboarding">{c.create}</Link>
              </p>
            </Form>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default FindWorkspace;
