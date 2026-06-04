import React, { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Row, Col, Table, Button, Empty } from "antd";
import { PlusOutlined, EditOutlined } from "@ant-design/icons";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { FormStatusTag } from "./components";
import { api, store, uiText } from "../../lib";

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
      title: "Name",
      dataIndex: "name",
      key: "name",
    },
    {
      title: "Type",
      key: "type",
      render: (_, record) => (record.parent ? "Monitoring" : "Registration"),
    },
    {
      title: "Status",
      key: "status",
      render: (_, record) => (
        <FormStatusTag status={record.status} text={text} />
      ),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_, record) => (
        <Button
          type="link"
          icon={<EditOutlined />}
          onClick={() => {
            navigate(`/control-center/form-builder/${record.id}/edit`);
          }}
        >
          Edit
        </Button>
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
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  navigate("/control-center/form-builder/create");
                }}
              >
                New Form
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
