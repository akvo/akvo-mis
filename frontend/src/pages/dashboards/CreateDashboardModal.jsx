import React, { useCallback, useMemo, useState } from "react";
import { Modal, Form, Input, Select, message } from "antd";
import { Link } from "react-router-dom";
import { store, uiText } from "../../lib";
import dashboardApi from "../../util/dashboardApi";

const CreateDashboardModal = ({ visible, onCancel, onCreate }) => {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const { allForms, language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const registrationForms = useMemo(
    () =>
      (allForms || []).filter(
        (f) => !f.content?.parent && f.content?.published !== false
      ),
    [allForms]
  );

  const doCreate = useCallback(
    (payload) =>
      dashboardApi.create(payload).catch((err) => {
        if (err?.response?.status === 409) {
          const suggested = err.response.data?.suggested_slug;
          if (suggested) {
            return dashboardApi.create({ ...payload, slug: suggested });
          }
          message.error(
            text.dashboardSlugConflict ||
              "A dashboard with a similar name already exists. Please choose a different name."
          );
        } else if (err?.response?.status === 403) {
          message.error(
            text.dashboardForbidden ||
              "You no longer have permission to perform this action."
          );
        } else {
          message.error(text.errorSomething || "Something went wrong");
        }
        throw err;
      }),
    [text]
  );

  const handleOk = useCallback(() => {
    form
      .validateFields()
      .then((values) => {
        setSubmitting(true);
        return doCreate({
          name: values.name.trim(),
          root_form: values.root_form,
        });
      })
      .then((res) => {
        form.resetFields();
        onCreate(res.data);
      })
      .catch((err) => {
        if (err?.errorFields) {
          // validation error, ant design handles display
        }
      })
      .finally(() => {
        setSubmitting(false);
      });
  }, [form, onCreate, doCreate]);

  const handleCancel = useCallback(() => {
    form.resetFields();
    onCancel();
  }, [form, onCancel]);

  return (
    <Modal
      title={text.dashboardCreateTitle || "Create a dashboard"}
      open={visible}
      onOk={handleOk}
      onCancel={handleCancel}
      okText={text.dashboardCreateBtn || "Create dashboard"}
      cancelText={text.cancel || "Cancel"}
      confirmLoading={submitting}
      okButtonProps={{ disabled: registrationForms.length === 0 }}
      destroyOnClose
    >
      <p className="dashboards-modal-hint">
        {text.dashboardCreateHint ||
          "Name it, then pick the registration form whose data this dashboard will show."}
      </p>
      <Form form={form} layout="vertical">
        <Form.Item
          name="name"
          label={text.dashboardNameLabel || "Dashboard name"}
          rules={[
            {
              required: true,
              message:
                text.dashboardNameRequired || "Please enter a dashboard name",
            },
          ]}
        >
          <Input placeholder="e.g. Regional Water Monitoring" />
        </Form.Item>
        <Form.Item
          name="root_form"
          label={text.dashboardFormLabel || "Data source"}
          extra={
            registrationForms.length > 0
              ? text.dashboardFormExtra ||
                "This dashboard will show data from this form and its monitoring forms. This cannot be changed later."
              : null
          }
          rules={[
            {
              required: true,
              message:
                text.dashboardFormRequired ||
                "Please select a registration form",
            },
          ]}
        >
          {registrationForms.length > 0 ? (
            <Select
              placeholder={
                text.dashboardFormPlaceholder || "Select a registration form"
              }
              showSearch
              optionFilterProp="children"
            >
              {registrationForms.map((f) => (
                <Select.Option key={f.id} value={f.id}>
                  {f.name}
                </Select.Option>
              ))}
            </Select>
          ) : (
            <div className="dashboards-no-forms">
              <p>
                {text.dashboardNoForms ||
                  "No published registration forms available."}
              </p>
              <p>
                <Link to="/control-center/form-builder">
                  {text.dashboardGoFormBuilder ||
                    "Go to Form Builder to create and publish a form."}
                </Link>
              </p>
            </div>
          )}
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default CreateDashboardModal;
