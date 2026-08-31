import React, { useContext, useEffect, useMemo, useState } from "react";
import { Layout, Menu, Modal } from "antd";
import { store, uiText } from "../../lib";
import api from "../../lib/api";
import { useLocation, useNavigate } from "react-router-dom";
import {
  UserOutlined,
  TableOutlined,
  DatabaseOutlined,
  DashboardOutlined,
  DownloadOutlined,
  BookOutlined,
  FormOutlined,
  AndroidOutlined,
  BarChartOutlined,
} from "@ant-design/icons";
import { AbilityContext } from "../can";

const { Sider } = Layout;

const Sidebar = () => {
  const [firstLoad, setFirstLoad] = useState(true);
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [openKeys, setOpenKeys] = useState([]);
  const [openDownloadAppsModal, setOpenDownloadAppsModal] = useState(false);
  const { user: authUser, administration, language } = store.useState((s) => s);
  const navigate = useNavigate();
  const location = useLocation();
  const lastPath = location.pathname.split("/").pop() || "control-center";

  const { active: activeLang } = language || { active: "en" };
  const text = useMemo(() => {
    return uiText[activeLang] || uiText.en;
  }, [activeLang]);

  const ability = useContext(AbilityContext);

  // Define a mapping between child paths and their parent submenu keys
  const submenuMap = useMemo(
    () => ({
      // Users submenu children
      users: "manage-user",
      tree: "manage-user",
      "mobile-assignment": "manage-user",
      roles: "manage-user",
      approvers: "manage-user",
      // Data submenu children
      data: "manage-data",
      submissions: "manage-data",
      approvals: "manage-data",
      draft: "manage-data",
      // Master data submenu children
      administration: "manage-master-data",
      attributes: "manage-master-data",
      entities: "manage-master-data",
      "entity-types": "manage-master-data",
      organisations: "manage-master-data",
    }),
    []
  );

  const handleResetGlobalFilterState = async () => {
    // reset global filter store when moving page on sidebar click
    store.update((s) => {
      s.filters = {
        trained: null,
        role: null,
        organisation: null,
        query: null,
        attributeType: null,
        entityType: [],
      };
    });
    if (authUser?.administration?.id && administration?.length > 1) {
      try {
        const { data: apiData } = await api.get(
          `administration/${authUser.administration.id}`
        );
        store.update((s) => {
          s.administration = [apiData];
        });
      } catch (error) {
        console.error(error);
      }
    }
  };

  const handleMenuClick = ({ key, item }) => {
    setSelectedKeys([key]);
    // Get the URL from the menu item
    const url = item.props?.["data-url"];
    // Reset global filter state
    handleResetGlobalFilterState();
    // Navigate to the URL
    navigate(url);
  };

  // Handle submenu open state
  const handleOpenChange = (keys) => {
    setOpenKeys(keys);
  };

  useEffect(() => {
    if (
      (selectedKeys.length === 0 && firstLoad) ||
      (selectedKeys.length === 1 &&
        selectedKeys[0] !== `menu-${lastPath}` &&
        !firstLoad)
    ) {
      setFirstLoad(false);

      // Determine which menu item is selected based on the URL path
      const menuKey = `menu-${lastPath}`;
      const keysToSet = [menuKey];

      // Set the selected keys
      setSelectedKeys(keysToSet);

      // Determine which parent submenu should be open
      let submenuToOpen = null;

      // Check if the path is a child of master-data
      if (location.pathname.includes("/master-data/")) {
        submenuToOpen = "manage-master-data";
      }
      // Check the submenu map for other paths
      else if (submenuMap[lastPath]) {
        submenuToOpen = submenuMap[lastPath];
      }
      // Special case for data/submissions
      else if (location.pathname.includes("/data/submissions")) {
        submenuToOpen = "manage-data";
      }

      // Set the open keys if a submenu should be open
      if (submenuToOpen) {
        setOpenKeys([submenuToOpen]);
      }
    }
  }, [lastPath, selectedKeys, firstLoad, location.pathname, submenuMap]);
  return (
    <Sider className="site-layout-background">
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "hidden",
        }}
      >
        <Menu
          mode="inline"
          style={{
            borderRight: 0,
          }}
          onClick={handleMenuClick}
          selectedKeys={selectedKeys}
          openKeys={openKeys}
          onOpenChange={handleOpenChange}
        >
          {/* Control Center */}

          <Menu.Item
            key="menu-control-center"
            icon={<DashboardOutlined />}
            data-url="/control-center"
          >
            {text.menuControlCenter}
          </Menu.Item>

          {/* Users SubMenu */}
          <Menu.SubMenu
            key="manage-user"
            icon={<UserOutlined />}
            title={text.menuUsers}
          >
            {/* Wrap each menu item explicitly with a unique key for Can */}
            {ability.can("manage", "user") && (
              <Menu.Item key="menu-users" data-url="/control-center/users">
                {text.menuManagePlatformUsers}
              </Menu.Item>
            )}
            <Menu.Item
              key="menu-tree"
              data-url="/control-center/approvers/tree"
            >
              {text.menuValidationTree}
            </Menu.Item>
            {ability.can("read", "mobile") && (
              <Menu.Item
                key="menu-mobile-assignment"
                data-url="/control-center/mobile-assignment"
              >
                {text.menuManageMobileUsers}
              </Menu.Item>
            )}
            {ability.can("manage", "roles") && (
              <Menu.Item key="menu-roles" data-url="/control-center/roles">
                {text.menuManageRoles}
              </Menu.Item>
            )}
          </Menu.SubMenu>

          {/* Data SubMenu */}
          <Menu.SubMenu
            key="manage-data"
            icon={<TableOutlined />}
            title={text.menuData}
          >
            <Menu.Item key="menu-data" data-url="/control-center/data">
              {text.menuManageData}
            </Menu.Item>

            {ability.can("manage", "draft") && (
              <Menu.Item key="menu-draft" data-url="/control-center/data/draft">
                {text.menuManageDraft}
              </Menu.Item>
            )}

            {ability.can("manage", "submissions") && (
              <Menu.Item
                key="menu-submissions"
                data-url="/control-center/data/submissions"
              >
                {text.menuPendingSubmissions}
              </Menu.Item>
            )}

            {ability.can("manage", "approvals") && (
              <Menu.Item
                key="menu-approvals"
                data-url="/control-center/approvals"
              >
                {text.menuApprovals}
              </Menu.Item>
            )}
          </Menu.SubMenu>

          {/* Master Data SubMenu */}
          {ability.can("manage", "master-data") && (
            <Menu.SubMenu
              key="manage-master-data"
              icon={<DatabaseOutlined />}
              title={text.menuMasterData}
            >
              <Menu.Item
                key="menu-administration"
                data-url="/control-center/master-data/administration"
              >
                {text.menuAdministrativeList}
              </Menu.Item>
              <Menu.Item
                key="menu-levels"
                data-url="/control-center/master-data/levels"
              >
                {text.menuLevels}
              </Menu.Item>
              <Menu.Item
                key="menu-attributes"
                data-url="/control-center/master-data/attributes"
              >
                {text.menuAttributes}
              </Menu.Item>
              {/* <Menu.Item
              key="menu-entities"
              data-url="/control-center/master-data/entities"
            >
              {text.menuEntities}
            </Menu.Item>
            <Menu.Item
              key="menu-entity-types"
              data-url="/control-center/master-data/entity-types"
            >
              {text.menuEntityTypes}
            </Menu.Item> */}
              <Menu.Item
                key="menu-organisations"
                data-url="/control-center/master-data/organisations"
              >
                {text.menuOrganisations}
              </Menu.Item>
            </Menu.SubMenu>
          )}

          {/* Form builder */}
          {ability.can("read", "form-builder") && (
            <Menu.Item
              key="menu-form-builder"
              icon={<FormOutlined />}
              data-url="/control-center/form-builder"
            >
              {text.menuFormBuilder}
            </Menu.Item>
          )}

          {/* Dashboards */}
          {(ability.can("manage", "dashboard") ||
            ability.can("read", "dashboard")) && (
            <Menu.Item
              key="menu-dashboards"
              icon={<BarChartOutlined />}
              data-url="/control-center/dashboard"
            >
              {text.menuDashboards}
            </Menu.Item>
          )}

          {/* Downloads */}
          {ability.can("read", "downloads") && (
            <Menu.Item
              key="menu-downloads"
              icon={<DownloadOutlined />}
              data-url="/downloads"
            >
              {text.menuDownloads}
            </Menu.Item>
          )}
        </Menu>
      </div>

      <Menu
        mode="inline"
        style={{
          borderRight: 0,
          borderTop: "1px solid #f0f0f0",
          marginTop: "auto",
        }}
        selectable={false}
      >
        {ability.can("manage", "mobile") && (
          <Menu.Item
            key="menu-download-apps"
            icon={<AndroidOutlined />}
            onClick={() => setOpenDownloadAppsModal(true)}
          >
            {text.menuDownloadApps}
          </Menu.Item>
        )}
        <Menu.Item
          key="menu-documentation"
          icon={<BookOutlined />}
          onClick={(e) => {
            e.domEvent.preventDefault();
            window.open("/documentation", "_blank", "noopener,noreferrer");
          }}
        >
          {text.menuDocumentation}
        </Menu.Item>
      </Menu>
      <Modal
        title={text.menuDownloadApps}
        open={openDownloadAppsModal}
        footer={null}
        onOk={() => setOpenDownloadAppsModal(false)}
        onCancel={() => setOpenDownloadAppsModal(false)}
      >
        <div style={{ textAlign: "center" }}>
          <p>{text.downloadAppsQRText}</p>
          <div style={{ margin: "20px 0" }}>
            <img
              src="/images/download-app.png"
              alt={text.menuDownloadApps}
              width={200}
              height={200}
            />
          </div>
          <p>{text.downloadAppsLinkText}</p>
          <div>
            <a
              href={`${window.location.origin}/app`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {`${window.location.origin}/app`}
            </a>
          </div>
        </div>
      </Modal>
    </Sider>
  );
};

export default Sidebar;
