import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  Modal,
  Form,
  Input,
  Select,
  Radio,
  Switch,
  Tag,
  Spin,
  message,
} from "antd";
import { ThunderboltOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { store, uiText } from "../../lib";
import dashboardApi from "../../util/dashboardApi";
import dashboardAi from "../../util/dashboardAi";

const INTENT_PRESETS = [
  "Executive KPI Overview",
  "Regional & Spatial Breakdown",
  "Status & Functionality Analysis",
  "Monthly Trends & Timelines",
];

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
  const watchedRootForm = Form.useWatch("root_form", form);
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

  const availableMonitoringForms = useMemo(() => {
    if (!watchedRootForm) {
      return [];
    }
    return (allForms || []).filter(
      (f) =>
        f.content?.parent === watchedRootForm && f.content?.published !== false
    );
  }, [allForms, watchedRootForm]);

  const isCancelledRef = useRef(false);

  const handleChipClick = useCallback(
    (preset) => {
      const current = form.getFieldValue("user_intent");
      if (!current || !current.trim()) {
        form.setFieldsValue({ user_intent: preset });
      } else if (!current.includes(preset)) {
        form.setFieldsValue({ user_intent: `${current}, ${preset}` });
      }
    },
    [form]
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
    isCancelledRef.current = false;
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
            if (
              values.monitoring_forms &&
              Array.isArray(values.monitoring_forms) &&
              values.monitoring_forms.length > 0
            ) {
              aiPayload.monitoring_forms = values.monitoring_forms;
            }
            if (values.user_intent && values.user_intent.trim()) {
              aiPayload.user_intent = values.user_intent.trim();
            }
            const aiRes = await dashboardAi.suggestDashboard(aiPayload);
            if (isCancelledRef.current) {
              return null;
            }
            if (aiRes?.data?.widgets && Array.isArray(aiRes.data.widgets)) {
              starterWidgets = aiRes.data.widgets;
            }
          } catch (aiErr) {
            if (isCancelledRef.current) {
              return null;
            }
            message.warning(
              text.dashboardAiFallbackWarning ||
                "Could not generate AI starter widgets. Creating empty dashboard instead."
            );
          }
        }

        if (isCancelledRef.current) {
          return null;
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
        if (!res || isCancelledRef.current) {
          return;
        }
        form.resetFields();
        onCreate(res.data);
      })
      .catch((err) => {
        if (err?.errorFields) {
          // validation error, ant design handles display
        }
      })
      .finally(() => {
        if (!isCancelledRef.current) {
          setSubmitting(false);
        }
      });
  }, [form, onCreate, doCreate, text]);

  const handleCancel = useCallback(() => {
    isCancelledRef.current = true;
    setSubmitting(false);
    form.resetFields();
    onCancel();
  }, [form, onCancel]);

  const modalOkText = useMemo(() => {
    if (submitting && watchedAutoAi) {
      return text.dashboardGeneratingAi || "Generating with AI...";
    }
    return text.dashboardCreateBtn || "Create dashboard";
  }, [submitting, watchedAutoAi, text]);

  return (
    <Modal
      title={text.dashboardCreateTitle || "Create a dashboard"}
      open={visible}
      onOk={handleOk}
      onCancel={handleCancel}
      okText={modalOkText}
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
            extra={
              <span className="dashboards-modal-subhint">
                {text.dashboardEmbedHint}
              </span>
            }
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
              registrationForms.length > 0 ? (
                <span className="dashboards-modal-subhint">
                  {text.dashboardFormExtra ||
                    "This dashboard will show data from this form and its monitoring forms. This cannot be changed later."}
                </span>
              ) : null
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
              <>
                <div className="dashboards-modal-intent-chips">
                  <span className="dashboards-modal-chips-label">
                    {text.dashboardAiPresetsLabel || "Quick presets:"}
                  </span>
                  {INTENT_PRESETS.map((preset) => (
                    <Tag
                      key={preset}
                      className="dashboards-modal-intent-chip"
                      onClick={() => handleChipClick(preset)}
                    >
                      + {preset}
                    </Tag>
                  ))}
                </div>
                {availableMonitoringForms.length > 0 && (
                  <Form.Item
                    name="monitoring_forms"
                    label={
                      text.dashboardAiMonitoringFormsLabel ||
                      "Monitoring Forms to Include"
                    }
                    extra={
                      <span className="dashboards-modal-subhint">
                        {text.dashboardAiMonitoringFormsHint ||
                          "Optionally choose specific monitoring forms for the AI starter dashboard (defaults to all)"}
                      </span>
                    }
                  >
                    <Select
                      mode="multiple"
                      placeholder="All monitoring forms"
                      allowClear
                      showSearch
                      optionFilterProp="children"
                    >
                      {availableMonitoringForms.map((mf) => (
                        <Select.Option key={mf.id} value={mf.id}>
                          {mf.name}
                        </Select.Option>
                      ))}
                    </Select>
                  </Form.Item>
                )}
                <Form.Item
                  name="user_intent"
                  label={
                    text.dashboardAiIntentLabel ||
                    "Dashboard Goal & Questions (Optional)"
                  }
                  extra={
                    <span className="dashboards-modal-subhint">
                      {text.dashboardAiIntentHint ||
                        "Tell the AI what insights you are looking for (e.g. 'Overview of borehole status and functional breakdown', max 250 chars)"}
                    </span>
                  }
                  rules={[
                    {
                      max: 250,
                      message:
                        text.dashboardAiIntentMax ||
                        "Dashboard goal cannot exceed 250 characters",
                    },
                  ]}
                >
                  <Input.TextArea
                    rows={2}
                    maxLength={250}
                    showCount
                    placeholder="e.g. Overview of borehole functionality and regional water access"
                  />
                </Form.Item>
                {submitting && (
                  <div className="dashboards-ai-generating-status">
                    <Spin size="small" />
                    <span>
                      {text.dashboardAiGeneratingStatus ||
                        "Analyzing form questions and crafting AI starter layout..."}
                    </span>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </Form>
    </Modal>
  );
};

export default CreateDashboardModal;
