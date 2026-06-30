import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { Card, Empty, Table } from "antd";
import { findAnswer, findQuestion, formatAnswerValue } from "./helpers";
import useAdministrationNames from "./useAdministrationNames";

/**
 * Two-column AntD <Table> rendering Question (published-form label) /
 * Answer (formatAnswerValue) for a list of question ids. Skips qids with
 * no resolvable answer rather than rendering blank rows.
 */
const CharacteristicsTable = ({
  title,
  qids,
  values,
  bordered,
  size,
  emptyText,
}) => {
  const administrationLookup = useAdministrationNames(values);
  const rows = useMemo(() => {
    const lookups = { administration: administrationLookup };
    return (qids || [])
      .map((qid) => {
        const question = findQuestion(qid);
        const answer = findAnswer(values, qid);
        const display = formatAnswerValue(answer, question, lookups);
        if (!question || display === null) {
          return null;
        }
        return {
          key: String(qid),
          question: question.label || question.name || String(qid),
          answer: display,
        };
      })
      .filter(Boolean);
  }, [qids, values, administrationLookup]);

  const columns = [
    {
      title: "Question",
      dataIndex: "question",
      key: "question",
      width: "50%",
    },
    {
      title: "Answer",
      dataIndex: "answer",
      key: "answer",
    },
  ];

  const body =
    rows.length === 0 ? (
      <Empty description={emptyText} />
    ) : (
      <Table
        columns={columns}
        dataSource={rows}
        pagination={false}
        size={size}
        bordered={bordered}
        showHeader={false}
      />
    );

  if (!title) {
    return body;
  }
  return (
    <Card title={title} bordered>
      {body}
    </Card>
  );
};

CharacteristicsTable.propTypes = {
  title: PropTypes.string,
  qids: PropTypes.arrayOf(
    PropTypes.oneOfType([PropTypes.number, PropTypes.string])
  ).isRequired,
  values: PropTypes.array,
  bordered: PropTypes.bool,
  size: PropTypes.oneOf(["small", "middle", "large"]),
  emptyText: PropTypes.string,
};

CharacteristicsTable.defaultProps = {
  values: [],
  bordered: true,
  size: "small",
  emptyText: "No information available",
};

export default CharacteristicsTable;
