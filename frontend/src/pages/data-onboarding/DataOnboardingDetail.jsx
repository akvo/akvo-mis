import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Alert, Button, Input, Spin, message } from "antd";
import { Breadcrumbs } from "../../components";
import { api, store, uiText } from "../../lib";
import { DownloadOutlined } from "@ant-design/icons";
import ProposalReview from "./ProposalReview";
import OnboardingReport from "./OnboardingReport";

const POLL_INTERVAL_MS = 2500;

const DataOnboardingDetail = () => {
  const { id } = useParams();
  const [onboarding, setOnboarding] = useState(null);
  const { active: activeLang } = store.useState((s) => s.language);
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const status = onboarding?.status;
  const blocked = onboarding?.blocked || [];
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

  const edit = (body) =>
    api
      .post(`/data-onboarding/${id}/edits`, body)
      .then((res) => setOnboarding(res.data))
      .catch((err) => message.error(err.response?.data?.message));

  const [instruction, setInstruction] = useState("");
  const revise = () =>
    api
      .post(`/data-onboarding/${id}/revise`, { instruction })
      .then((res) => {
        setOnboarding(res.data);
        setInstruction("");
      })
      .catch((err) => message.error(err.response?.data?.message));

  const downloadReport = () => {
    api
      .get(`/data-onboarding/${id}/report`, { responseType: "blob" })
      .then((res) => {
        const filename =
          /filename="(?<f>[^"]+)"/.exec(res.headers["content-disposition"])
            ?.groups?.f || `onboarding-report-${id}.xlsx`;
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => message.error(text.dataOnboardingDownloadFailed));
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
    {
      title: text.dataOnboardingHistory,
      link: "/control-center/data-onboarding",
    },
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
              message={
                // A draft failure leaves no Proposal; an Apply failure does.
                onboarding.proposal
                  ? text.dataOnboardingApplyFailed
                  : text.dataOnboardingFailed
              }
              description={onboarding.error}
            />
          )}
          {status === "applying" && (
            <Spin tip={text.dataOnboardingApplying}>
              <div style={{ minHeight: 120 }} />
            </Spin>
          )}
          {status === "proposed" && (
            <>
              {onboarding.error && (
                // A failed revision keeps the previous Proposal.
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginBottom: 16 }}
                  message={text.dataOnboardingRevisionFailed}
                  description={onboarding.error}
                />
              )}
              {blocked.length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginBottom: 16 }}
                  message={text.dataOnboardingBlockedNote}
                />
              )}
              <Button
                type="primary"
                loading={applying}
                disabled={
                  blocked.length >= (onboarding.proposal?.forms.length || 0)
                }
                onClick={apply}
              >
                {text.dataOnboardingApply}
              </Button>
              <Input.TextArea
                rows={2}
                maxLength={2000}
                style={{ margin: "16px 0 8px" }}
                placeholder={text.dataOnboardingReviseHint}
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
              />
              <Button disabled={!instruction.trim()} onClick={revise}>
                {text.dataOnboardingRevise}
              </Button>
            </>
          )}
          {onboarding?.report ? (
            <>
              <Button
                icon={<DownloadOutlined />}
                onClick={downloadReport}
                style={{ float: "right" }}
              >
                {text.dataOnboardingDownloadReport}
              </Button>
              <OnboardingReport report={onboarding.report} text={text} />
            </>
          ) : (
            onboarding?.proposal && (
              <ProposalReview
                proposal={onboarding.proposal}
                blocked={blocked}
                text={text}
                onEdit={status === "proposed" ? edit : null}
              />
            )
          )}
        </div>
      </div>
    </div>
  );
};

export default DataOnboardingDetail;
