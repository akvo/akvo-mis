import React, { useState, useMemo, useCallback } from "react";
import "./style.scss";
import {
  Row,
  Col,
  Space,
  Button,
  Dropdown,
  Checkbox,
  Badge,
  Tooltip,
  Radio,
  Input,
  DatePicker,
} from "antd";
import { useLocation, useNavigate } from "react-router-dom";
import AdministrationDropdown from "./AdministrationDropdown";
import FormDropdown from "./FormDropdown.js";
import { useNotification } from "../../util/hooks";
import { api, store, uiText } from "../../lib";
import { takeRight } from "lodash";
import RemoveFiltersButton from "./RemoveFiltersButton";
import AdvancedFilters from "./AdvancedFilters";
import {
  PlusOutlined,
  DownloadOutlined,
  // UploadOutlined,
  FileWordOutlined,
  DownOutlined,
  SearchOutlined,
  CalendarOutlined,
  FileZipOutlined,
} from "@ant-design/icons";
import { Can } from "../can/index.js";

const DataFilters = ({
  loading,
  showAdm = true,
  resetFilter = true,
  showSearch = true,
  showDateRange = true,
  selectedRowKeys = [],
  search = "",
  onSearchChange = () => {},
}) => {
  const authUser = store.useState((s) => s.user);
  const selectedForm = store.useState((s) => s.selectedForm);
  const loadingForm = store.useState((s) => s.loadingForm);
  const administration = store.useState((s) => s.administration);
  const showAdvancedFilters = store.useState((s) => s.showAdvancedFilters);
  const dateRange = store.useState((s) => s.dateRange);
  const activeLang = store.useState((s) => s.language?.active);
  const allForms = store.useState((s) => s.allForms);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { notify } = useNotification();
  const [exporting, setExporting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [excelChildForms, setExcelChildForms] = useState([]);
  const [docxChildForms, setDocxChildForms] = useState([]);
  const [openDocx, setOpenDocx] = useState(false);
  const [openExcel, setOpenExcel] = useState(false);
  const [downloadType, setDownloadType] = useState("recent");
  const isUserHasForms = authUser?.is_superuser || authUser?.forms?.length || 0;

  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const childForms = useMemo(() => {
    return allForms?.filter((f) => f?.content?.parent === selectedForm);
  }, [selectedForm, allForms]);

  const selectedAdm = takeRight(administration, 1)[0];

  const export2Excel = useCallback(async () => {
    setExporting(true);
    try {
      const adm_id = selectedAdm?.id;
      const childFormIds = excelChildForms
        .map((id) => `child_form_ids=${id}`)
        .join("&");
      const urls = [`download/generate?form_id=${selectedForm}`];
      if (adm_id && selectedAdm?.parent) {
        urls.push(`administration_id=${adm_id}`);
      }
      if (excelChildForms.length) {
        urls.push(childFormIds);
      }
      if (selectedRowKeys.length) {
        const selectionIds = selectedRowKeys
          .map((id) => `selection_ids=${id}`)
          .join("&");
        urls.push(selectionIds);
      }
      if (!selectedRowKeys.length && ["all", "recent"].includes(downloadType)) {
        urls.push(`type=${downloadType}`);
      }
      if (dateRange && dateRange.length === 2 && dateRange[0] && dateRange[1]) {
        urls.push(`date_from=${dateRange[0].format("YYYY-MM-DD")}`);
        urls.push(`date_to=${dateRange[1].format("YYYY-MM-DD")}`);
      }
      const apiURL = `/${urls.join("&")}`;
      await api.get(apiURL);
      notify({
        type: "success",
        message: text.export2ExcelSuccess,
      });
      setExporting(false);
      setOpenExcel(false); // Close dropdown after successful export
      navigate("/downloads");
    } catch (error) {
      setExporting(false);
      notify({
        type: "error",
        message: text.export2ExcelError,
      });
    }
  }, [
    selectedAdm,
    selectedForm,
    excelChildForms,
    notify,
    downloadType,
    dateRange,
    selectedRowKeys,
    text.export2ExcelSuccess,
    text.export2ExcelError,
    navigate,
  ]);

  const export2Docx = useCallback(async () => {
    setDownloading(true);
    try {
      const selectionIds = selectedRowKeys
        .map((id) => `selection_ids=${id}`)
        .join("&");
      const childFormIds = docxChildForms
        .map((id) => `child_form_ids=${id}`)
        .join("&");
      let apiURL = `/download/datapoint-report?form_id=${selectedForm}&${selectionIds}`;
      if (docxChildForms.length) {
        apiURL += `&${childFormIds}`;
      }
      await api.get(apiURL);
      setDownloading(false);
      setOpenDocx(false); // Close dropdown after successful download
      notify({
        type: "success",
        message: text.downloadReportSuccess,
      });
      navigate("/downloads");
    } catch (error) {
      setDownloading(false);
      setOpenDocx(false); // Close dropdown even on error
      notify({
        type: "error",
        message: text.downloadReportError,
      });
    }
  }, [
    selectedRowKeys,
    docxChildForms,
    notify,
    selectedForm,
    text.downloadReportError,
    text.downloadReportSuccess,
    navigate,
  ]);

  const goToAddForm = () => {
    /***
     * reset initial value
     */
    store.update((s) => {
      s.initialValue = [];
    });
    navigate(`/control-center/form/${selectedForm}`);
  };

  const handleDateRangeChange = useCallback((dates) => {
    store.update((s) => {
      s.dateRange = dates;
    });
  }, []);

  const buildCheckboxItems = useCallback(
    (selected, setSelected) =>
      childForms.map((form) => ({
        key: form.id,
        label: (
          <Checkbox
            checked={selected.includes(form.id)}
            onChange={(e) => {
              if (e.target.checked) {
                setSelected([...selected, form.id]);
              } else {
                setSelected(selected.filter((id) => id !== form.id));
              }
            }}
          >
            {form.content.name}
          </Checkbox>
        ),
      })),
    [childForms]
  );

  const excelMenuItems = useMemo(() => {
    const menuItems = [];

    if (childForms.length > 0) {
      menuItems.push(
        {
          key: "header",
          label: (
            <div
              style={{ fontWeight: 500, color: "#262626", padding: "4px 0" }}
            >
              {text.selectChildForms}
            </div>
          ),
          disabled: true,
        },
        ...buildCheckboxItems(excelChildForms, setExcelChildForms),
        {
          key: "divider",
          type: "divider",
        }
      );
    }

    if (!selectedRowKeys.length) {
      menuItems.push({
        key: "download-type",
        label: (
          <Radio.Group
            onChange={(e) => setDownloadType(e.target.value)}
            value={downloadType}
          >
            <Radio value="all">{text.allData}</Radio>
            <Radio value="recent">{text.latestData}</Radio>
          </Radio.Group>
        ),
      });
    }

    return [
      ...menuItems,
      {
        key: "download-footer",
        label: (
          <Button
            type="primary"
            icon={<FileZipOutlined />}
            loading={exporting}
            onClick={export2Excel}
            style={{ width: "100%" }}
          >
            {text.downloadData}
          </Button>
        ),
        disabled: true,
      },
    ];
  }, [
    childForms,
    buildCheckboxItems,
    excelChildForms,
    selectedRowKeys,
    downloadType,
    exporting,
    text.selectChildForms,
    text.allData,
    text.latestData,
    text.downloadData,
    export2Excel,
  ]);

  const docxMenuItems = useMemo(() => {
    const menuItems = [];

    if (childForms.length > 0) {
      menuItems.push(
        {
          key: "header",
          label: (
            <div
              style={{ fontWeight: 500, color: "#262626", padding: "4px 0" }}
            >
              {text.selectChildForms}
            </div>
          ),
          disabled: true,
        },
        ...buildCheckboxItems(docxChildForms, setDocxChildForms),
        {
          key: "divider",
          type: "divider",
        }
      );
    }

    return [
      ...menuItems,
      {
        key: "download-footer",
        label: (
          <Button
            type="primary"
            icon={<FileWordOutlined />}
            loading={downloading}
            onClick={export2Docx}
            disabled={!selectedRowKeys?.length}
            style={{ width: "100%" }}
          >
            {text.downloadReport}
          </Button>
        ),
        disabled: true,
      },
    ];
  }, [
    childForms,
    buildCheckboxItems,
    docxChildForms,
    downloading,
    selectedRowKeys,
    text.selectChildForms,
    text.downloadReport,
    export2Docx,
  ]);

  return (
    <>
      <Row style={{ marginBottom: "16px" }}>
        <Col flex={1}>
          <Space>
            <FormDropdown
              loading={loading}
              width="100%"
              style={{ minWidth: 300 }}
            />
            {/* <AdvancedFiltersButton /> */}
          </Space>
        </Col>
        <Col>
          <Space>
            {/* <Can I="upload" a="data">
              <Link to="/control-center/data/upload">
                <Button shape="round" icon={<UploadOutlined />}>
                  {text.bulkUpload}
                </Button>
              </Link>
            </Can> */}
            {pathname === "/control-center/data" && (
              <Space>
                {selectedRowKeys.length === 0 ? (
                  <Tooltip
                    title={text.selectRowsToDownload}
                    trigger="hover"
                    placement="top"
                  >
                    <Button shape="round" icon={<FileWordOutlined />} disabled>
                      {text.downloadReport}
                    </Button>
                  </Tooltip>
                ) : (
                  <Dropdown
                    trigger={["click"]}
                    placement="bottomLeft"
                    open={openDocx}
                    onOpenChange={setOpenDocx}
                    menu={{
                      items: docxMenuItems,
                      style: { minWidth: "200px" },
                    }}
                    disabled={!selectedRowKeys.length}
                  >
                    <Badge count={selectedRowKeys.length}>
                      <Button
                        shape="round"
                        icon={<FileWordOutlined />}
                        loading={downloading}
                        disabled={!selectedRowKeys.length}
                      >
                        {text.downloadReport} <DownOutlined />
                      </Button>
                    </Badge>
                  </Dropdown>
                )}
              </Space>
            )}
            {pathname === "/control-center/data" && (
              <Can I="create" a="downloads">
                <Dropdown
                  trigger={["click"]}
                  open={openExcel}
                  onOpenChange={setOpenExcel}
                  menu={{
                    items: excelMenuItems,
                    style: { minWidth: "200px" },
                  }}
                  placement="bottomRight"
                >
                  <Badge count={selectedRowKeys.length}>
                    <Button
                      icon={<DownloadOutlined />}
                      shape="round"
                      loading={exporting}
                    >
                      {text.download}
                    </Button>
                  </Badge>
                </Dropdown>
              </Can>
            )}
            <Can I="manage" a="submissions">
              <Button
                shape="round"
                icon={<PlusOutlined />}
                type="primary"
                disabled={!isUserHasForms}
                onClick={goToAddForm}
              >
                {text.addNewButton}
              </Button>
            </Can>
          </Space>
        </Col>
      </Row>
      {(showSearch || showDateRange || showAdm || resetFilter) && (
        <Row>
          <Col>
            <Space>
              {showSearch && (
                <Input
                  prefix={<SearchOutlined />}
                  placeholder={text.searchPlaceholder}
                  value={search}
                  onChange={(e) => onSearchChange(e.target.value)}
                  allowClear
                  style={{ width: 200 }}
                />
              )}
              {showDateRange && (
                <DatePicker.RangePicker
                  value={dateRange}
                  onChange={handleDateRangeChange}
                  allowClear
                  placeholder={[
                    text.dateFromPlaceholder,
                    text.dateToPlaceholder,
                  ]}
                  suffixIcon={<CalendarOutlined />}
                />
              )}
              {showAdm && (
                <AdministrationDropdown loading={loading || loadingForm} />
              )}
              {resetFilter && <RemoveFiltersButton />}
            </Space>
          </Col>
        </Row>
      )}
      {showAdvancedFilters && <AdvancedFilters />}
    </>
  );
};

export default React.memo(DataFilters);
