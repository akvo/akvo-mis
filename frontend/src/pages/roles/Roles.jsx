import React, { useState, useCallback, useEffect, useMemo } from "react";
import "./style.scss";
import { Row, Col, Button, Divider, Table, Input, Modal } from "antd";
import { Link } from "react-router-dom";
import {
  LeftCircleOutlined,
  DownCircleOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import debounce from "lodash/debounce";
import { api, store, uiText } from "../../lib";
import RoleDetail from "./RoleDetail";
import { Breadcrumbs, DescriptionPanel } from "../../components";

const { Search } = Input;

const RolesPage = () => {
  const [loading, setLoading] = useState(true);
  const [dataset, setDataset] = useState([]);
  const [deleting, setDeleting] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);

  const { language } = store.useState((s) => s);
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
      title: text.manageRoles,
    },
  ];

  const columns = [
    {
      title: text.roleAdmLevel,
      dataIndex: "administration_level",
      render: (obj) => obj?.name,
    },
    {
      title: text.roleName,
      dataIndex: "name",
    },
    {
      title: text.roleDescription,
      dataIndex: "description",
    },
    {
      title: text.roleTotalUsers,
      dataIndex: "total_users",
    },
    Table.EXPAND_COLUMN,
  ];

  const handleChange = (e) => {
    setCurrentPage(e.current);
  };

  const handleOnDelete = (record) => {
    Modal.confirm({
      title: text.roleDeleteTitle,
      content: text.roleConfirmDelete.replace("{roleName}", record.name),
      centered: true,
      okText: text.confirm,
      cancelText: text.cancel,
      onOk: async () => {
        setDeleting(true);
        try {
          await api.delete(`role/${record.id}`);
          setDataset((prev) => prev.filter((role) => role.id !== record.id));
          setTotalCount((prev) => prev - 1);
        } catch (error) {
          console.error("Error deleting role:", error);
        } finally {
          setDeleting(false);
        }
      },
    });
  };

  const fetchData = useCallback(
    async (searchQuery) => {
      setLoading(true);
      try {
        let apiURL = `roles?page=${currentPage}&limit=10`;
        if (searchQuery) {
          apiURL += `&search=${encodeURIComponent(searchQuery)}`;
        }
        const response = await api.get(apiURL);
        const { data, total } = response.data;
        setDataset(data);
        setTotalCount(total);
      } catch (error) {
        console.error("Error fetching roles:", error);
      } finally {
        setLoading(false);
      }
    },
    [currentPage]
  );

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div id="roles">
      <div className="description-container">
        <Row justify="space-between" align="bottom">
          <Col>
            <Breadcrumbs pagePath={pagePath} />
            <DescriptionPanel
              description={text.manageRoleText}
              title={text.manageRoles}
            />
          </Col>
        </Row>
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <Row justify="space-between" align="middle">
            <Col span={20}>
              <Search
                placeholder={text.searchPlaceholder}
                onChange={(e) => {
                  // Debounce the search to avoid too many API calls
                  debounce(fetchData, 300)(e.target.value);
                }}
                style={{ width: 260, marginBottom: "1rem" }}
                loading={loading}
                allowClear
              />
            </Col>
            <Col>
              <Link to="/control-center/roles/add">
                <Button type="primary" shape="round" icon={<PlusOutlined />}>
                  {text.addRole}
                </Button>
              </Link>
            </Col>
          </Row>
          <Divider />
          <div
            style={{ padding: 0, minHeight: "40vh" }}
            bodystyle={{ padding: 0 }}
          >
            <Table
              columns={columns}
              dataSource={dataset}
              loading={loading}
              onChange={handleChange}
              pagination={{
                showSizeChanger: false,
                current: currentPage,
                total: totalCount,
                pageSize: 10,
                showTotal: (total, range) =>
                  `Results: ${range[0]} - ${range[1]} of ${total} roles`,
              }}
              rowKey="id"
              expandable={{
                expandedRowRender: (record) => (
                  <RoleDetail
                    record={record}
                    onDelete={handleOnDelete}
                    deleting={deleting}
                  />
                ),
                expandIcon: ({ expanded, onExpand, record }) =>
                  expanded ? (
                    <DownCircleOutlined
                      onClick={(e) => onExpand(record, e)}
                      style={{ color: "#404797", fontSize: "19px" }}
                    />
                  ) : (
                    <LeftCircleOutlined
                      onClick={(e) => onExpand(record, e)}
                      style={{ color: "#404797", fontSize: "19px" }}
                    />
                  ),
              }}
              rowClassName="editable-row expandable-row"
              expandRowByClick
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default RolesPage;
