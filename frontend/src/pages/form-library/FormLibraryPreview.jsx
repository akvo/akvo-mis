import React, { useEffect, useState } from "react";
import { Modal, Button, Tabs, Spin, Empty, Tag, Typography } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { api } from "../../lib";

const { Title, Text } = Typography;

// Read-only structural outline of one form (groups → questions). The template
// is never editable from here; "Use this form" clones it into the workspace.
const FormOutline = ({ form, emptyText }) => {
  const groups = form?.question_group || [];
  if (groups.length === 0) {
    return <Empty description={emptyText} />;
  }
  return (
    <div className="form-library-outline">
      {groups.map((group, gi) => (
        <div key={group.id || gi} className="form-library-outline-group">
          <Title level={5}>{group.label || group.name}</Title>
          <ul>
            {(group.question || []).map((q, qi) => (
              <li key={q.id || qi}>
                <Text>{q.label || q.name}</Text>{" "}
                <Tag className="form-library-outline-type">{q.type}</Tag>
                {q.required && <Tag color="red">required</Tag>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
};

const FormLibraryPreview = ({ templateId, text, canUse, onClose, onUse }) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!templateId) {
      setData(null);
      return;
    }
    setLoading(true);
    api
      .get(`/manage/forms/library/${templateId}/preview`)
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [templateId]);

  const registration = data?.registration;
  const monitoring = data?.monitoring || [];

  return (
    <Modal
      open={Boolean(templateId)}
      title={registration?.name || text.formLibraryPreviewTitle}
      width={720}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>
          {text.closeButton || "Close"}
        </Button>,
        canUse && (
          <Button
            key="use"
            type="primary"
            icon={<DownloadOutlined />}
            onClick={() => onUse({ id: templateId })}
          >
            {text.formLibraryUseButton}
          </Button>
        ),
      ]}
    >
      <Spin spinning={loading}>
        {!loading && !registration ? (
          <Empty description={text.formLibraryEmptyText} />
        ) : (
          registration && (
            <Tabs>
              <Tabs.TabPane
                tab={text.formLibraryRegistrationTab}
                key="registration"
              >
                <FormOutline
                  form={registration}
                  emptyText={text.formLibraryEmptyText}
                />
              </Tabs.TabPane>
              {monitoring.map((m, i) => (
                <Tabs.TabPane
                  tab={`${text.formLibraryMonitoringTab} ${
                    monitoring.length > 1 ? i + 1 : ""
                  }`.trim()}
                  key={`monitoring-${i}`}
                >
                  <FormOutline form={m} emptyText={text.formLibraryEmptyText} />
                </Tabs.TabPane>
              ))}
            </Tabs>
          )
        )}
      </Spin>
    </Modal>
  );
};

export default FormLibraryPreview;
