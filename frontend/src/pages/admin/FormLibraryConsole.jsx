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
  Dropdown,
  Modal,
} from "antd";
import {
  PlusOutlined,
  SearchOutlined,
  TagsOutlined,
  MoreOutlined,
  DownOutlined,
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
  const [savingCatId, setSavingCatId] = useState(null);

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

  const confirmDelete = (r) =>
    Modal.confirm({
      title: text.consoleFLDeleteConfirm,
      okText: text.consoleFLDeleteButton,
      okButtonProps: { danger: true },
      onOk: () => onDelete(r.id),
    });

  // Inline-edit a template's categories straight from the Categories cell.
  const saveRowCategories = (row, ids) => {
    setSavingCatId(row.id);
    api
      .post(`/manage/forms/library/${row.id}/categories`, {
        category_ids: ids,
      })
      .then((res) => {
        const updated = res.data?.categories || [];
        setTemplates((prev) =>
          prev.map((t) => {
            if (t.id === row.id) {
              return { ...t, categories: updated };
            }
            return t;
          })
        );
      })
      .catch((err) => {
        notify({
          type: "error",
          message: err?.response?.data?.message || text.consoleFLCategoryError,
        });
      })
      .finally(() => setSavingCatId(null));
  };

  const rowMenuItems = (r) => {
    const items = [
      { key: "edit", label: text.consoleFLEditButton },
      { key: "preview", label: text.formLibraryPreviewButton },
    ];
    if (!r._isChild && r.status === "published") {
      items.push({ key: "add-monitoring", label: text.consoleFLAddMonitoring });
    }
    if (!r._isChild) {
      items.push({ type: "divider" });
      items.push({
        key: "delete",
        label: text.consoleFLDeleteButton,
        danger: true,
      });
    }
    return items;
  };

  const onRowMenuClick = (r) => (info) => {
    if (info.key === "edit") {
      navigate(`/admin/form-library/${r.id}/edit`);
    } else if (info.key === "preview") {
      setPreviewFormId(r.id);
    } else if (info.key === "add-monitoring") {
      navigate(`/admin/form-library/create?parent_id=${r.id}`);
    } else if (info.key === "delete") {
      confirmDelete(r);
    }
  };

  const newTemplateItems = [
    { key: "promote", label: text.consoleFLFromWorkspace },
    { key: "scratch", label: text.consoleFLFromScratch },
  ];

  const onNewTemplateClick = (info) => {
    navigate(
      info.key === "promote"
        ? "/admin/form-library/promote"
        : "/admin/form-library/create"
    );
  };

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
      width: 280,
      render: (_, r) =>
        r._isChild ? (
          (r.categories || []).length === 0 ? (
            "—"
          ) : (
            r.categories.map((c) => <Tag key={c.id}>{c.name}</Tag>)
          )
        ) : (
          <Select
            mode="multiple"
            size="small"
            bordered={false}
            style={{ width: "100%", minWidth: 200 }}
            placeholder={text.consoleFLCategoriesPlaceholder}
            value={(r.categories || []).map((c) => c.id)}
            loading={savingCatId === r.id}
            maxTagCount="responsive"
            optionFilterProp="label"
            onChange={(ids) => saveRowCategories(r, ids)}
            options={categories.map((c) => ({ value: c.id, label: c.name }))}
          />
        ),
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
      width: 80,
      render: (_, r) => (
        <Dropdown
          trigger={["click"]}
          menu={{ items: rowMenuItems(r), onClick: onRowMenuClick(r) }}
        >
          <Button size="small" icon={<MoreOutlined />} />
        </Dropdown>
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
            <Dropdown
              trigger={["click"]}
              menu={{ items: newTemplateItems, onClick: onNewTemplateClick }}
            >
              <Button type="primary" icon={<PlusOutlined />}>
                {text.consoleFLNewTemplate} <DownOutlined />
              </Button>
            </Dropdown>
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
