import React from "react";
import "../login/style.scss";
import { Row, Col, Button, Typography } from "antd";
import { baseDomainUrl } from "../../util/tenant";

const { Title, Text } = Typography;

// A workspace address that names no workspace — a typo, or one that was
// never created. Every API call from here is refused by the same 404 that
// got us here, so there is no version of the app worth rendering; what is
// worth offering is the two ways forward, and both live on the main site.
//
// The address is echoed back because it is the whole diagnosis: a wrong
// guess is usually one character away from a right one, and nothing else
// on this page can tell the visitor which character.
const WorkspaceNotFound = () => {
  const requested = window.location.hostname.split(".")[0];
  return (
    <div id="login">
      <Row className="wrapper" align="middle">
        <Col span={24} className="right-side">
          <div className="login-form-container" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 46, lineHeight: 1 }}>🧭</div>
            <Title level={2}>No workspace here</Title>
            <Text type="secondary">
              Nothing is set up at <strong>{window.location.hostname}</strong>.
              Check the address for a typo, or create this workspace.
            </Text>
            <div style={{ marginTop: 24 }}>
              <Button
                type="primary"
                shape="round"
                block
                href={baseDomainUrl("/find-workspace")}
              >
                Try another address
              </Button>
            </div>
            <div style={{ marginTop: 12 }}>
              <Button
                shape="round"
                block
                href={baseDomainUrl(
                  `/register?subdomain=${encodeURIComponent(requested)}`
                )}
              >
                Create this workspace
              </Button>
            </div>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default WorkspaceNotFound;
