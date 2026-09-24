import React, { useCallback, useMemo, useState } from "react";
import { Modal, Form, Input, Select, Radio, Switch, message } from "antd";
import { ThunderboltOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { store, uiText } from "../../lib";
import dashboardApi from "../../util/dashboardApi";
import dashboardAi from "../../util/dashboardAi";

const CreateDashboardModal = ({ visible, onCancel, onCreate }) => {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  // Read the kind from the form rather than mirroring it in state. The
  // Modal is `destroyOnClose` but this component is never unmounted, so a
  // second copy of this value survives the close that resets the form and
  // then disagrees with it — the body would render the embed field while
  // handleOk, which branches on the form value, posted a widgets payload.
  // One source of truth makes that desync unrepresentable.
  const { allForms, language, tenant } = store.useState((s) => s);
  // Only offered when this workspace is entitled to embedding. The
  // server answers that on tenant-info, and only to a signed-in caller,
  // so an absent field reads as false. Dashboards of this kind that
  // already exist are unaffected — this gates creating, not reading.
  const canEmbed = Boolean(tenant?.embed_enabled);
  const watchedKind = Form.useWatch("kind", form);
  const watchedAutoAi = Form.useWatch("auto_generate_ai", form);
  const kind = (canEmbed && watchedKind) || "widgets";
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
      .then(async (values) => {
        setSubmitting(true);
        if (values.kind === "embed") {
          return doCreate({
            name: values.name.trim(),
            kind: "embed",
            embed_snippet: values.embed_snippet,
          });
        }

        let starterWidgets = null;
        if (values.auto_generate_ai && values.root_form) {
          try {
            const aiPayload = { root_form: values.root_form };
            if (values.user_intent && values.user_intent.trim()) {
              aiPayload.user_intent = values.user_intent.trim();
            }
            const aiRes = await dashboardAi.suggestDashboard(aiPayload);
            if (aiRes?.data?.widgets && Array.isArray(aiRes.data.widgets)) {
              starterWidgets = aiRes.data.widgets;
            }
          } catch (aiErr) {
            message.warning(
              text.dashboardAiFallbackWarning ||
                "Could not generate AI starter widgets. Creating empty dashboard instead."
            );
          }
        }

        const createPayload = {
          name: values.name.trim(),
          root_form: values.root_form,
        };
        if (starterWidgets) {
          createPayload.widgets = starterWidgets;
        }

        return doCreate(createPayload);
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
  }, [form, onCreate, doCreate, text]);

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
        {kind !== "embed" && registrationForms.length > 0 && (
          <>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginTop: 8,
                marginBottom: 16,
              }}
            >
              <span
                style={{
                  fontWeight: 500,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <ThunderboltOutlined style={{ color: "#1890ff" }} />
                {text.dashboardAiStarterToggle ||
                  "Auto-generate starter dashboard with AI"}
              </span>
              <Form.Item
                name="auto_generate_ai"
                valuePropName="checked"
                noStyle
                initialValue={false}
              >
                <Switch />
              </Form.Item>
            </div>
            {watchedAutoAi && (
              <Form.Item
                name="user_intent"
                label={
                  text.dashboardAiIntentLabel ||
                  "Dashboard Goal & Questions (Optional)"
                }
                extra={
                  text.dashboardAiIntentHint ||
                  "Tell the AI what insights you are looking for (e.g. 'Overview of borehole status and functional breakdown')"
                }
              >
                <Input.TextArea
                  rows={2}
                  placeholder="e.g. Overview of borehole functionality and regional water access"
                />
              </Form.Item>
            )}
          </>
        )}
      </Form>
    </Modal>
  );
};

export default CreateDashboardModal;
