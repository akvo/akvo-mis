import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { Table } from "antd";

// Sources the backend refuses without a question id
// (EscalationFilterSerializer.validate_columns).
const QID_REQUIRED = ["answer", "parent_answer", "latest_date"];

const usableColumns = (columns) =>
  (Array.isArray(columns) ? columns : []).filter(
    (c) =>
      c?.key &&
      c?.source &&
      (!QID_REQUIRED.includes(c.source) || Boolean(c.question))
  );

const VizTable = ({ config, data, pagination }) => {
  const widgetConfig = config?.config || {};
  const columns = useMemo(() => {
    if (!Array.isArray(widgetConfig.columns)) {
      return [];
    }
    return widgetConfig.columns.map((col) => ({
      title: col.label || col.key,
      dataIndex: col.key,
      key: col.key,
    }));
  }, [widgetConfig.columns]);

  const rows = useMemo(() => {
    if (!Array.isArray(data)) {
      return [];
    }
    return data.map((row, i) => ({ ...row, key: row.id || i }));
  }, [data]);

  // Columns are the one thing a table cannot do without: they are what
  // the request asks for and what the grid draws. Criteria are optional —
  // no conditions means every datapoint — so there is nothing to prompt
  // for there, and an unfinished condition simply does not narrow
  // anything.
  //
  // The server decides what to send now (VIZ-010), and it drops a column
  // whose source needs a question id and has none. This mirrors that rule
  // so the empty state says "no columns" instead of drawing a grid the
  // server will answer with nothing. It is a prompt, not a query: the
  // rule that must not be duplicated is the one that produces numbers.
  if (columns.length === 0 || !usableColumns(widgetConfig.columns).length) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        Configure table columns in the inspector
      </div>
    );
  }

  return (
    <Table
      columns={columns}
      dataSource={rows}
      size="small"
      // Server-side. `data` is one page and `pagination.total` is the
      // whole set, so antd must be told the total rather than left to infer
      // it from the rows in front of it — inferring gave it one page every
      // time and `hideOnSinglePage` then removed the pager entirely.
      // `onChange` fetches the next page rather than slicing locally.
      pagination={{
        current: pagination?.current || 1,
        pageSize: pagination?.pageSize || widgetConfig.page_size || 20,
        total: pagination?.total ?? (Array.isArray(data) ? data.length : 0),
        onChange: pagination?.onChange,
        hideOnSinglePage: true,
        showSizeChanger: false,
      }}
      scroll={{ x: true }}
    />
  );
};

VizTable.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
  pagination: PropTypes.object,
};

export default VizTable;
