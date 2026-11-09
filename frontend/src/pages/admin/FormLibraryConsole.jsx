import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Row,
  Col,
  Table,
  Button,
  Tag,
  Space,
  Input,
  Select,
  Empty,
  Popconfirm,
} from "antd";
import {
  PlusOutlined,
  SearchOutlined,
  TagsOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import { api, store, uiText, MONITORING_FORM } from "../../lib";
import { useNotification } from "../../util/hooks";
import { FormStatusTag } from "../form-builder/components";
import FormLibraryPreview from "../form-library/FormLibraryPreview";
import ManageCategoriesModal from "./ManageCategoriesModal";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 400;

const FormLibraryConsole = () => {
  const navigate = useNavigate();
  const { notify } = useNotification();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang] || uiText.en, [activeLang]);

  const [templates, setTemplates] = useState([]);
  const [categories, setCategories] = useState([]);
  const [categoryIds, setCategoryIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [categoriesOpen, setCategoriesOpen] = useState(false);
  const [previewFormId, setPreviewFormId] = useState(null);
  const [expandedKeys, setExpandedKeys] = useState([]);

  useEffect(() => {
    const handler = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handler);
  }, [searchInput]);

  const loadCategories = useCallback(() => {
    api
      .get("/manage/form-categories")
      .then((res) => setCategories(res.data || []))
      .catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  const loadTemplates = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
    if (search) {
      params.set("search", search);
    }
    if (categoryIds.length > 0) {
      params.set("category", categoryIds.join(","));
    }
    api
      .get(`/manage/forms/library?${params.toString()}`)
      .then((res) => {
        setTemplates(res.data.data || []);
        setTotal(res.data.total || 0);
      })
      .catch(() => setTemplates([]))
      .finally(() => setLoading(false));
  }, [page, search, categoryIds]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // Nest each monitoring form as an indented sub-row, inheriting the family's
  // categories for display; expand families with children by default.
  const dataSource = useMemo(
    () =>
      templates.map((t) => {
        const children = (t.monitoring || []).map((m) => ({
          ...m,
          _isChild: true,
          categories: t.categories,
        }));
        return children.length > 0 ? { ...t, children } : t;
      }),
    [templates]
  );

  useEffect(() => {
    setExpandedKeys(
      templates.filter((t) => (t.monitoring || []).length > 0).map((t) => t.id)
    );
  }, [templates]);

  const onDelete = (id) => {
    api
      .delete(`/manage/forms/${id}`)
      .then(() => {
        notify({ type: "success", message: text.consoleFLDeleteSuccess });
        loadTemplates();
      })
      .catch((err) => {
        notify({
          type: "error",
          message: err?.response?.data?.message || text.consoleFLDeleteError,
        });
      });
  };

  const previewButton = (id) => (
    <Button
      size="small"
      icon={<EyeOutlined />}
      onClick={() => setPreviewFormId(id)}
    >
      {text.formLibraryPreviewButton}
    </Button>
  );

  const columns = [
    {
      title: text.consoleFLNameCol,
      key: "name",
      render: (_, r) => {
        const isMon = r.type === MONITORING_FORM;
        return (
          <Space direction="vertical" size={2}>
            <Space>
              <Tag color={isMon ? "blue" : "geekblue"}>
                {isMon
                  ? text.formBuilderMonitoringType
                  : text.formBuilderRegistrationType}
              </Tag>
              <span style={{ fontWeight: 500 }}>{r.name}</span>
            </Space>
            {!r._isChild && r.source && (
              <div style={{ color: "rgba(0,0,0,0.35)", fontSize: 11 }}>
                {text.consoleFLPromotedFrom}{" "}
                {r.source.tenant_name || r.source.tenant_id} ·{" "}
                {r.source.promoted_at}
              </div>
            )}
          </Space>
        );
      },
    },
    {
      title: text.consoleFLCategoriesCol,
      key: "categories",
      render: (_, r) =>
        (r.categories || []).length === 0
          ? "—"
          : r.categories.map((c) => <Tag key={c.id}>{c.name}</Tag>),
    },
    {
      title: text.formBuilderStatusCol,
      key: "status",
      render: (_, r) => <FormStatusTag status={r.status} text={text} />,
    },
    {
      title: text.consoleFLUsedCol,
      key: "import_count",
      render: (_, r) => (r._isChild ? "—" : r.import_count || 0),
    },
    {
      title: text.consoleFLMonitoringCol,
      key: "monitoring_count",
      render: (_, r) => (r._isChild ? "—" : (r.monitoring || []).length),
    },
    {
      title: text.consoleFLActionsCol,
      key: "actions",
      render: (_, r) =>
        r._isChild ? (
          previewButton(r.id)
        ) : (
          <Space size="small">
            {previewButton(r.id)}
            <Popconfirm
              title={text.consoleFLDeleteConfirm}
              okText={text.consoleFLDeleteButton}
              okButtonProps={{ danger: true }}
              onConfirm={() => onDelete(r.id)}
            >
              <Button danger size="small">
                {text.consoleFLDeleteButton}
              </Button>
            </Popconfirm>
          </Space>
        ),
    },
  ];

  return (
    <div id="form-library-console">
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <h2 style={{ marginBottom: 0 }}>{text.formLibraryTitle}</h2>
          <p style={{ color: "rgba(0,0,0,0.45)", marginBottom: 0 }}>
            {text.consoleFLDescription}
          </p>
        </Col>
        <Col>
          <Space>
            <Button
              icon={<TagsOutlined />}
              onClick={() => setCategoriesOpen(true)}
            >
              {text.consoleFLManageCategories}
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate("/admin/form-library/promote")}
            >
              {text.consoleFLPromoteButton}
            </Button>
          </Space>
        </Col>
      </Row>
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder={text.formLibrarySearchPlaceholder}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            style={{ width: 260 }}
          />
        </Col>
        <Col>
          <Select
            mode="multiple"
            allowClear
            value={categoryIds}
            style={{ minWidth: 260 }}
            placeholder={text.formLibraryAllCategories}
            optionFilterProp="label"
            onChange={(vals) => {
              setCategoryIds(vals);
              setPage(1);
            }}
            options={categories.map((c) => ({ value: c.id, label: c.name }))}
          />
        </Col>
      </Row>
      {!loading && templates.length === 0 ? (
        <Empty description={text.consoleFLEmpty} />
      ) : (
        <Table
          columns={columns}
          dataSource={dataSource}
          rowKey="id"
          loading={loading}
          childrenColumnName="children"
          expandable={{
            expandedRowKeys: expandedKeys,
            onExpandedRowsChange: setExpandedKeys,
          }}
          pagination={{
            current: page,
            total,
            pageSize: PAGE_SIZE,
            showSizeChanger: false,
            onChange: (p) => setPage(p),
          }}
        />
      )}
      <ManageCategoriesModal
        open={categoriesOpen}
        text={text}
        onClose={() => {
          setCategoriesOpen(false);
          loadCategories();
        }}
      />
      <FormLibraryPreview
        formId={previewFormId}
        text={text}
        canUse={false}
        onClose={() => setPreviewFormId(null)}
        onUse={() => setPreviewFormId(null)}
      />
    </div>
  );
};

export default FormLibraryConsole;
