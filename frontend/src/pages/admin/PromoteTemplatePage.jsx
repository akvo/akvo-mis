import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Row,
  Col,
  Card,
  Select,
  Button,
  Tabs,
  Space,
  Spin,
  Empty,
  Typography,
} from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { api, store, uiText } from "../../lib";
import { useNotification } from "../../util/hooks";
import { FormOutline } from "../form-library/FormLibraryPreview";
import "../form-library/style.scss";

const { Title } = Typography;

const PromoteTemplatePage = () => {
  const navigate = useNavigate();
  const { notify } = useNotification();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang] || uiText.en, [activeLang]);

  const [tenants, setTenants] = useState([]);
  const [categories, setCategories] = useState([]);
  const [sourceForms, setSourceForms] = useState([]);
  const [tenantId, setTenantId] = useState(null);
  const [sourceId, setSourceId] = useState(null);
  const [categoryIds, setCategoryIds] = useState([]);

  const [loadingSources, setLoadingSources] = useState(false);
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .get("admin/tenants/summary?page=1&ordering=subdomain")
      .then((res) => setTenants(res.data?.data || []))
      .catch(() => setTenants([]));
    api
      .get("/manage/form-categories")
      .then((res) => setCategories(res.data || []))
      .catch(() => setCategories([]));
  }, []);

  // Workspace changed → reset the source + preview and load that workspace's
  // published registration families.
  useEffect(() => {
    setSourceId(null);
    setPreview(null);
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

  // Source form changed → preview its family inline (curator cross-tenant
  // read via the source-forms endpoint's ?preview param).
  const loadPreview = useCallback(() => {
    if (!sourceId) {
      setPreview(null);
      return;
    }
    setLoadingPreview(true);
    api
      .get(`/manage/library/source-forms?preview=${sourceId}`)
      .then((res) => setPreview(res.data))
      .catch(() => setPreview(null))
      .finally(() => setLoadingPreview(false));
  }, [sourceId]);

  useEffect(() => {
    loadPreview();
  }, [loadPreview]);

  const tenantOptions = useMemo(
    () => tenants.map((t) => ({ value: t.id, label: t.name || t.subdomain })),
    [tenants]
  );

  const onPromote = () => {
    if (!sourceId) {
      return;
    }
    setSubmitting(true);
    api
      .post("/manage/library/promote", {
        source_form_id: sourceId,
        category_ids: categoryIds,
      })
      .then(() => {
        notify({ type: "success", message: text.consoleFLPromoteSuccess });
        navigate("/admin/form-library");
      })
      .catch((err) => {
        notify({
          type: "error",
          message: err?.response?.data?.message || text.consoleFLPromoteError,
        });
      })
      .finally(() => setSubmitting(false));
  };

  const registration = preview?.registration;
  const monitoring = preview?.monitoring || [];

  return (
    <div id="promote-template-page">
      <Space align="center" style={{ marginBottom: 12 }}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate("/admin/form-library")}
        >
          {text.consoleFLBack}
        </Button>
      </Space>
      <Title level={3} style={{ marginTop: 0 }}>
        {text.consoleFLPromoteTitle}
      </Title>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <div style={{ fontWeight: 500, marginBottom: 6 }}>
              {text.consoleFLWorkspaceLabel}
            </div>
            <Select
              showSearch
              optionFilterProp="label"
              style={{ width: "100%" }}
              placeholder={text.consoleFLWorkspacePlaceholder}
              options={tenantOptions}
              value={tenantId}
              onChange={setTenantId}
            />
          </Col>
          <Col xs={24} md={8}>
            <div style={{ fontWeight: 500, marginBottom: 6 }}>
              {text.consoleFLSourceLabel}
            </div>
            <Select
              showSearch
              optionFilterProp="label"
              style={{ width: "100%" }}
              placeholder={text.consoleFLSourcePlaceholder}
              disabled={!tenantId || loadingSources}
              notFoundContent={loadingSources ? <Spin size="small" /> : null}
              value={sourceId}
              onChange={setSourceId}
              options={sourceForms.map((f) => ({
                value: f.id,
                label: f.name,
              }))}
            />
          </Col>
          <Col xs={24} md={8}>
            <div style={{ fontWeight: 500, marginBottom: 6 }}>
              {text.consoleFLCategoriesLabel}
            </div>
            <Select
              mode="multiple"
              allowClear
              optionFilterProp="label"
              style={{ width: "100%" }}
              placeholder={text.consoleFLCategoriesPlaceholder}
              value={categoryIds}
              onChange={setCategoryIds}
              options={categories.map((c) => ({ value: c.id, label: c.name }))}
            />
          </Col>
        </Row>
      </Card>

      <Card
        title={text.consoleFLPreviewHeading}
        style={{ marginBottom: 16 }}
        bodyStyle={{ minHeight: 240 }}
      >
        <Spin spinning={loadingPreview}>
          {!registration ? (
            <Empty description={text.consoleFLPreviewEmpty} />
          ) : (
            <Tabs>
              <Tabs.TabPane
                tab={registration.name || text.formLibraryRegistrationTab}
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
      </Card>

      <Row justify="end">
        <Space>
          <Button onClick={() => navigate("/admin/form-library")}>
            {text.consoleFLCancel}
          </Button>
          <Button
            type="primary"
            disabled={!sourceId}
            loading={submitting}
            onClick={onPromote}
          >
            {text.consoleFLPromoteButton}
          </Button>
        </Space>
      </Row>
    </div>
  );
};

export default PromoteTemplatePage;
