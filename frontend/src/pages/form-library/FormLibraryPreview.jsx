import React, { useEffect, useState } from "react";
import { Modal, Button, Tabs, Spin, Empty } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { api } from "../../lib";

// One question rendered like a paper form field: a label over a faux,
// read-only input whose shape hints at the answer type.
const PaperField = ({ q }) => {
  const options = q.option || q.options || [];
  const isChoice = q.type === "option" || q.type === "multiple_option";
  return (
    <div className="paper-field">
      <div className="paper-field-label">
        {q.label || q.name}
        {q.required && <span className="paper-field-required">*</span>}
      </div>
      <div className="paper-field-body">
        {isChoice && options.length > 0 ? (
          <div className="paper-field-options">
            {options.map((o, oi) => (
              <span key={o.id || o.value || oi} className="paper-option">
                <span
                  className={
                    q.type === "multiple_option"
                      ? "paper-option-box"
                      : "paper-option-radio"
                  }
                />
                {o.label || o.name || o.value}
              </span>
            ))}
          </div>
        ) : (
          <div
            className={`paper-field-input paper-input-${q.type || "input"}`}
          />
        )}
        <div className="paper-field-type">{q.type}</div>
      </div>
    </div>
  );
};

// Read-only, paper-like preview of one form (groups → fields). Exported so the
// promote page can reuse it to preview a source family inline.
export const FormOutline = ({ form, emptyText }) => {
  const groups = form?.question_group || [];
  if (groups.length === 0) {
    return <Empty description={emptyText} />;
  }
  return (
    <div className="form-library-outline">
      {groups.map((group, gi) => (
        <div key={group.id || gi} className="paper-group">
          <div className="paper-group-title">{group.label || group.name}</div>
          {(group.question || []).map((q, qi) => (
            <PaperField key={q.id || qi} q={q} />
          ))}
        </div>
      ))}
    </div>
  );
};

// Preview a template family (`templateId`, tabs) OR a single form
// (`formId`, no tabs). The single mode is for the console, where each form —
// registration and every monitoring child — gets its own Preview so a family
// with many monitoring forms never produces an overflowing tab bar.
const FormLibraryPreview = ({
  templateId,
  formId,
  text,
  canUse,
  onClose,
  onUse,
}) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  useEffect(() => {
    const id = templateId || formId;
    if (!id) {
      setData(null);
      return;
    }
    setLoading(true);
    // A template form is tenant-less, so a tenant-less curator can read a
    // single one via the normal for_user-scoped detail endpoint.
    const request = templateId
      ? api
          .get(`/manage/forms/library/${templateId}/preview`)
          .then((res) => res.data)
      : api
          .get(`/manage/forms/${formId}`)
          .then((res) => ({ registration: res.data, monitoring: [] }));
    request
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [templateId, formId]);

  const registration = data?.registration;
  const monitoring = data?.monitoring || [];

  return (
    <Modal
      open={Boolean(templateId || formId)}
      title={registration?.name || text.formLibraryPreviewTitle}
      width={720}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>
          {text.closeButton || "Close"}
        </Button>,
        canUse && templateId && (
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
        {!registration ? (
          !loading && <Empty description={text.formLibraryEmptyText} />
        ) : monitoring.length === 0 ? (
          <FormOutline
            form={registration}
            emptyText={text.formLibraryEmptyText}
          />
        ) : (
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
                tab={m.name || `${text.formLibraryMonitoringTab} ${i + 1}`}
                key={`monitoring-${i}`}
              >
                <FormOutline form={m} emptyText={text.formLibraryEmptyText} />
              </Tabs.TabPane>
            ))}
          </Tabs>
        )}
      </Spin>
    </Modal>
  );
};

export default FormLibraryPreview;
