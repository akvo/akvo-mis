import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { Table } from "antd";

const VizTable = ({ config, data }) => {
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

  if (columns.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        Configure table columns in the inspector
      </div>
    );
  }

  // /escalation requires criteria as well as columns, so until there is at
  // least one condition useWidgetData issues no request and `data` stays
  // null. Without saying so the widget drew an empty grid, which reads as a
  // broken table rather than an unfinished one.
  if (!Array.isArray(widgetConfig.criteria) || !widgetConfig.criteria.length) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        Add at least one filter condition in the inspector
      </div>
    );
  }

  return (
    <Table
      columns={columns}
      dataSource={rows}
      size="small"
      pagination={{
        pageSize: widgetConfig.page_size || 20,
        hideOnSinglePage: true,
      }}
      scroll={{ x: true }}
    />
  );
};

VizTable.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizTable;
