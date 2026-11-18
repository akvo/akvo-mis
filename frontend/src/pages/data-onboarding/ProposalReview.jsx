import React from "react";
import {
  Alert,
  Button,
  Card,
  Divider,
  Empty,
  Table,
  Tag,
  Tree,
  Typography,
} from "antd";

const { Title, Text } = Typography;

// Units are names, or {name, match} for a near-match spelling.
const unitText = (u) => (u.match ? `${u.name} → ${u.match}` : u);

export const BlockedCauses = ({ causes }) => (
  <Alert
    type="error"
    showIcon
    style={{ marginBottom: 16 }}
    message={
      <ul style={{ margin: 0, paddingLeft: 16 }}>
        {causes.map((c, i) => (
          <li key={i}>
            <span>{c.reason}</span>
            {c.units?.length > 0 && (
              <Text type="secondary">
                {" "}
                ({c.units.map(unitText).join(", ")})
              </Text>
            )}
          </li>
        ))}
      </ul>
    }
  />
);

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

// onEdit(body) sends a structured edit; without it the review is read-only.
const ProposalReview = ({ proposal, blocked = [], text, onEdit }) => {
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
        const block = blocked.find((b) => b.form === form.key);
        const questions = form.question_group.flatMap((g) => g.question);
        const label = (name) =>
          questions.find((q) => q.name === name)?.label || name;
        const columnEdit = (op, title) =>
          onEdit
            ? [
                {
                  key: op,
                  render: (_, row) => (
                    <Button
                      size="small"
                      onClick={() =>
                        onEdit({ op, form: form.key, column: row.column })
                      }
                    >
                      {title}
                    </Button>
                  ),
                },
              ]
            : [];
        return (
          <Card
            key={form.key}
            title={
              <Text
                editable={
                  onEdit && {
                    onChange: (name) =>
                      name.trim() &&
                      name !== form.name &&
                      onEdit({ op: "rename_form", form: form.key, name }),
                  }
                }
              >
                {form.name}
              </Text>
            }
            extra={
              <>
                {block && <Tag color="red">{text.dataOnboardingBlocked}</Tag>}
                <Tag>{form.type}</Tag>
              </>
            }
            style={{ marginBottom: 16 }}
          >
            {block && <BlockedCauses causes={block.causes} />}
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
                    ...columnEdit("drop_column", text.dataOnboardingDropColumn),
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
                        ...columnEdit(
                          "keep_column",
                          text.dataOnboardingKeepColumn
                        ),
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
