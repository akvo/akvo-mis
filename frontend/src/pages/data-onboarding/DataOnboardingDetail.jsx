import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Alert, Spin } from "antd";
import { Breadcrumbs } from "../../components";
import { api, store, uiText } from "../../lib";
import ProposalReview from "./ProposalReview";

const POLL_INTERVAL_MS = 2500;

const DataOnboardingDetail = () => {
  const { id } = useParams();
  const [onboarding, setOnboarding] = useState(null);
  const { active: activeLang } = store.useState((s) => s.language);
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const drafting = !onboarding || onboarding.status === "drafting";

  useEffect(() => {
    if (!drafting) {
      return () => {};
    }
    const load = () => {
      api
        .get(`/data-onboarding/${id}`)
        .then((res) => setOnboarding(res.data))
        .catch(() => {
          // transient polling error — keep polling
        });
    };
    if (!onboarding) {
      load();
    }
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [id, drafting, onboarding]);

  const pagePath = [
    { title: text.controlCenter, link: "/control-center" },
    { title: text.menuFormBuilder, link: "/control-center/form-builder" },
    { title: onboarding?.file_name || text.formBuilderDataOnboardingButton },
  ];

  return (
    <div id="data-onboarding-detail">
      <div className="description-container">
        <Breadcrumbs pagePath={pagePath} />
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          {drafting && (
            <Spin tip={text.dataOnboardingDrafting}>
              <div style={{ minHeight: 120 }} />
            </Spin>
          )}
          {onboarding?.status === "failed" && (
            <Alert
              type="error"
              showIcon
              message={text.dataOnboardingFailed}
              description={onboarding.error}
            />
          )}
          {onboarding?.proposal && (
            <ProposalReview proposal={onboarding.proposal} text={text} />
          )}
        </div>
      </div>
    </div>
  );
};

export default DataOnboardingDetail;
