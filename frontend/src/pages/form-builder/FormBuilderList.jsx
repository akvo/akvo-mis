import React, { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Row, Col, Table, Button, Empty, Space } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { FormStatusTag } from "./components";
import { api, store, uiText, REGISTRATION_FORM } from "../../lib";

const FormBuilderList = () => {
  const navigate = useNavigate();
  const [forms, setForms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const pagePath = [
    { title: "Control Center", link: "/control-center" },
    { title: text.menuFormBuilder },
  ];

  useEffect(() => {
    setLoading(true);
    api
      .get(`/manage/forms?page=${currentPage}`)
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
  }, [currentPage]);

  const columns = [
    {
      title: text.formBuilderNameCol,
      dataIndex: "name",
      key: "name",
    },
    {
      title: text.formBuilderTypeCol,
      key: "type",
      render: (_, record) =>
        record.parent
          ? text.formBuilderMonitoringType
          : text.formBuilderRegistrationType,
    },
    {
      title: text.formBuilderStatusCol,
      key: "status",
      render: (_, record) => (
        <FormStatusTag status={record.status} text={text} />
      ),
    },
    {
      title: text.formBuilderActionsCol,
      key: "actions",
      render: (_, record) => (
        <Space size="middle">
          <Button
            onClick={() => {
              navigate(`/control-center/form-builder/${record.id}/edit`);
            }}
            shape="round"
          >
            {text.editButton}
          </Button>
          {record.status === "published" && record.type === REGISTRATION_FORM && (
            <Button
              onClick={() => {
                navigate(
                  `/control-center/form-builder/create?parent_id=${record.id}`
                );
              }}
              shape="round"
              type="primary"
            >
              {text.formBuilderCreateMonitoringButton}
            </Button>
          )}
        </Space>
      ),
    },
  ];

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
          <Row justify="end" style={{ marginBottom: 16, marginTop: 16 }}>
            <Col>
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
            </Col>
          </Row>
          {!loading && forms.length === 0 ? (
            <Empty description="No forms found" />
          ) : (
            <Table
              columns={columns}
              dataSource={forms}
              rowKey="id"
              loading={loading}
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
    </div>
  );
};

export default FormBuilderList;
