import React, { useState, useEffect, useMemo, useCallback } from "react";
import "./style.scss";
import {
  Row,
  Col,
  Divider,
  Table,
  ConfigProvider,
  Empty,
  Button,
  Space,
  Select,
  Modal,
} from "antd";
import { useNavigate } from "react-router-dom";
import {
  DownCircleOutlined,
  LeftCircleOutlined,
  PlusOutlined,
} from "@ant-design/icons";

import { api, store, uiText } from "../../lib";
import {
  AdministrationDropdown,
  Breadcrumbs,
  DescriptionPanel,
  RemoveFiltersButton,
} from "../../components";
import FormDropdown from "../../components/filters/FormDropdown";
import DraftDetail from "./DraftDetail";
import { useNotification } from "../../util/hooks";
import { Can } from "../../components/can";

const ManageDraft = () => {
  const [loading, setLoading] = useState(false);
  const [dataset, setDataset] = useState([]);
  const [query, setQuery] = useState("");
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [updateRecord, setUpdateRecord] = useState(true);
  const [activeFilter, setActiveFilter] = useState(null);
  const [childForm, setChildForm] = useState(null);

  const navigate = useNavigate();
  const { notify } = useNotification();

  const formIdFromUrl = new URLSearchParams(window.location.search).get(
    "form_id"
  );

  const {
    language,
    administration,
    selectedForm,
    user,
    forms: registrationForms,
  } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const selectedAdministration = useMemo(() => {
    return administration?.[administration.length - 1];
  }, [administration]);

  const isAdministrationLoaded = useMemo(() => {
    return (
      selectedAdministration?.id === user?.administration?.id ||
      administration?.length > 1
    );
  }, [selectedAdministration, administration, user?.administration?.id]);

  const childrenForms = useMemo(() => {
    return window?.forms?.filter((f) => f?.content?.parent === selectedForm);
  }, [selectedForm]);

  const goToAddForm = () => {
    navigate(`/control-center/data/draft/${selectedForm}`, {
      state: { formId: selectedForm },
    });
  };

  const handleChange = (e) => {
    setUpdateRecord(true);
    setCurrentPage(e.current);
  };

  const handleOnDelete = (row, setDeleting) => {
    Modal.confirm({
      title: text.deleteDraftTitle,
      content: text.deleteDraftContent?.replace("{{draftName}}", row?.name),
      okText: text.deleteText,
      cancelText: text.cancelButton,
      onOk: () => {
        setLoading(true);
        setDeleting(true);
        api
          .delete(`draft-submission/${row.id}`)
          .then(() => {
            setDataset(dataset.filter((d) => d.id !== row.id));
            notify({
              type: "success",
              message: text.deleteDraftSuccess,
            });
          })
          .catch((e) => {
            console.error(e);
            notify({
              type: "error",
              message: text.deleteDraftError,
            });
          })
          .finally(() => {
            setLoading(false);
            setDeleting(false);
          });
      },
    });
  };

  const fetchData = useCallback(() => {
    const formId = formIdFromUrl || childForm || selectedForm;
    const isRegForm = registrationForms.some(
      (f) => f.id === parseInt(formId, 10) && f.content?.parent === null
    );
    if (formIdFromUrl !== null) {
      const isChildForm = childrenForms.some(
        (f) => f.id === parseInt(formId, 10) && f.content?.parent
      );
      if (isChildForm) {
        setChildForm(parseInt(formId, 10));
      }
    }
    if (formIdFromUrl && isRegForm) {
      store.update((s) => {
        s.selectedForm = parseInt(formIdFromUrl, 10);
      });
    }
    if (formId && isAdministrationLoaded && updateRecord) {
      setUpdateRecord(false);
      setLoading(true);
      let url = `/draft-submissions/${formId}/?page=${currentPage}`;
      if (selectedAdministration?.id) {
        url += `&administration=${selectedAdministration.id}`;
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
    updateRecord,
    formIdFromUrl,
    registrationForms,
    childForm,
    childrenForms,
  ]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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

  useEffect(() => {
    const unsubscribe = store.subscribe(
      (s) => s.selectedForm,
      () => {
        setChildForm(null);
        setUpdateRecord(true);
      }
    );
    return () => {
      unsubscribe();
    };
  }, []);

  return (
    <div id="manage-draft">
      <div className="description-container">
        <Row justify="space-between">
          <Col>
            <Breadcrumbs
              pagePath={[
                {
                  title: text.controlCenter,
                  link: "/control-center",
                },
                {
                  title: text.manageDraftTitle,
                },
              ]}
            />
            <DescriptionPanel
              description={text.manageDraftText}
              title={text.manageDataTitle}
            />
          </Col>
        </Row>
      </div>

      <div className="table-section">
        <div className="table-wrapper">
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <Row>
              <Col flex={1}>
                <Space>
                  <FormDropdown
                    loading={loading}
                    width="100%"
                    style={{ minWidth: 300 }}
                  />
                  <Select
                    value={childForm}
                    onChange={(value) => {
                      setChildForm(value);
                      setQuery("");
                      setUpdateRecord(true);
                      setCurrentPage(1);
                    }}
                    fieldNames={{ label: "name", value: "id" }}
                    options={childrenForms}
                    placeholder={text.selectFormPlaceholder}
                    style={{ width: "100%", minWidth: 300 }}
                    allowClear
                  />
                </Space>
              </Col>
              <Col>
                <Can I="manage" a="draft">
                  <Button
                    shape="round"
                    icon={<PlusOutlined />}
                    type="primary"
                    onClick={goToAddForm}
                  >
                    {text.addNewButton}
                  </Button>
                </Can>
              </Col>
            </Row>
            <Row>
              <Col>
                <Space>
                  <AdministrationDropdown loading={loading} />
                  <RemoveFiltersButton />
                </Space>
              </Col>
            </Row>
          </Space>
          <Divider />
          <div
            style={{ padding: 0, minHeight: "40vh" }}
            bodystyle={{ padding: 0 }}
          >
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
                columns={[
                  {
                    title: "Last Updated",
                    dataIndex: "updated",
                    render: (cell, row) => cell || row.created,
                  },
                  {
                    title: "Name",
                    dataIndex: "name",
                    key: "name",
                    filtered: true,
                    filteredValue: query.trim() === "" ? [] : [query],
                    onFilter: (value, filters) =>
                      filters.name.toLowerCase().includes(value.toLowerCase()),
                  },
                  {
                    title: "Region",
                    dataIndex: "administration",
                  },
                  Table.EXPAND_COLUMN,
                ]}
                expandable={{
                  expandedRowRender: (record) => (
                    <DraftDetail
                      onDelete={handleOnDelete}
                      {...{ record, childrenForms }}
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
                rowClassName="row-normal sticky"
                rowKey="id"
                expandRowByClick
              />
            </ConfigProvider>
          </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(ManageDraft);
