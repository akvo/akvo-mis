import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Alert, Button, Spin, message } from "antd";
import { Breadcrumbs } from "../../components";
import { api, store, uiText } from "../../lib";
import ProposalReview from "./ProposalReview";
import OnboardingReport from "./OnboardingReport";

const POLL_INTERVAL_MS = 2500;

const DataOnboardingDetail = () => {
  const { id } = useParams();
  const [onboarding, setOnboarding] = useState(null);
  const { active: activeLang } = store.useState((s) => s.language);
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const status = onboarding?.status;
  const drafting = !onboarding || status === "drafting";
  const busy = drafting || status === "applying";
  const [applying, setApplying] = useState(false);

  const apply = () => {
    setApplying(true);
    api
      .post(`/data-onboarding/${id}/apply`)
      .then((res) => setOnboarding(res.data))
      .catch((err) => message.error(err.response?.data?.message))
      .finally(() => setApplying(false));
  };

  useEffect(() => {
    if (!busy) {
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
  }, [id, busy, onboarding]);

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
          {status === "applying" && (
            <Spin tip={text.dataOnboardingApplying}>
              <div style={{ minHeight: 120 }} />
            </Spin>
          )}
          {status === "proposed" && (
            <Button type="primary" loading={applying} onClick={apply}>
              {text.dataOnboardingApply}
            </Button>
          )}
          {onboarding?.report ? (
            <OnboardingReport report={onboarding.report} text={text} />
          ) : (
            onboarding?.proposal && (
              <ProposalReview proposal={onboarding.proposal} text={text} />
            )
          )}
        </div>
      </div>
    </div>
  );
};

export default DataOnboardingDetail;
