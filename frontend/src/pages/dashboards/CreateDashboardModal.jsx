import React, { useCallback, useMemo, useState } from "react";
import { Modal, Form, Input, Select, Radio, message } from "antd";
import { Link } from "react-router-dom";
import { store, uiText } from "../../lib";
import dashboardApi from "../../util/dashboardApi";
import { embedEnabled } from "../../util/tenant";

const CreateDashboardModal = ({ visible, onCancel, onCreate }) => {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  // Read the kind from the form rather than mirroring it in state. The
  // Modal is `destroyOnClose` but this component is never unmounted, so a
  // second copy of this value survives the close that resets the form and
  // then disagrees with it — the body would render the embed field while
  // handleOk, which branches on the form value, posted a widgets payload.
  // One source of truth makes that desync unrepresentable.
  // Only offered when the deployment has somewhere to render it.
  // Dashboards of this kind that already exist are unaffected —
  // this gates creating new ones, not reading old ones.
  const canEmbed = embedEnabled();
  const watchedKind = Form.useWatch("kind", form);
  const kind = (canEmbed && watchedKind) || "widgets";
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
        return doCreate(
          values.kind === "embed"
            ? {
                name: values.name.trim(),
                kind: "embed",
                embed_snippet: values.embed_snippet,
              }
            : {
                name: values.name.trim(),
                root_form: values.root_form,
              }
        );
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
      okButtonProps={{
        disabled: kind === "widgets" && registrationForms.length === 0,
      }}
      destroyOnClose
    >
      <p className="dashboards-modal-hint">
        {text.dashboardCreateHint ||
          "Name it, then pick the registration form whose data this dashboard will show."}
      </p>
      <Form form={form} layout="vertical" initialValues={{ kind: "widgets" }}>
        {canEmbed && (
          <Form.Item name="kind" label={text.dashboardKindLabel}>
            <Radio.Group>
              <Radio value="widgets">
                {text.dashboardKindWidgets}
                <div className="dashboards-modal-hint">
                  {text.dashboardKindWidgetsHint}
                </div>
              </Radio>
              <Radio value="embed">
                {text.dashboardKindEmbed}
                <div className="dashboards-modal-hint">
                  {text.dashboardKindEmbedHint}
                </div>
              </Radio>
            </Radio.Group>
          </Form.Item>
        )}
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
        {kind === "embed" ? (
          <Form.Item
            name="embed_snippet"
            label={text.dashboardEmbedLabel}
            extra={text.dashboardEmbedHint}
            rules={[{ required: true, message: text.dashboardEmbedRequired }]}
          >
            <Input.TextArea
              rows={5}
              placeholder={text.dashboardEmbedPlaceholder}
            />
          </Form.Item>
        ) : (
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
        )}
      </Form>
    </Modal>
  );
};

export default CreateDashboardModal;
