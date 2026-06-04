import React from "react";
import { Button, Drawer, Popconfirm, Space, Table, Tag } from "antd";

const VersionHistoryDrawer = ({
  open,
  onClose,
  versions,
  loading,
  onRefresh,
  activatingId,
  previewLoadingId,
  onActivate,
  onPreview,
  text,
}) => {
  const columns = [
    {
      title: text.formBuilderVersionCol,
      dataIndex: "version",
      key: "version",
      render: (v, record) => (
        <Space>
          {`v${v}`}
          {record.is_active && (
            <Tag color="green">{text.formBuilderActiveTag}</Tag>
          )}
        </Space>
      ),
    },
    {
      title: text.formBuilderPublishedAtCol,
      dataIndex: "published_at",
      key: "published_at",
      render: (v) => (v ? new Date(v).toLocaleString() : "—"),
    },
    {
      title: text.formBuilderPublishedByCol,
      dataIndex: "published_by",
      key: "published_by",
      render: (v) => v || "—",
    },
    {
      title: text.formBuilderActionsCol,
      key: "actions",
      render: (_, record) => {
        if (record.is_active) {
          return null;
        }
        return (
          <Space>
            <Button
              size="small"
              loading={previewLoadingId === record.id}
              disabled={
                activatingId !== null ||
                (previewLoadingId !== null && previewLoadingId !== record.id)
              }
              onClick={() => {
                onPreview(record);
              }}
            >
              {text.formBuilderPreviewButton}
            </Button>
            <Popconfirm
              title={text.formBuilderActivateVersionTitle(record.version)}
              description={text.formBuilderActivateVersionDesc}
              onConfirm={() => {
                onActivate(record.id, record.version);
              }}
              okText={text.formBuilderActivateButton}
              cancelText={text.cancelButton}
            >
              <Button
                size="small"
                loading={activatingId === record.id}
                disabled={
                  (activatingId !== null && activatingId !== record.id) ||
                  previewLoadingId !== null
                }
              >
                {text.formBuilderSetActiveButton}
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <Drawer
      title={text.formBuilderVersionHistoryTitle}
      width={640}
      open={open}
      onClose={onClose}
      extra={
        <Button size="small" onClick={onRefresh} loading={loading}>
          {text.formBuilderRefreshButton}
        </Button>
      }
    >
      <Table
        columns={columns}
        dataSource={versions}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10, hideOnSinglePage: true }}
        size="small"
        locale={{ emptyText: text.formBuilderVersionHistoryEmpty }}
        rowClassName={(record) =>
          record.is_active ? "version-row-active" : ""
        }
      />
    </Drawer>
  );
};

export default VersionHistoryDrawer;
