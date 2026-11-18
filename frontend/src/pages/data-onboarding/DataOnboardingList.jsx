import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button, Table, Tag } from "antd";
import dayjs from "dayjs";
import { Breadcrumbs } from "../../components";
import { api, store, uiText } from "../../lib";

const formatDate = (value) => dayjs(value).format("YYYY-MM-DD HH:mm");

const DataOnboardingList = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const { active: activeLang } = store.useState((s) => s.language);
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  useEffect(() => {
    api
      .get("/data-onboarding")
      .then((res) => setRows(res.data))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, []);

  const pagePath = [
    { title: text.controlCenter, link: "/control-center" },
    { title: text.menuFormBuilder, link: "/control-center/form-builder" },
    { title: text.dataOnboardingHistory },
  ];

  return (
    <div id="data-onboarding-list">
      <div className="description-container">
        <Breadcrumbs pagePath={pagePath} />
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <Link to="/control-center/data-onboarding/create">
            <Button type="primary" shape="round" style={{ marginBottom: 16 }}>
              {text.formBuilderDataOnboardingButton}
            </Button>
          </Link>
          <Table
            rowKey="id"
            loading={loading}
            columns={[
              {
                title: text.dataOnboardingFile,
                dataIndex: "file_name",
                render: (name, r) => (
                  <Link to={`/control-center/data-onboarding/${r.id}`}>
                    {name}
                  </Link>
                ),
              },
              {
                title: text.dataOnboardingStatus,
                dataIndex: "status",
                render: (status) => <Tag>{status}</Tag>,
              },
              { title: text.dataOnboardingCreatedBy, dataIndex: "created_by" },
              {
                title: text.dataOnboardingCreated,
                dataIndex: "created",
                render: formatDate,
              },
              {
                title: text.dataOnboardingUpdated,
                dataIndex: "updated",
                render: formatDate,
              },
            ]}
            dataSource={rows}
          />
        </div>
      </div>
    </div>
  );
};

export default DataOnboardingList;
