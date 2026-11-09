import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  Row,
  Col,
  Card,
  Tag,
  Button,
  Input,
  Select,
  Empty,
  Space,
  Pagination,
  Spin,
} from "antd";
import {
  SearchOutlined,
  DownloadOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { AbilityContext } from "../../components/can";
import { api, store, uiText } from "../../lib";
import { useNotification } from "../../util/hooks";
import FormLibraryPreview from "./FormLibraryPreview";
import "./style.scss";

const PAGE_SIZE = 12;
const SEARCH_DEBOUNCE_MS = 400;

const FormLibrary = () => {
  const navigate = useNavigate();
  const { notify } = useNotification();
  const ability = useContext(AbilityContext);

  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang] || uiText.en, [activeLang]);

  const [templates, setTemplates] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [category, setCategory] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [usingId, setUsingId] = useState(null);
  const [previewId, setPreviewId] = useState(null);

  const canUse = ability.can("create", "form-builder");

  const pagePath = [
    { title: text.controlCenter, link: "/control-center" },
    { title: text.menuFormBuilder, link: "/control-center/form-builder" },
    { title: text.formLibraryTitle },
  ];

  useEffect(() => {
    const handler = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handler);
  }, [searchInput]);

  useEffect(() => {
    api
      .get("/manage/form-categories")
      .then((res) => setCategories(res.data || []))
      .catch(() => setCategories([]));
  }, []);

  const loadTemplates = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
    if (category) {
      params.set("category", category);
    }
    if (search) {
      params.set("search", search);
    }
    api
      .get(`/manage/forms/library?${params.toString()}`)
      .then((res) => {
        setTemplates(res.data.data || []);
        setTotal(res.data.total || 0);
      })
      .catch((err) => {
        console.error("Failed to load form library", err);
        setTemplates([]);
      })
      .finally(() => setLoading(false));
  }, [page, category, search]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const onUse = (template) => {
    setUsingId(template.id);
    api
      .post(`/manage/forms/library/${template.id}/use`, {})
      .then(() => {
        notify({ type: "success", message: text.formLibraryUseSuccess });
        // Land on the Form Builder list, not the registration's edit page:
        // the clone is a whole family (registration + monitoring forms) and
        // each is published separately, so the list is where the user works
        // through them one by one.
        navigate("/control-center/form-builder");
      })
      .catch((err) => {
        notify({
          type: "error",
          message: err?.response?.data?.message || text.formLibraryUseError,
        });
      })
      .finally(() => setUsingId(null));
  };

  const renderCard = (template) => {
    const monitoringCount = template.monitoring_count || 0;
    return (
      <Col key={template.id} xs={24} sm={12} md={12} lg={12} xl={8} xxl={6}>
        <Card
          className="form-library-card"
          title={template.name}
          hoverable
          actions={[
            <Button
              key="preview"
              type="link"
              icon={<EyeOutlined />}
              onClick={() => setPreviewId(template.id)}
            >
              {text.formLibraryPreviewButton}
            </Button>,
            canUse ? (
              <Button
                key="use"
                type="link"
                icon={<DownloadOutlined />}
                loading={usingId === template.id}
                onClick={() => onUse(template)}
              >
                {text.formLibraryUseButton}
              </Button>
            ) : (
              <span key="use-disabled" className="form-library-card-muted">
                {text.formLibraryViewOnly}
              </span>
            ),
          ]}
        >
          <Space direction="vertical" size="small" style={{ width: "100%" }}>
            <div className="form-library-card-tags">
              {(template.categories || []).length === 0 ? (
                <Tag>{text.formLibraryUncategorized}</Tag>
              ) : (
                template.categories.map((c) => <Tag key={c.id}>{c.name}</Tag>)
              )}
            </div>
            <div className="form-library-card-meta">
              <span>
                {text.formLibraryUsedCount}: {template.import_count || 0}
              </span>
              {monitoringCount > 0 && (
                <span>
                  {" · "}
                  {monitoringCount} {text.formLibraryMonitoringLabel}
                </span>
              )}
            </div>
          </Space>
        </Card>
      </Col>
    );
  };

  return (
    <div id="form-library">
      <div className="description-container">
        <Row justify="space-between">
          <Col>
            <Breadcrumbs pagePath={pagePath} />
            <DescriptionPanel
              title={text.formLibraryTitle}
              description={text.formLibraryDescription}
            />
          </Col>
        </Row>
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col>
              <Input
                allowClear
                prefix={<SearchOutlined />}
                placeholder={text.formLibrarySearchPlaceholder}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                style={{ width: 240 }}
              />
            </Col>
            <Col>
              <Select
                value={category}
                style={{ width: 220 }}
                onChange={(val) => {
                  setCategory(val);
                  setPage(1);
                }}
                options={[
                  { value: "", label: text.formLibraryAllCategories },
                  ...categories.map((c) => ({
                    value: String(c.id),
                    label: c.name,
                  })),
                ]}
              />
            </Col>
          </Row>
          <Spin spinning={loading}>
            {!loading && templates.length === 0 ? (
              <Empty description={text.formLibraryEmptyText} />
            ) : (
              <>
                <Row gutter={[16, 16]} align="stretch">
                  {templates.map(renderCard)}
                </Row>
                {total > PAGE_SIZE && (
                  <Row justify="end" style={{ marginTop: 16 }}>
                    <Pagination
                      current={page}
                      total={total}
                      pageSize={PAGE_SIZE}
                      showSizeChanger={false}
                      onChange={(p) => setPage(p)}
                    />
                  </Row>
                )}
              </>
            )}
          </Spin>
        </div>
      </div>
      <FormLibraryPreview
        templateId={previewId}
        text={text}
        canUse={canUse}
        onClose={() => setPreviewId(null)}
        onUse={(tpl) => {
          setPreviewId(null);
          onUse(tpl);
        }}
      />
    </div>
  );
};

export default FormLibrary;
