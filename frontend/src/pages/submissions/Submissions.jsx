import React, { useEffect, useState, useMemo } from "react";
import "./style.scss";
import { Table, Tabs, Button, Modal } from "antd";
import { Breadcrumbs, CreateBatchModal } from "../../components";
import {
  LeftCircleOutlined,
  DownCircleOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import {
  api,
  columnsBatch,
  store,
  uiText,
  columnsPending as defaultPendingCols,
} from "../../lib";
import { useNotification } from "../../util/hooks";
import { getForms } from "../../util/form";
import UploadDetail from "./UploadDetail";
import BatchDetail from "./BatchDetail";
import { DataFilters } from "../../components";
import { isEmpty, union, xor, without, uniq } from "lodash";

const { TabPane } = Tabs;
const { confirm } = Modal;

const Submissions = () => {
  const [dataset, setDataset] = useState([]);
  const [dataTab, setDataTab] = useState("pending-submission");
  const [totalCount, setTotalCount] = useState(0);
  const [modalButton, setModalButton] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [expandedKeys, setExpandedKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [deleting, setDeleting] = useState(false);
  const [search, setSearch] = useState("");
  const { selectedForm, dateRange } = store.useState((state) => state);
  const [editedRecord, setEditedRecord] = useState({});
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const { notify } = useNotification();

  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const pagePath = [
    {
      title: text.controlCenter,
      link: "/control-center",
    },
    {
      title: text.submissionsText,
      link: "/control-center",
    },
    {
      title: getForms().find((x) => x.id === selectedForm)?.name,
    },
  ];

  const columnsPending = [
    ...defaultPendingCols,
    {
      title: "Action",
      dataIndex: "#",
      key: "duration",
      render: (_, row) => (
        <div
          onClick={() => {
            confirm({
              title: "Are you sure to delete this batch?",
              icon: <ExclamationCircleOutlined />,
              content: "Once you have deleted you can't get it back",
              okText: "Yes",
              okType: "danger",
              cancelText: "No",
              onOk() {
                handleDelete(row);
              },
              onCancel() {
                return;
              },
            });
          }}
        >
          <Button shape="round" type="danger" ghost>
            {text.deleteText}
          </Button>
        </div>
      ),
      align: "center",
      width: 100,
    },
  ];

  // Reset date range filter when component mounts
  useEffect(() => {
    store.update((s) => {
      s.dateRange = null;
    });
  }, []);

  useEffect(() => {
    if (selectedForm) {
      setLoading(true);
      let url;
      setExpandedKeys([]);
      if (dataTab === "pending-submission") {
        url = `/form-pending-data/${selectedForm}/?page=${currentPage}`;
        setModalButton(true);
      } else if (dataTab === "pending-approval") {
        url = `batch/?form=${selectedForm}&page=${currentPage}`;
        setModalButton(false);
      } else if (dataTab === "approved") {
        url = `batch/?form=${selectedForm}&page=${currentPage}&approved=true`;
        setModalButton(false);
      }
      // Add search filter if set
      if (search) {
        url += `&search=${encodeURIComponent(search)}`;
      }
      // Add date range filter if set
      if (dateRange && dateRange.length === 2) {
        const dateFrom = dateRange[0].format("YYYY-MM-DD");
        const dateTo = dateRange[1].format("YYYY-MM-DD");
        url += `&date_from=${dateFrom}&date_to=${dateTo}`;
      }
      api
        .get(url)
        .then((res) => {
          setDataset(res.data.data);
          setTotalCount(res.data.total);
        })
        .catch((e) => {
          console.error(e);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [dataTab, currentPage, reload, selectedForm, dateRange, search]);

  useEffect(() => {
    if (selectedForm) {
      setExpandedKeys([]);
      setSelectedRowKeys([]);
    }
  }, [selectedForm, dataTab]);

  // Reset current page when selected form changes
  useEffect(() => {
    const unsubscribe = store.subscribe(
      ({ selectedForm }) => ({ selectedForm }),
      () => {
        setCurrentPage(1);
      }
    );
    return () => unsubscribe();
  }, []);

  const handleChange = (e) => {
    setCurrentPage(e.current);
  };

  const btnBatchSelected = useMemo(() => {
    const handleOnClickBatchSelectedDataset = () => {
      api.get(`form/check-approver/${selectedForm}`).then((res) => {
        if (!res.data.count) {
          notify({
            type: "error",
            message: text.batchNoApproverMessage,
          });
        } else {
          setModalVisible(true);
        }
      });
    };
    return (
      dataTab === "pending-submission" && (
        <Button
          type="primary"
          shape="round"
          onClick={handleOnClickBatchSelectedDataset}
          disabled={!selectedRowKeys?.length && modalButton}
        >
          {text.batchSelectedDatasets}
        </Button>
      )
    );
  }, [
    selectedRowKeys,
    modalButton,
    text.batchSelectedDatasets,
    dataTab,
    notify,
    selectedForm,
    text.batchNoApproverMessage,
  ]);

  const hasSelected = !isEmpty(selectedRowKeys);
  const onSelectTableRow = (val) => {
    const { id } = val;
    const ids = [...selectedRowKeys, id];
    if (val?.parent?.id && val?.parent?.is_pending) {
      ids.push(val.parent.id);
    }
    let rowIds = selectedRowKeys.includes(id)
      ? without(selectedRowKeys, id)
      : uniq(ids);
    rowIds = rowIds.filter((r) => parseInt(r, 10)); // Remove any falsy values
    setSelectedRowKeys(rowIds);
  };

  const onSelectAllTableRow = (isSelected) => {
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

  const handleDelete = (rowInfo) => {
    setDeleting(true);
    api
      .delete(`pending-data/${rowInfo.id}`, { pending_data_id: rowInfo.id })
      .then(() => {
        setDataset(dataset.filter((d) => d.id !== rowInfo.id));
        setDeleting(false);
        notify({
          type: "success",
          message: "Batch deleted",
        });
      })
      .catch((err) => {
        const { status, data } = err.response;
        if (status === 409) {
          notify({
            type: "error",
            message: data?.message || text.userDeleteFail,
          });
        } else {
          notify({
            type: "error",
            message: text.userDeleteFail,
          });
        }
        setDeleting(false);
        console.error(err.response);
      });
  };

  return (
    <div id="submissions">
      <div className="description-container">
        <Breadcrumbs pagePath={pagePath} />
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <DataFilters
            showAdm={false}
            resetFilter={false}
            showSearch={dataTab === "pending-submission"}
            showDateRange={dataTab === "pending-submission"}
            search={search}
            onSearchChange={setSearch}
          />
          <div style={{ padding: 0 }} bodystyle={{ padding: 30 }}>
            <Tabs
              className="main-tab"
              activeKey={dataTab}
              onChange={(key) => {
                setDataTab(key);
                setCurrentPage(1);
                setExpandedKeys([]);
                setSelectedRowKeys([]);
                // Reset search and date range when switching tabs
                setSearch("");
                store.update((s) => {
                  s.dateRange = null;
                });
              }}
              tabBarExtraContent={btnBatchSelected}
            >
              <TabPane
                tab={text.uploadsTab1}
                key="pending-submission"
              ></TabPane>
              <TabPane tab={text.uploadsTab2} key="pending-approval"></TabPane>
              <TabPane tab={text.uploadsTab3} key="approved"></TabPane>
            </Tabs>
            <Table
              className="main-table"
              dataSource={dataset}
              onChange={handleChange}
              columns={
                dataTab === "pending-submission"
                  ? [...columnsPending, Table.EXPAND_COLUMN]
                  : [...columnsBatch, Table.EXPAND_COLUMN]
              }
              rowSelection={
                dataTab === "pending-submission"
                  ? {
                      selectedRowKeys: selectedRowKeys,
                      onSelect: onSelectTableRow,
                      onSelectAll: onSelectAllTableRow,
                      handleDelete: handleDelete,
                      getCheckboxProps: (record) => ({
                        disabled: record?.disabled,
                      }),
                    }
                  : false
              }
              loading={loading}
              pagination={{
                current: currentPage,
                total: totalCount,
                pageSize: 10,
                showSizeChanger: false,
                showTotal: (total, range) =>
                  `Results: ${range[0]} - ${range[1]} of ${total} users`,
              }}
              expandedRowKeys={expandedKeys}
              expandable={{
                expandedRowRender: (record) => {
                  if (dataTab === "pending-submission") {
                    return (
                      <BatchDetail
                        expanded={record}
                        setReload={setReload}
                        setDataset={setDataset}
                        dataset={dataset}
                        handleDelete={handleDelete}
                        deleting={deleting}
                        setEditedRecord={setEditedRecord}
                        editedRecord={editedRecord}
                      />
                    );
                  }
                  return <UploadDetail record={record} setReload={setReload} />;
                },
                expandIcon: ({ expanded, onExpand, record }) => {
                  return expanded ? (
                    <DownCircleOutlined
                      onClick={(e) => {
                        setExpandedKeys(
                          expandedKeys.filter((k) => k !== record.id)
                        );
                        onExpand(record, e);
                      }}
                      style={{ color: "#1651B6", fontSize: "19px" }}
                    />
                  ) : (
                    <LeftCircleOutlined
                      onClick={(e) => {
                        setExpandedKeys([record.id]);
                        onExpand(record, e);
                      }}
                      style={{ color: "#1651B6", fontSize: "19px" }}
                    />
                  );
                },
              }}
              rowKey="id"
              onRow={(record) => ({
                onClick: () => {
                  if (expandedKeys.includes(record.id)) {
                    setExpandedKeys((prevExpandedKeys) =>
                      prevExpandedKeys.filter((key) => key !== record.id)
                    );
                  } else {
                    setExpandedKeys((prevExpandedKeys) => [
                      ...prevExpandedKeys,
                      record.id,
                    ]);
                  }
                },
              })}
              rowClassName={(record) => {
                const rowEdited = editedRecord[record.id]
                  ? "row-edited"
                  : "row-normal";
                return `expandable-row ${rowEdited}`;
              }}
              expandRowByClick
            />
          </div>
        </div>
      </div>
      <CreateBatchModal
        selectedRows={selectedRowKeys}
        isOpen={modalVisible}
        onCancel={() => {
          setModalVisible(false);
        }}
        onSuccess={() => {
          setCurrentPage(1);
          setSelectedRowKeys([]);
          setDataTab("pending-approval");
          setModalVisible(false);
        }}
      />
    </div>
  );
};

export default React.memo(Submissions);
