import React, {
  useEffect,
  useState,
  useMemo,
  useCallback,
  useContext,
} from "react";
import dayjs from "dayjs";
import customParseFormat from "dayjs/plugin/customParseFormat";
import { useNavigate } from "react-router-dom";
import {
  Row,
  Col,
  Table,
  Button,
  Empty,
  Space,
  Tabs,
  Input,
  Select,
  Popconfirm,
  Tooltip,
  Dropdown,
  Modal,
} from "antd";
import {
  PlusOutlined,
  SearchOutlined,
  PlusSquareOutlined,
  MinusSquareOutlined,
  UploadOutlined,
  MoreOutlined,
} from "@ant-design/icons";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { FormStatusTag, ImportFormModal } from "./components";
import { api, store, uiText, REGISTRATION_FORM } from "../../lib";
import { useNotification } from "../../util/hooks";
import "./style.scss";
import { AbilityContext, Can } from "../../components/can";

dayjs.extend(customParseFormat);

const SEARCH_DEBOUNCE_MS = 400;
const regExpFilename = /filename="(?<filename>.*)"/;

const FormBuilderList = () => {
  const navigate = useNavigate();
  const { notify } = useNotification();

  const [forms, setForms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const [activeTab, setActiveTab] = useState("active");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [expandedKeys, setExpandedKeys] = useState([]);
  const [importModalOpen, setImportModalOpen] = useState(false);

  const { language, user } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const isArchivedTab = activeTab === "archived";
  const isSuperuser = Boolean(user?.is_superuser);
  const hasFormDelete =
    isSuperuser || (user?.roles || []).some((r) => r.can_form_delete);

  const pagePath = [
    { title: "Control Center", link: "/control-center" },
    { title: text.menuFormBuilder },
  ];
  const ability = useContext(AbilityContext);

  // Debounce the search input, resetting to the first page on change.
  useEffect(() => {
    const handler = setTimeout(() => {
      setSearch(searchInput.trim());
      setCurrentPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handler);
  }, [searchInput]);

  const loadForms = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ page: currentPage });
    if (isArchivedTab) {
      params.set("archived", "true");
    } else if (statusFilter) {
      params.set("status", statusFilter);
    }
    if (typeFilter) {
      params.set("type", typeFilter);
    }
    if (search) {
      params.set("search", search);
    }
    api
      .get(`/manage/forms?${params.toString()}`)
      .then((res) => {
        setForms(res.data.data);
        setTotalCount(res.data.total);
      })
      .catch((err) => {
        console.error("Failed to load forms", err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [currentPage, isArchivedTab, statusFilter, typeFilter, search]);

  useEffect(() => {
    loadForms();
  }, [loadForms]);

  // Expand every registration row that has monitoring children by default
  // whenever the list (re)loads; the user can still collapse individual rows.
  useEffect(() => {
    setExpandedKeys(
      forms.filter((f) => f.children && f.children.length > 0).map((f) => f.id)
    );
  }, [forms]);

  const onTabChange = (key) => {
    setActiveTab(key);
    setCurrentPage(1);
  };

  const runAction = (request, successMsg, errorMsg) => {
    request
      .then(() => {
        notify({ type: "success", message: successMsg });
        loadForms();
      })
      .catch((err) => {
        notify({
          type: "error",
          message: err?.response?.data?.message || errorMsg,
        });
      });
  };

  const onPublish = (id) =>
    runAction(
      api.post(`/manage/forms/${id}/publish`, {}),
      text.formBuilderPublishSuccess,
      text.formBuilderPublishError
    );

  const onArchive = (id) =>
    runAction(
      api.post(`/manage/forms/${id}/archive`, {}),
      text.formBuilderArchiveSuccess,
      text.formBuilderArchiveError
    );

  const onRestore = (id) =>
    runAction(
      api.post(`/manage/forms/${id}/restore`, {}),
      text.formBuilderRestoreSuccess,
      text.formBuilderRestoreError
    );

  const onDuplicate = (id) =>
    runAction(
      api.post(`/manage/forms/${id}/duplicate`, {}),
      text.formBuilderDuplicateSuccess,
      text.formBuilderDuplicateError
    );

  const onDelete = (id) =>
    runAction(
      api.delete(`/manage/forms/${id}`),
      text.formBuilderDeleteSuccess,
      text.formBuilderDeleteError
    );

  const onExport = (id) => {
    api
      .get(`/manage/forms/${id}/export`, { responseType: "blob" })
      .then((res) => {
        const contentDispositionHeader = res.headers["content-disposition"];
        const filename = regExpFilename.exec(contentDispositionHeader)?.groups
          ?.filename;
        if (!filename) {
          notify({ type: "error", message: text.formBuilderExportError });
          return;
        }
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => {
        notify({ type: "error", message: text.formBuilderExportError });
      });
  };

  const formatDate = (value) => {
    if (!value) {
      return "—";
    }
    const parsed = dayjs(
      value,
      ["DD-MM-YYYY HH:mm:ss", "YYYY-MM-DDTHH:mm:ssZ", dayjs.ISO_8601],
      true
    );
    if (!parsed.isValid()) {
      return value;
    }
    return parsed.format("MMM D, YYYY, h:mm A");
  };

  const nameColumn = {
    title: text.formBuilderNameCol,
    dataIndex: "name",
    key: "name",
  };

  const typeColumn = {
    title: text.formBuilderTypeCol,
    key: "type",
    render: (_, record) =>
      record.parent
        ? text.formBuilderMonitoringType
        : text.formBuilderRegistrationType,
  };

  const statusColumn = {
    title: text.formBuilderStatusCol,
    key: "status",
    render: (_, record) => <FormStatusTag status={record.status} text={text} />,
  };

  const versionColumn = {
    title: text.formBuilderVersionCol,
    key: "version",
    render: (_, record) => record.version || 1,
  };

  const renderActiveActions = (_, record) => {
    const canCreateMonitoring =
      record.status === "published" && record.type === REGISTRATION_FORM;
    const menuItems = [{ key: "export", label: text.formBuilderExportButton }];
    if (record.status === "draft" && ability.can("publish", "form-builder")) {
      menuItems.push({ key: "publish", label: text.formBuilderPublishButton });
    }
    if (canCreateMonitoring) {
      menuItems.push({
        key: "create-monitoring",
        label: text.formBuilderCreateMonitoringButton,
      });
    }

    if (ability.can("create", "form-builder")) {
      menuItems.push({
        key: "duplicate",
        label: text.formBuilderDuplicateButton,
      });
    }

    if (ability.can("delete", "form-builder")) {
      menuItems.push({ type: "divider" });
      menuItems.push({
        key: "archive",
        label: text.formBuilderArchiveButton,
        danger: true,
      });
    }

    const onMenuClick = ({ key }) => {
      if (key === "duplicate") {
        onDuplicate(record.id);
      } else if (key === "export") {
        onExport(record.id);
      } else if (key === "publish") {
        Modal.confirm({
          title: text.formBuilderPublishConfirmTitle,
          content: text.formBuilderPublishConfirmDesc,
          okText: text.formBuilderPublishButton,
          onOk: () => onPublish(record.id),
        });
      } else if (key === "create-monitoring") {
        navigate(`/control-center/form-builder/create?parent_id=${record.id}`);
      } else if (key === "archive") {
        Modal.confirm({
          title: text.formBuilderArchiveConfirmTitle,
          content: text.formBuilderArchiveConfirmDesc(
            record.submission_count || 0
          ),
          okText: text.formBuilderArchiveButton,
          okButtonProps: { danger: true },
          onOk: () => onArchive(record.id),
        });
      }
    };

    return (
      <Space size="small">
        <Can I="edit" a="form-builder">
          <Button
            shape="round"
            onClick={() => {
              navigate(`/control-center/form-builder/${record.id}/edit`);
            }}
          >
            {text.editButton}
          </Button>
        </Can>
        <Dropdown
          trigger={["click"]}
          menu={{ items: menuItems, onClick: onMenuClick }}
        >
          <Button shape="round" icon={<MoreOutlined />} />
        </Dropdown>
      </Space>
    );
  };

  const renderDeletePermanently = (record) => {
    if (record.submission_count === 0) {
      return (
        <Can I="delete" a="form-builder">
          <Popconfirm
            title={text.formBuilderDeleteConfirmTitle}
            description={text.formBuilderDeleteConfirmDesc}
            okText={text.formBuilderDeleteButton}
            okButtonProps={{ danger: true }}
            onConfirm={() => onDelete(record.id)}
          >
            <Button shape="round" danger>
              {text.formBuilderDeleteButton}
            </Button>
          </Popconfirm>
        </Can>
      );
    }
    return (
      <Tooltip title={text.formBuilderDeleteDisabledTooltip}>
        <Can I="delete" a="form-builder">
          <Button shape="round" danger disabled>
            {text.formBuilderDeleteButton}
          </Button>
        </Can>
      </Tooltip>
    );
  };

  const renderArchivedActions = (_, record) => (
    <Space size="middle" wrap>
      <Can I="delete" a="form-builder">
        <Popconfirm
          title={text.formBuilderRestoreConfirmTitle}
          description={text.formBuilderRestoreConfirmDesc}
          okText={text.formBuilderRestoreButton}
          onConfirm={() => onRestore(record.id)}
        >
          <Button shape="round" type="primary">
            {text.formBuilderRestoreButton}
          </Button>
        </Popconfirm>
      </Can>
      {hasFormDelete && renderDeletePermanently(record)}
    </Space>
  );

  // Show the expand toggle only for registration forms that actually have
  // monitoring children; otherwise render a fixed-width spacer so the Name
  // column stays aligned.
  const renderExpandIcon = ({ expanded, onExpand, record }) => {
    const hasChildren = record.children && record.children.length > 0;
    if (!hasChildren) {
      return <span style={{ display: "inline-block", width: 17 }} />;
    }
    return (
      <Button
        type="text"
        size="small"
        style={{ marginRight: 4 }}
        icon={expanded ? <MinusSquareOutlined /> : <PlusSquareOutlined />}
        onClick={(e) => onExpand(record, e)}
      />
    );
  };

  const columns = isArchivedTab
    ? [
        nameColumn,
        typeColumn,
        statusColumn,
        versionColumn,
        {
          title: text.formBuilderArchivedAtCol,
          key: "archived",
          render: (_, record) => formatDate(record.deleted_at),
        },
        {
          title: text.formBuilderActionsCol,
          key: "actions",
          render: renderArchivedActions,
        },
      ]
    : [
        {
          title: text.formBuilderLastUpdatedCol,
          dataIndex: "updated",
          key: "updated",
          render: (val, record) => formatDate(val || record.created),
        },
        nameColumn,
        typeColumn,
        statusColumn,
        versionColumn,
        {
          title: text.formBuilderActionsCol,
          key: "actions",
          render: renderActiveActions,
        },
      ];

  // Strip empty children arrays so AntD does not render an expand toggle
  // on registration forms that have no monitoring children.
  const dataSource = useMemo(
    () =>
      forms.map((form) => {
        if (form.children && form.children.length > 0) {
          return form;
        }
        const copy = { ...form };
        delete copy.children;
        return copy;
      }),
    [forms]
  );

  return (
    <div id="form-builder-list">
      <div className="description-container">
        <Row justify="space-between">
          <Col>
            <Breadcrumbs pagePath={pagePath} />
            <DescriptionPanel
              title={text.menuFormBuilder}
              description={text.formBuilderDescription}
            />
          </Col>
        </Row>
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <Row justify="space-between" align="middle" wrap>
            <Col>
              <Tabs activeKey={activeTab} onChange={onTabChange}>
                <Tabs.TabPane tab={text.formBuilderTabActive} key="active" />
                <Tabs.TabPane
                  tab={text.formBuilderTabArchived}
                  key="archived"
                />
              </Tabs>
            </Col>
            {!isArchivedTab && (
              <Col>
                <Can I="create" a="form-builder">
                  <Space>
                    <Button
                      shape="round"
                      icon={<UploadOutlined />}
                      onClick={() => {
                        setImportModalOpen(true);
                      }}
                    >
                      {text.formBuilderImportButton}
                    </Button>
                    <Button
                      shape="round"
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() => {
                        navigate("/control-center/form-builder/create");
                      }}
                    >
                      {text.formBuilderCreateButton}
                    </Button>
                  </Space>
                </Can>
              </Col>
            )}
          </Row>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col>
              <Input
                allowClear
                prefix={<SearchOutlined />}
                placeholder={text.formBuilderSearchPlaceholder}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                style={{ width: 240 }}
              />
            </Col>
            {!isArchivedTab && (
              <Col>
                <Select
                  value={statusFilter}
                  style={{ width: 180 }}
                  onChange={(val) => {
                    setStatusFilter(val);
                    setCurrentPage(1);
                  }}
                  options={[
                    { value: "", label: text.formBuilderFilterStatusAll },
                    {
                      value: "draft",
                      label: text.formBuilderStatusDraft,
                    },
                    {
                      value: "published",
                      label: text.formBuilderStatusPublished,
                    },
                  ]}
                />
              </Col>
            )}
            <Col>
              <Select
                value={typeFilter}
                style={{ width: 180 }}
                onChange={(val) => {
                  setTypeFilter(val);
                  setCurrentPage(1);
                }}
                options={[
                  { value: "", label: text.formBuilderFilterTypeAll },
                  {
                    value: "registration",
                    label: text.formBuilderRegistrationType,
                  },
                  {
                    value: "monitoring",
                    label: text.formBuilderMonitoringType,
                  },
                ]}
              />
            </Col>
          </Row>
          {!loading && dataSource.length === 0 ? (
            <Empty description={text.formBuilderEmptyText} />
          ) : (
            <Table
              columns={columns}
              dataSource={dataSource}
              rowKey="id"
              loading={loading}
              childrenColumnName="children"
              expandable={{
                expandIcon: renderExpandIcon,
                expandedRowKeys: expandedKeys,
                onExpandedRowsChange: setExpandedKeys,
              }}
              pagination={{
                current: currentPage,
                total: totalCount,
                pageSize: 10,
                onChange: (page) => {
                  setCurrentPage(page);
                },
              }}
            />
          )}
        </div>
      </div>
      <ImportFormModal
        open={importModalOpen}
        onClose={() => {
          setImportModalOpen(false);
        }}
        onImported={loadForms}
        text={text}
      />
    </div>
  );
};

export default FormBuilderList;
