import React, { useEffect, useMemo, useState } from "react";
import { Modal, Form, Select, Spin } from "antd";
import { api } from "../../lib";
import { useNotification } from "../../util/hooks";

// Path 1 (D-7): a curator promotes a published registration family from any
// workspace into the Library. The source is never modified.
const PromoteTemplateModal = ({ open, text, onClose, onPromoted }) => {
  const { notify } = useNotification();
  const [form] = Form.useForm();

  const [tenants, setTenants] = useState([]);
  const [categories, setCategories] = useState([]);
  const [sourceForms, setSourceForms] = useState([]);
  const [loadingSources, setLoadingSources] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [tenantId, setTenantId] = useState(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    form.resetFields();
    setSourceForms([]);
    setTenantId(null);
    api
      .get("admin/tenants/summary?page=1&ordering=subdomain")
      .then((res) => setTenants(res.data?.data || []))
      .catch(() => setTenants([]));
    api
      .get("/manage/form-categories")
      .then((res) => setCategories(res.data || []))
      .catch(() => setCategories([]));
  }, [open, form]);

  useEffect(() => {
    if (!tenantId) {
      setSourceForms([]);
      return;
    }
    setLoadingSources(true);
    api
      .get(`/manage/library/source-forms?tenant=${tenantId}`)
      .then((res) => setSourceForms(res.data?.data || []))
      .catch(() => setSourceForms([]))
      .finally(() => setLoadingSources(false));
  }, [tenantId]);

  const tenantOptions = useMemo(
    () =>
      tenants.map((t) => ({
        value: t.id,
        label: t.name || t.subdomain,
      })),
    [tenants]
  );

  const onSubmit = () => {
    form.validateFields().then((values) => {
      setSubmitting(true);
      api
        .post("/manage/library/promote", {
          source_form_id: values.source_form_id,
          category_ids: values.category_ids || [],
        })
        .then(() => {
          notify({ type: "success", message: text.consoleFLPromoteSuccess });
          onPromoted();
        })
        .catch((err) => {
          notify({
            type: "error",
            message: err?.response?.data?.message || text.consoleFLPromoteError,
          });
        })
        .finally(() => setSubmitting(false));
    });
  };

  return (
    <Modal
      open={open}
      title={text.consoleFLPromoteTitle}
      okText={text.consoleFLPromoteButton}
      onOk={onSubmit}
      confirmLoading={submitting}
      onCancel={onClose}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="tenant_id"
          label={text.consoleFLWorkspaceLabel}
          rules={[{ required: true, message: text.consoleFLWorkspaceRequired }]}
        >
          <Select
            showSearch
            optionFilterProp="label"
            placeholder={text.consoleFLWorkspacePlaceholder}
            options={tenantOptions}
            onChange={(val) => {
              setTenantId(val);
              form.resetFields(["source_form_id"]);
            }}
          />
        </Form.Item>
        <Form.Item
          name="source_form_id"
          label={text.consoleFLSourceLabel}
          rules={[{ required: true, message: text.consoleFLSourceRequired }]}
        >
          <Select
            showSearch
            optionFilterProp="label"
            placeholder={text.consoleFLSourcePlaceholder}
            disabled={!tenantId || loadingSources}
            notFoundContent={loadingSources ? <Spin size="small" /> : null}
            options={sourceForms.map((f) => ({ value: f.id, label: f.name }))}
          />
        </Form.Item>
        <Form.Item name="category_ids" label={text.consoleFLCategoriesLabel}>
          <Select
            mode="multiple"
            allowClear
            optionFilterProp="label"
            placeholder={text.consoleFLCategoriesPlaceholder}
            options={categories.map((c) => ({ value: c.id, label: c.name }))}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default PromoteTemplateModal;
