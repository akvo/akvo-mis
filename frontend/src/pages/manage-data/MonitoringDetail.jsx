import React, {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useContext,
} from "react";
import "./style.scss";
import {
  Row,
  Col,
  Divider,
  Table,
  Typography,
  ConfigProvider,
  Empty,
  Modal,
  Button,
  Space,
  Dropdown,
  Tabs,
  Select,
  Tag,
  Tooltip,
  Spin,
  Input,
} from "antd";
import {
  LeftCircleOutlined,
  DownCircleOutlined,
  DeleteOutlined,
  ArrowLeftOutlined,
  FormOutlined,
  LoadingOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useParams, useNavigate } from "react-router-dom";
import { api, store, uiText } from "../../lib";
import { getForms } from "../../util/form";
import DataDetail from "./DataDetail";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { useNotification } from "../../util/hooks";
import { AbilityContext } from "../../components/can";
import MonitoringOverview from "./MonitoringOverview";

const { Title } = Typography;
const { TabPane } = Tabs;
const questionOverviewTypes = ["number", "date"];

const MonitoringDetail = () => {
  const { form, parentId } = useParams();
  const navigate = useNavigate();

  const {
    language,
    selectedFormData,
    user: authUser,
  } = store.useState((s) => s);
  const childrenForms = useMemo(() => {
    return getForms().filter((f) => `${f.content?.parent}` === form);
  }, [form]);

  // Get form_id from URL as default selectedForm
  const formIdFromUrl = new URLSearchParams(window.location.search).get(
    "form_id"
  );
  const defaultFormId = formIdFromUrl
    ? parseInt(formIdFromUrl, 10)
    : childrenForms[0]?.id;

  const { notify } = useNotification();
  const [loading, setLoading] = useState(false);
  const [dataset, setDataset] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [updateRecord, setUpdateRecord] = useState(
    formIdFromUrl ? true : false
  );
  const [deleteData, setDeleteData] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [editedRecord, setEditedRecord] = useState({});
  const [dataTab, setDataTab] = useState(
    formIdFromUrl ? "monitoring-data" : "registration-data"
  );
  const [selectedForm, setSelectedForm] = useState(defaultFormId);
  const [selectedOverviewQuestion, setSelectedOverviewQuestion] =
    useState(null);
  const [selectedOverviewDate, setSelectedOverviewDate] = useState(null);
  const [search, setSearch] = useState("");
  const ability = useContext(AbilityContext);

  const editable = ability.can("edit", "data") || authUser?.is_superuser;

  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const pagePath = [
    {
      title: text.controlCenter,
      link: "/control-center",
    },
    {
      title: text.manageDataTitle,
      link: "/control-center/data",
    },
    {
      title: text.monitoringDataTitle,
    },
  ];

  const { questionGroups } = store.useState((state) => state);

  const overviewQuestions = useMemo(() => {
    const forms = getForms().filter((f) =>
      selectedForm
        ? f?.id === selectedForm
        : f?.content?.parent === parseInt(form, 10)
    );
    return forms
      .map((f) => f.content.question_group)
      .flat()
      .filter((qg) => qg.question)
      .map((qg) => qg.question)
      .flat()
      .filter((q) => questionOverviewTypes.includes(q.type))
      .map((q) => ({
        id: q.id,
        name: q.label,
        type: q.type,
      }));
  }, [form, selectedForm]);

  const columns = [
    {
      title: text.lastUpdatedCol,
      dataIndex: "updated",
      render: (cell, row) => cell || row.created,
    },
    {
      title: text.nameCol,
      dataIndex: "name",
      key: "name",
    },
    {
      title: text.channelCol,
      dataIndex: "submitter",
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
      title: text.userCol,
      dataIndex: "created_by",
    },
    Table.EXPAND_COLUMN,
  ];

  const handleChange = (e) => {
    setCurrentPage(e.current);
    setUpdateRecord(true);
  };

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
        })
        .catch((err) => {
          notify({
            type: "error",
            message: "Could not delete datapoint",
          });
          console.error(err.response);
        })
        .finally(() => {
          setDeleting(false);
        });
    }
  };

  const goToMonitoringForm = async (form) => {
    const { uuid } = selectedFormData;
    navigate(`/control-center/form/${form}/${uuid}`);
  };

  const onChangeMonitoringForm = (value) => {
    if (formIdFromUrl && formIdFromUrl !== `${value}`) {
      // Reset the URL to remove form_id query parameter
      const url = new URL(window.location.href);
      url.searchParams.delete("form_id");
      window.history.replaceState({}, "", url);
    }
    setSelectedForm(value);
    setSelectedOverviewQuestion(null);
    setSelectedOverviewDate(null);
    setUpdateRecord(true);
    setCurrentPage(1);
  };

  useEffect(() => {
    if (questionGroups.length === 0 && dataset.length > 0) {
      store.update((s) => {
        s.questionGroups = getForms().find(
          (f) => f.id === dataset[0]?.form
        ).content.question_group;
      });
    }
  }, [questionGroups, dataset]);

  const fetchDatapoint = useCallback(async () => {
    if (parentId) {
      const { data: apiData } = await api.get(`/data-details/${parentId}`);
      store.update((s) => {
        s.selectedFormData = apiData;
      });
    }
  }, [parentId]);

  useEffect(() => {
    fetchDatapoint();
  }, [fetchDatapoint]);

  const fetchMonitoringData = useCallback(async () => {
    try {
      if (updateRecord && selectedFormData?.uuid) {
        setUpdateRecord(false);

        setLoading(true);
        const parentUUID = selectedFormData?.uuid;
        let url = `/form-data/${selectedForm}/?page=${currentPage}&parent=${parentUUID}`;
        if (search) {
          url += `&search=${encodeURIComponent(search)}`;
        }
        const { data: apiData } = await api.get(url);
        const { data: dataList, total } = apiData || {};
        setDataset(dataList);
        setTotalCount(total);
        setLoading(false);
      }
    } catch {
      setUpdateRecord(false);
      setLoading(false);
    }
  }, [currentPage, updateRecord, selectedForm, selectedFormData?.uuid, search]);

  useEffect(() => {
    fetchMonitoringData();
  }, [fetchMonitoringData]);

  useEffect(() => {
    setCurrentPage(1);
    setUpdateRecord(true);
  }, [search]);

  return (
    <div id="manageData">
      <div className="description-container">
        <Row justify="space-between">
          <Col>
            <Breadcrumbs pagePath={pagePath} />
            <DescriptionPanel
              description={text.monitoringDataDescription}
              title={text.monitoringDataTitle}
            />
          </Col>
        </Row>
      </div>

      <div className="table-section">
        <div className="table-wrapper">
          <Row justify={"space-between"} align={"middle"}>
            <Col span={6}>
              <Button
                shape="round"
                onClick={() => navigate("/control-center/data")}
                icon={<ArrowLeftOutlined />}
              >
                {text.backManageData}
              </Button>
            </Col>
            <Col span={6} style={{ textAlign: "right" }}>
              <Dropdown
                trigger={["click"]}
                menu={{
                  items: childrenForms.map((form) => ({
                    key: form.id,
                    label: form.name,
                  })),
                  onClick: (e) => goToMonitoringForm(e.key),
                }}
              >
                <Button type="primary" shape="round" icon={<FormOutlined />}>
                  {text.updateDataButton}
                </Button>
              </Dropdown>
            </Col>
          </Row>
          <Divider />
          <Title>{selectedFormData?.name || text.loadingText}</Title>
          <div
            style={{ padding: "16px 0 0", minHeight: "40vh" }}
            bodystyle={{ padding: 0 }}
          >
            <Tabs
              className="manage-data-tab"
              activeKey={dataTab}
              onChange={(activeKey) => {
                if (activeKey === "monitoring-data") {
                  setUpdateRecord(true);
                }
                setDataTab(activeKey);
              }}
            >
              <TabPane tab={text.manageDataTab1} key="registration-data">
                <div className="registration-data-wrapper">
                  <DataDetail
                    record={selectedFormData}
                    updateRecord={updateRecord}
                    updater={setUpdateRecord}
                    setDeleteData={setDeleteData}
                    setEditedRecord={setEditedRecord}
                    editedRecord={editedRecord}
                    isPublic={!editable}
                    isFullScreen
                  />
                </div>
              </TabPane>
              <TabPane tab={text.manageDataTab2} key="monitoring-data">
                <Row style={{ marginBottom: "16px" }}>
                  <Col flex={1}>
                    <Space>
                      <Input
                        prefix={<SearchOutlined />}
                        placeholder={text.searchPlaceholder}
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        allowClear
                        style={{ width: 200 }}
                      />
                      <Select
                        value={selectedForm}
                        onChange={onChangeMonitoringForm}
                        fieldNames={{ label: "name", value: "id" }}
                        options={childrenForms}
                        placeholder={text.selectFormPlaceholder}
                      />
                    </Space>
                  </Col>
                </Row>
                <ConfigProvider
                  renderEmpty={() => <Empty description={text.noFormText} />}
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
                    rowKey="id"
                    expandable={{
                      expandedRowRender: (record) => (
                        <DataDetail
                          record={record}
                          updateRecord={updateRecord}
                          updater={setUpdateRecord}
                          setDeleteData={setDeleteData}
                          setEditedRecord={setEditedRecord}
                          editedRecord={editedRecord}
                          isPublic={!editable}
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
                    }}
                    rowClassName={(record) => {
                      const rowEdited = editedRecord[record.id]
                        ? "row-edited"
                        : "row-normal sticky";
                      return `expandable-row ${rowEdited}`;
                    }}
                    expandRowByClick
                  />
                </ConfigProvider>
              </TabPane>
              <TabPane tab={text.manageDataTab3} key="monitoring-overview">
                <Row style={{ marginBottom: "16px" }}>
                  <Col>
                    <Select
                      value={selectedForm}
                      onChange={onChangeMonitoringForm}
                      fieldNames={{ label: "name", value: "id" }}
                      options={childrenForms}
                      placeholder={text.selectFormPlaceholder}
                    />
                    <Select
                      style={{ marginLeft: "16px", width: "300px" }}
                      prefix="Select Indicator"
                      value={selectedOverviewQuestion?.id || null}
                      onChange={(value) => {
                        setSelectedOverviewQuestion(
                          overviewQuestions.find((q) => q.id === value)
                        );
                      }}
                      fieldNames={{ label: "name", value: "id" }}
                      options={overviewQuestions.filter(
                        (x) => x.type === "number"
                      )}
                      placeholder={text.selectIndicatorPlaceholder}
                    />
                    <Select
                      style={{ marginLeft: "16px", width: "300px" }}
                      prefix="Select Date"
                      value={selectedOverviewDate?.id || null}
                      onChange={(value) => {
                        setSelectedOverviewDate(
                          overviewQuestions.find((q) => q.id === value)
                        );
                      }}
                      fieldNames={{ label: "name", value: "id" }}
                      options={overviewQuestions.filter(
                        (x) => x.type === "date"
                      )}
                      placeholder={text.selectIndicatorPlaceholder}
                    />
                  </Col>
                </Row>
                <ConfigProvider
                  renderEmpty={() => <Empty description={text.noFormText} />}
                ></ConfigProvider>
                <Row>
                  {updateRecord ? (
                    <Space
                      style={{ paddingTop: 18, color: "#9e9e9e9e" }}
                      size="middle"
                    >
                      <Spin
                        indicator={
                          <LoadingOutlined style={{ color: "#1b91ff" }} spin />
                        }
                      />
                      <span>{text.loadingText}</span>
                    </Space>
                  ) : (
                    <MonitoringOverview
                      question={selectedOverviewQuestion}
                      date={selectedOverviewDate}
                    />
                  )}
                </Row>
              </TabPane>
            </Tabs>
          </div>
        </div>
      </div>
      <Modal
        open={deleteData}
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
        bodystyle={{ textAlign: "center" }}
      >
        <Space direction="vertical">
          <DeleteOutlined style={{ fontSize: "50px" }} />
          <p>
            You are about to delete <i>{`${deleteData?.name}`}</i> data.{" "}
            <b>Delete a datapoint also will delete the history</b>. Are you sure
            want to delete this datapoint?
          </p>
        </Space>
      </Modal>
    </div>
  );
};

export default React.memo(MonitoringDetail);
