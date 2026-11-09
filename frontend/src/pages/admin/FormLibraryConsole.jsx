import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Row,
  Col,
  Table,
  Button,
  Tag,
  Space,
  Input,
  Empty,
  Popconfirm,
} from "antd";
import { PlusOutlined, SearchOutlined, TagsOutlined } from "@ant-design/icons";
import { api, store, uiText } from "../../lib";
import { useNotification } from "../../util/hooks";
import PromoteTemplateModal from "./PromoteTemplateModal";
import ManageCategoriesModal from "./ManageCategoriesModal";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 400;

const FormLibraryConsole = () => {
  const { notify } = useNotification();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang] || uiText.en, [activeLang]);

  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [categoriesOpen, setCategoriesOpen] = useState(false);

  useEffect(() => {
    const handler = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handler);
  }, [searchInput]);

  const loadTemplates = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
    if (search) {
      params.set("search", search);
    }
    api
      .get(`/manage/forms/library?${params.toString()}`)
      .then((res) => {
        setTemplates(res.data.data || []);
        setTotal(res.data.total || 0);
      })
      .catch(() => setTemplates([]))
      .finally(() => setLoading(false));
  }, [page, search]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

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

  const columns = [
    { title: text.consoleFLNameCol, dataIndex: "name", key: "name" },
    {
      title: text.consoleFLCategoriesCol,
      key: "categories",
      render: (_, r) =>
        (r.categories || []).length === 0
          ? "—"
          : r.categories.map((c) => <Tag key={c.id}>{c.name}</Tag>),
    },
    {
      title: text.consoleFLUsedCol,
      key: "import_count",
      render: (_, r) => r.import_count || 0,
    },
    {
      title: text.consoleFLMonitoringCol,
      key: "monitoring_count",
      render: (_, r) => r.monitoring_count || 0,
    },
    {
      title: text.consoleFLActionsCol,
      key: "actions",
      render: (_, r) => (
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
              onClick={() => setPromoteOpen(true)}
            >
              {text.consoleFLPromoteButton}
            </Button>
          </Space>
        </Col>
      </Row>
      <Row style={{ marginBottom: 16 }}>
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
      </Row>
      {!loading && templates.length === 0 ? (
        <Empty description={text.consoleFLEmpty} />
      ) : (
        <Table
          columns={columns}
          dataSource={templates}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            total,
            pageSize: PAGE_SIZE,
            showSizeChanger: false,
            onChange: (p) => setPage(p),
          }}
        />
      )}
      <PromoteTemplateModal
        open={promoteOpen}
        text={text}
        onClose={() => setPromoteOpen(false)}
        onPromoted={() => {
          setPromoteOpen(false);
          loadTemplates();
        }}
      />
      <ManageCategoriesModal
        open={categoriesOpen}
        text={text}
        onClose={() => setCategoriesOpen(false)}
      />
    </div>
  );
};

export default FormLibraryConsole;
