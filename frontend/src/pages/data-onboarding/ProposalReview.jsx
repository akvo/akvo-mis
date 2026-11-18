import React from "react";
import { Card, Divider, Empty, Table, Tag, Tree, Typography } from "antd";

const { Title, Text } = Typography;

// Units are paths of names below the root; merge them into one tree.
const unitTree = (units) => {
  const root = [];
  units.forEach((path) => {
    let level = root;
    path.forEach((name, i) => {
      const key = path.slice(0, i + 1).join("/");
      let node = level.find((n) => n.key === key);
      if (!node) {
        node = { key, title: name, children: [] };
        level.push(node);
      }
      level = node.children;
    });
  });
  return root;
};

const ProposalReview = ({ proposal, text }) => {
  const { administration, forms, data, notes } = proposal;

  const questionColumns = [
    { title: text.dataOnboardingQuestion, dataIndex: "label" },
    { title: text.dataOnboardingName, dataIndex: "name" },
    { title: text.dataOnboardingType, dataIndex: "type" },
    {
      title: text.dataOnboardingRequired,
      dataIndex: "required",
      render: (required) => (required ? <Tag>{text.yesText}</Tag> : null),
    },
    {
      title: text.dataOnboardingOptions,
      dataIndex: "option",
      render: (options) => options.map((o) => o.label).join(", "),
    },
  ];

  return (
    <div className="proposal-review">
      <Title level={4}>{text.dataOnboardingUnits}</Title>
      <Text type="secondary">{administration.levels.join(" › ")}</Text>
      {administration.units.length ? (
        <Tree treeData={unitTree(administration.units)} defaultExpandAll />
      ) : (
        <Empty description={text.dataOnboardingNoUnits} />
      )}

      <Divider />
      <Title level={4}>{text.dataOnboardingForms}</Title>
      {forms.map((form) => {
        const spec = data.find((d) => d.form === form.key);
        const questions = form.question_group.flatMap((g) => g.question);
        const label = (name) =>
          questions.find((q) => q.name === name)?.label || name;
        return (
          <Card
            key={form.key}
            title={form.name}
            extra={<Tag>{form.type}</Tag>}
            style={{ marginBottom: 16 }}
          >
            <Table
              rowKey="name"
              size="small"
              pagination={false}
              columns={questionColumns}
              dataSource={questions}
            />
            {spec && (
              <>
                <Title level={5}>{text.dataOnboardingMapping}</Title>
                <Text type="secondary">
                  {spec.sheet} · {text.dataOnboardingKeyColumns}:{" "}
                  {spec.key_columns.join(", ")}
                </Text>
                <Table
                  rowKey="question"
                  size="small"
                  pagination={false}
                  columns={[
                    { title: text.dataOnboardingColumn, dataIndex: "column" },
                    {
                      title: text.dataOnboardingQuestion,
                      dataIndex: "question",
                      render: label,
                    },
                  ]}
                  dataSource={spec.columns}
                />
                {spec.value_maps.length > 0 && (
                  <>
                    <Title level={5}>{text.dataOnboardingValueMaps}</Title>
                    <Table
                      rowKey={(r) => `${r.question}/${r.raw}`}
                      size="small"
                      pagination={false}
                      columns={[
                        {
                          title: text.dataOnboardingQuestion,
                          dataIndex: "question",
                          render: label,
                        },
                        { title: text.dataOnboardingRaw, dataIndex: "raw" },
                        {
                          title: text.dataOnboardingOptions,
                          dataIndex: "label",
                        },
                      ]}
                      dataSource={spec.value_maps.flatMap((m) =>
                        m.values.map((v) => ({ question: m.question, ...v }))
                      )}
                    />
                  </>
                )}
                {spec.unmapped_columns.length > 0 && (
                  <>
                    <Title level={5}>{text.dataOnboardingDropped}</Title>
                    <Table
                      rowKey="column"
                      size="small"
                      pagination={false}
                      columns={[
                        {
                          title: text.dataOnboardingColumn,
                          dataIndex: "column",
                        },
                        {
                          title: text.dataOnboardingReason,
                          dataIndex: "reason",
                        },
                      ]}
                      dataSource={spec.unmapped_columns}
                    />
                  </>
                )}
              </>
            )}
          </Card>
        );
      })}

      {notes.length > 0 && (
        <>
          <Divider />
          <Title level={4}>{text.dataOnboardingNotes}</Title>
          <ul>
            {notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
};

export default ProposalReview;
