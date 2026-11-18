import React from "react";
import { Divider, Empty, Table, Tag, Typography } from "antd";

const { Title } = Typography;

const OnboardingReport = ({ report, text }) => (
  <div className="onboarding-report">
    <Title level={4}>{text.dataOnboardingReport}</Title>
    <Table
      rowKey="key"
      size="small"
      pagination={false}
      columns={[
        { title: text.dataOnboardingForms, dataIndex: "name" },
        { title: text.dataOnboardingLoaded, dataIndex: "loaded" },
      ]}
      dataSource={report.forms}
    />
    <Divider />
    <Title level={5}>{text.dataOnboardingIssues}</Title>
    {report.issues.length ? (
      <Table
        rowKey={(r) => `${r.sheet}/${r.row}/${r.question}`}
        size="small"
        columns={[
          { title: text.dataOnboardingSheet, dataIndex: "sheet" },
          { title: text.dataOnboardingRow, dataIndex: "row" },
          { title: text.dataOnboardingQuestion, dataIndex: "question" },
          {
            title: text.dataOnboardingReason,
            dataIndex: "reason",
            render: (reason, r) => (
              <>
                <Tag color={r.kind === "skipped" ? "red" : "orange"}>
                  {r.kind === "skipped"
                    ? text.dataOnboardingSkipped
                    : text.dataOnboardingDroppedAnswer}
                </Tag>
                {reason}
              </>
            ),
          },
        ]}
        dataSource={report.issues}
      />
    ) : (
      <Empty description={text.dataOnboardingNoIssues} />
    )}
  </div>
);

export default OnboardingReport;
