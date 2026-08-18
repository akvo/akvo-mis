import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Table,
  ConfigProvider,
  Empty,
  Modal,
  Tag,
  Tooltip,
  Button,
  Row,
  Col,
} from "antd";
import { useNavigate } from "react-router-dom";
import { isEmpty, union, xor, without } from "lodash";
import { LeftCircleOutlined, DownCircleOutlined } from "@ant-design/icons";

import { api, store, uiText } from "../../../lib";
import { generateAdvanceFilterURL } from "../../../util/filter";
import { useNotification } from "../../../util/hooks";
import DataDetail from "../DataDetail";

const ManageDataTable = ({
  selectedRowKeys,
  setSelectedRowKeys,
  formIdFromUrl = null,
  search = "",
  viewMode = "registration",
}) => {
  const [loading, setLoading] = useState(false);
  const [dataset, setDataset] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [updateRecord, setUpdateRecord] = useState(true);
  const [activeFilter, setActiveFilter] = useState(null);
  const [sortBy, setSortBy] = useState("latest_activity");
  const [sortType, setSortType] = useState("descend");
  const [editedRecord, setEditedRecord] = useState({});
  const [deleteData, setDeleteData] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const navigate = useNavigate();
  const { notify } = useNotification();

  const isMonitoringView = viewMode !== "registration";

  const { administration, selectedForm, user } = store.useState(
    (state) => state
  );
  const { language, advancedFilters, dateRange } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const goToMonitoring = (record) => {
    store.update((s) => {
      s.selectedFormData = record;
    });
    navigate(`/control-center/data/${selectedForm}/monitoring/${record.id}`);
  };

  const goToParentContext = useCallback(
    (record) => {
      if (record?.parent_form_id && record?.parent_id) {
        navigate(
          `/control-center/data/${record.parent_form_id}/monitoring/${record.parent_id}?form_id=${viewMode}`
        );
      }
    },
    [navigate, viewMode]
  );

  const handleDeleteData = () => {
    if (deleteData?.id) {
      setDeleting(true);
      api
        .delete(`data/${deleteData.id}`)
        .then(() => {
          notify({
            type: "success",
            message: `${deleteData.name} deleted`,
          });
          setDataset(dataset.filter((d) => d.id !== deleteData.id));
          setDeleteData(null);
          setTotalCount((prev) => Math.max(0, prev - 1));
        })
        .catch((err) => {
          notify({
            type: "error",
            message: "Could not delete datapoint",
          });
          console.error(err?.response);
        })
        .finally(() => {
          setDeleting(false);
        });
    }
  };

  const selectedAdministration = useMemo(() => {
    return administration?.[administration.length - 1];
  }, [administration]);

  const isAdministrationLoaded = useMemo(() => {
    return (
      selectedAdministration?.id === user?.administration?.id ||
      administration?.length > 1
    );
  }, [selectedAdministration, administration, user?.administration?.id]);

  const handleChange = (e, _, sorter) => {
    const newPage = e.current;
    const defaultSortField = isMonitoringView ? "created" : "latest_activity";
    const newSortBy = sorter?.field || defaultSortField;
    const newSortType = sorter?.order || null;

    const sortChanged = sortBy !== newSortBy || sortType !== newSortType;
    if (sortChanged) {
      setSortBy(newSortBy);
      setSortType(newSortType);
      setCurrentPage(1);
    } else if (newPage !== currentPage) {
      setCurrentPage(newPage);
    }
    setUpdateRecord(true);
  };

  const onSelectTableRow = ({ id }) => {
    selectedRowKeys.includes(id)
      ? setSelectedRowKeys(without(selectedRowKeys, id))
      : setSelectedRowKeys([...selectedRowKeys, id]);
  };

  const onSelectAllTableRow = (isSelected) => {
    const hasSelected = !isEmpty(selectedRowKeys);
    const ids = dataset.filter((x) => !x?.disabled).map((x) => x.id);
    if (!isSelected && hasSelected) {
      setSelectedRowKeys(xor(selectedRowKeys, ids));
    }
    if (isSelected && !hasSelected) {
      setSelectedRowKeys(ids);
    }
    if (isSelected && hasSelected) {
      setSelectedRowKeys(union(selectedRowKeys, ids));
    }
  };

  useEffect(() => {
    if (
      isAdministrationLoaded &&
      selectedAdministration?.id &&
      activeFilter !== selectedAdministration?.id
    ) {
      setActiveFilter(selectedAdministration.id);
      if (!updateRecord) {
        setCurrentPage(1);
        setUpdateRecord(true);
      }
    }
  }, [
    activeFilter,
    selectedAdministration,
    isAdministrationLoaded,
    updateRecord,
  ]);

  const fetchData = useCallback(() => {
    const formId = isMonitoringView ? viewMode : formIdFromUrl || selectedForm;
    if (formIdFromUrl && !isMonitoringView) {
      store.update((s) => {
        s.selectedForm = parseInt(formIdFromUrl, 10);
      });
    }
    if (formId && isAdministrationLoaded && updateRecord) {
      setUpdateRecord(false);
      setLoading(true);
      let url = `/form-data/${formId}/?page=${currentPage}`;
      if (selectedAdministration?.id) {
        url += `&administration=${selectedAdministration.id}`;
      }
      if (search) {
        url += `&search=${encodeURIComponent(search)}`;
      }
      if (advancedFilters && advancedFilters.length) {
        url = generateAdvanceFilterURL(advancedFilters, url);
      }
      if (dateRange && dateRange.length === 2) {
        const dateFrom = dateRange[0].format("YYYY-MM-DD");
        const dateTo = dateRange[1].format("YYYY-MM-DD");
        url += `&date_from=${dateFrom}&date_to=${dateTo}`;
      }
      if (sortBy) {
        url += `&sort_by=${sortBy}`;
      }
      if (sortType) {
        url += `&sort_type=${sortType}`;
      }
      api
        .get(url)
        .then((res) => {
          setDataset(res.data.data);
          setTotalCount(res.data.total);
          if (res.data.total < currentPage) {
            setCurrentPage(1);
          }
          setLoading(false);
        })
        .catch(() => {
          setDataset([]);
          setTotalCount(0);
          setLoading(false);
        });
    }
  }, [
    selectedForm,
    selectedAdministration,
    currentPage,
    isAdministrationLoaded,
    advancedFilters,
    dateRange,
    updateRecord,
    formIdFromUrl,
    search,
    sortBy,
    sortType,
    isMonitoringView,
    viewMode,
  ]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    const unsubscribe = store.subscribe(
      (s) => s.selectedForm,
      () => {
        setUpdateRecord(true);
        setCurrentPage(1);
        setSelectedRowKeys([]);
      }
    );
    return () => {
      unsubscribe();
    };
  }, [setSelectedRowKeys]);

  useEffect(() => {
    setSelectedRowKeys([]);
  }, [administration, setSelectedRowKeys]);

  useEffect(() => {
    setCurrentPage(1);
    setUpdateRecord(true);
  }, [search]);

  useEffect(() => {
    setCurrentPage(1);
    setUpdateRecord(true);
  }, [dateRange]);

  useEffect(() => {
    setCurrentPage(1);
    setSortBy(isMonitoringView ? "created" : "latest_activity");
    setSortType("descend");
    setUpdateRecord(true);
    setSelectedRowKeys([]);
  }, [viewMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const registrationColumns = useMemo(
    () => [
      {
        title: text.recentActivityCol,
        dataIndex: "latest_activity",
        key: "latest_activity",
        width: 210,
        sorter: true,
        sortDirections: ["descend", "ascend"],
        sortOrder: sortBy === "latest_activity" ? sortType : null,
        render: (cell, row) => {
          const displayDate = cell || row.updated || row.created;
          const source = row.latest_activity_source || text.initialRegistration;
          return (
            <div>
              <div>{displayDate}</div>
              <div style={{ fontSize: 12, color: "#888" }}>{source}</div>
            </div>
          );
        },
        onCell: (record) => ({
          onClick: () => goToMonitoring(record),
        }),
      },
      {
        title: text.nameCol,
        dataIndex: "name",
        key: "name",
        filtered: true,
        onFilter: (value, filters) =>
          filters.name.toLowerCase().includes(value.toLowerCase()),
        onCell: (record) => ({
          onClick: () => goToMonitoring(record),
        }),
      },
      {
        title: text.userCol,
        dataIndex: "created_by",
        onCell: (record) => ({
          onClick: () => goToMonitoring(record),
        }),
      },
      {
        title: text.regionCol,
        dataIndex: "administration",
        onCell: (record) => ({
          onClick: () => goToMonitoring(record),
        }),
      },
      {
        title: text.totalMonitoring,
        dataIndex: "total_children",
        width: 120,
        sorter: true,
        sortDirections: ["descend", "ascend"],
        sortOrder: sortBy === "total_children" ? sortType : null,
        onCell: (record) => ({
          onClick: () => goToMonitoring(record),
        }),
      },
    ],
    [text, sortBy, sortType, selectedForm] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const monitoringColumns = useMemo(
    () => [
      {
        title: text.submissionDateCol || "Submission Date",
        dataIndex: "created",
        key: "created",
        sorter: true,
        sortDirections: ["descend", "ascend"],
        sortOrder: sortBy === "created" ? sortType : null,
        render: (cell, row) => cell || row.updated,
      },
      {
        title: text.datapointCol || "Datapoint",
        dataIndex: "parent_name",
        key: "parent_name",
      },
      {
        title: text.channelCol || "Channel",
        dataIndex: "submitter",
        key: "submitter",
        render: (submitter) =>
          submitter ? (
            <Tooltip title={submitter}>
              <Tag color="green">{text.mobileAppText}</Tag>
            </Tooltip>
          ) : (
            <Tag color="blue">{text.webformText}</Tag>
          ),
      },
      {
        title: text.userCol || "User",
        dataIndex: "created_by",
        key: "created_by",
      },
      {
        title: text.regionCol || "Region",
        dataIndex: "administration",
        key: "administration",
      },
      Table.EXPAND_COLUMN,
    ],
    [text, sortBy, sortType]
  );

  const columns = isMonitoringView ? monitoringColumns : registrationColumns;

  const expandableConfig = isMonitoringView
    ? {
        expandedRowRender: (record) => (
          <DataDetail
            record={record}
            updater={() => setUpdateRecord(true)}
            updateRecord={updateRecord}
            setDeleteData={setDeleteData}
            editedRecord={editedRecord}
            setEditedRecord={setEditedRecord}
            goToParentContext={() => goToParentContext(record)}
          />
        ),
        expandIcon: ({ expanded, onExpand, record }) =>
          expanded ? (
            <DownCircleOutlined
              onClick={(e) => onExpand(record, e)}
              style={{ color: "#1651B6", fontSize: "19px" }}
            />
          ) : (
            <LeftCircleOutlined
              onClick={(e) => onExpand(record, e)}
              style={{ color: "#1651B6", fontSize: "19px" }}
            />
          ),
        expandRowByClick: true,
      }
    : null;

  return (
    <div>
      <ConfigProvider
        renderEmpty={() => (
          <Empty
            description={
              selectedForm ? text.noFormText : text.noFormSelectedText
            }
          />
        )}
      >
        <Table
          columns={columns}
          dataSource={dataset}
          loading={loading}
          onChange={handleChange}
          pagination={{
            current: currentPage,
            total: totalCount,
            pageSize: 10,
            showSizeChanger: false,
            showTotal: (total, range) =>
              `Results: ${range[0]} - ${range[1]} of ${total} data`,
          }}
          rowClassName={(record) => {
            if (!isMonitoringView) {
              return "row-normal sticky";
            }
            const rowEdited = editedRecord[record.id]
              ? "row-edited"
              : "row-normal sticky";
            return `expandable-row ${rowEdited}`;
          }}
          rowKey="id"
          rowSelection={{
            selectedRowKeys: selectedRowKeys,
            onSelect: onSelectTableRow,
            onSelectAll: onSelectAllTableRow,
          }}
          expandable={expandableConfig}
        />
      </ConfigProvider>
      <Modal
        open={Boolean(deleteData)}
        onCancel={() => setDeleteData(null)}
        centered
        width="575px"
        footer={
          <Row justify="center" align="middle">
            <Col span={14}>&nbsp;</Col>
            <Col span={10}>
              <Button
                className="light"
                disabled={deleting}
                onClick={() => {
                  setDeleteData(null);
                }}
              >
                {text.cancelButton}
              </Button>
              <Button
                type="primary"
                danger
                loading={deleting}
                onClick={handleDeleteData}
              >
                {text.deleteText}
              </Button>
            </Col>
          </Row>
        }
      >
        <div style={{ textAlign: "center", padding: "20px" }}>
          <h2>Delete Datapoint?</h2>
          <p>
            Are you sure you want to delete <b>{deleteData?.name}</b>?
          </p>
        </div>
      </Modal>
    </div>
  );
};

export default ManageDataTable;
