import React, { useMemo } from "react";
import "./style.scss";
import { Row, Col } from "antd";
import { store, uiText } from "../../lib";
import { PanelApprovals, PanelSubmissions } from "./components";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { ControlCenterTour } from "./components";
import { Can } from "../../components/can";

const ControlCenter = () => {
  const { user: authUser } = store.useState((s) => s);
  const { language } = store.useState((s) => s);

  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang] || uiText.en;
  }, [activeLang]);

  return (
    <>
      <div className="description-container">
        <Row justify="space-between">
          <Breadcrumbs
            pagePath={[
              {
                title: text.controlCenter,
                link: "/control-center",
              },
            ]}
          />
          <ControlCenterTour />
        </Row>
        <DescriptionPanel description={text.ccDescriptionPanel} />

        <div className="profile-container">
          <h2>
            {window?.appConfig?.name || "Akvo MIS"} {text.controlCenter}
          </h2>
          <div className="profle-wrapper">
            <div>
              <h2>{`${text.helloText} ${authUser?.name || ""}`}</h2>
              <p>
                {`${text.lastLoginLabel}: `}
                {authUser?.last_login
                  ? new Date(authUser.last_login * 1000)
                      .toISOString()
                      .replace("T", " ")
                      .slice(0, 19)
                  : "-"}
              </p>
            </div>
          </div>
        </div>
      </div>
      <Can I="manage" a="approvals">
        <div className="table-section">
          <div className="table-wrapper">
            <Col key="approvals-panel" span={24}>
              <PanelApprovals />
            </Col>
          </div>
        </div>
      </Can>
      <Can I="manage" a="submissions">
        <div className="table-section">
          <div className="table-wrapper">
            <Col key="submission-panel" span={24}>
              <PanelSubmissions />
            </Col>
          </div>
        </div>
      </Can>
    </>
  );
};

export default ControlCenter;
