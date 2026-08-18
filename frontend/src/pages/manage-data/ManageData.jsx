import React, { useState, useMemo } from "react";
import { Row, Col, Divider, Tabs, Space } from "antd";

import { store, uiText } from "../../lib";
import { DataFilters, Breadcrumbs, DescriptionPanel } from "../../components";
import { ManageDataMap, ManageDataTable } from "./components";

const { TabPane } = Tabs;

import "./style.scss";
import { CompassOutlined, TableOutlined } from "@ant-design/icons";

const ManageData = () => {
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [activeTab, setActiveTab] = useState("data-list");
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState("registration");

  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);
  // Get form_id from URL as default selectedForm
  const formIdFromUrl = new URLSearchParams(window.location.search).get(
    "form_id"
  );

  const handleViewModeChange = (value) => {
    setViewMode(value);
    setSelectedRowKeys([]);
  };

  return (
    <div id="manageData">
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
                  title: text.manageDataTitle,
                },
              ]}
            />
            {activeTab === "data-list" && (
              <DescriptionPanel
                description={text.manageDataText}
                title={text.manageDataTitle}
              />
            )}
          </Col>
        </Row>
      </div>

      <div className="table-section">
        <div className="table-wrapper">
          <DataFilters
            selectedRowKeys={selectedRowKeys}
            search={search}
            onSearchChange={setSearch}
            viewMode={viewMode}
            onViewModeChange={handleViewModeChange}
          />
          <Divider style={{ marginBottom: 8 }} />
          <div
            style={{ padding: 0, minHeight: "40vh" }}
            bodystyle={{ padding: 0 }}
          >
            <Tabs
              className="manage-data-tab"
              activeKey={activeTab}
              onChange={setActiveTab}
            >
              <TabPane
                tab={
                  <Space size="small">
                    <span>
                      <TableOutlined style={{ marginRight: 0 }} />
                    </span>
                    <span>{text.manageDataTabList}</span>
                  </Space>
                }
                key="data-list"
              >
                <ManageDataTable
                  {...{
                    formIdFromUrl,
                    selectedRowKeys,
                    setSelectedRowKeys,
                    search,
                    viewMode,
                  }}
                />
              </TabPane>
              <TabPane
                tab={
                  <Space size="small" align="start">
                    <span>
                      <CompassOutlined style={{ marginRight: 0 }} />
                    </span>
                    <span>{text.manageDataTabMap}</span>
                  </Space>
                }
                key="data-map"
              >
                <ManageDataMap />
              </TabPane>
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(ManageData);
