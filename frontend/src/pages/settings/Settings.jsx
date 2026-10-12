import React, { useMemo, useState } from "react";
import "./style.scss";
import { Layout, Row, Col, Card, Button } from "antd";
import { config, store, uiText } from "../../lib";
import { Link } from "react-router-dom";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import Sidebar from "../../components/sidebar";
import { Can } from "../../components/can";
import BrandingModal from "./BrandingModal";

const SHOW_ORGANISATIONS_PANEL = false;

const Settings = () => {
  const { language, tenant } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);
  const [brandingOpen, setBrandingOpen] = useState(false);

  return (
    <div id="settings">
      <Layout>
        <Sidebar />
        <Layout className="site-layout">
          <div className="description-container">
            <Row justify="space-between">
              <Breadcrumbs
                pagePath={[
                  {
                    title: text.settings,
                    link: "/settings",
                  },
                ]}
              />
            </Row>
            <DescriptionPanel
              description={text.settingsDescriptionPanel}
              title={text.settings}
            />
          </div>
          <div style={{ padding: 24 }}>
            <Row gutter={[16, 16]}>
              {SHOW_ORGANISATIONS_PANEL && (
                <Can I="manage" a="master-data">
                  <Col className="card-wrapper" span={12}>
                    <Card bordered={false} style={{ paddingBottom: 20 }}>
                      <div className="row">
                        <div className="flex-1">
                          <h2>{text.orgPanelTitle}</h2>
                          <span>{text.orgPanelDescription}</span>
                          <Link
                            to="/control-center/master-data/organisations"
                            className="explore"
                          >
                            <Button type="primary" shape="round">
                              {text.orgPanelButton}
                            </Button>
                          </Link>
                        </div>
                        <div>
                          <img
                            src="/assets/personal-information.png"
                            width={100}
                            height={100}
                          />
                        </div>
                      </div>
                    </Card>
                  </Col>
                </Can>
              )}
              <Can I="manage" a="all">
                <Col className="card-wrapper" span={12}>
                  <Card
                    bordered={false}
                    hoverable
                    style={{ paddingBottom: 20 }}
                  >
                    <div className="row">
                      <div className="flex-1">
                        <h2>{text.brandingPanelTitle}</h2>
                        <span>{text.brandingPanelDescription}</span>
                        <div className="explore" style={{ marginTop: 16 }}>
                          <Button
                            type="primary"
                            shape="round"
                            onClick={() => {
                              setBrandingOpen(true);
                            }}
                          >
                            {text.brandingPanelButton}
                          </Button>
                        </div>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: 75,
                          height: 75,
                        }}
                      >
                        <img
                          src={tenant?.logo || config.siteLogo}
                          alt="Workspace Logo"
                          style={{
                            maxWidth: 100,
                            maxHeight: 65,
                            objectFit: "contain",
                          }}
                          onError={(e) => {
                            e.target.onerror = null;
                            e.target.src = config.siteLogo;
                          }}
                        />
                      </div>
                    </div>
                  </Card>
                </Col>
              </Can>
            </Row>
          </div>
        </Layout>
      </Layout>
      <BrandingModal
        open={brandingOpen}
        onClose={() => {
          setBrandingOpen(false);
        }}
      />
    </div>
  );
};

export default React.memo(Settings);
