import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Table, Button, Space, Spin, Dropdown } from "antd";
import {
  LoadingOutlined,
  HistoryOutlined,
  FormOutlined,
} from "@ant-design/icons";
import {
  api,
  QUESTION_TYPES,
  store,
  uiText,
  transformDetailData,
} from "../../lib";
import { useNavigate } from "react-router-dom";
import { HistoryTable, ReadOnlyCell } from "../../components";
import { validateDependency } from "../../util";

const DraftDetail = ({
  record = {},
  childrenForms = [],
  onDelete = () => {},
  hideCreateDraftMonitoring = true,
}) => {
  const [dataset, setDataset] = useState([]);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const { language, forms: allForms, selectedForm } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const questionGroups = useMemo(() => {
    const formList = allForms || [];
    return formList?.find((f) => f.id === record?.form)?.content
      ?.question_group;
  }, [record?.form, allForms]);

  const navigate = useNavigate();

  const goToEdit = (record) => {
    navigate(`/control-center/data/draft/${record?.form}?id=${record.id}`, {
      state: { record },
    });
  };

  const goToEditAndPublish = (record) => {
    navigate(
      `/control-center/data/draft/${record?.form}?id=${record.id}&publish=true`,
      {
        state: { record },
      }
    );
  };

  const addDraftMonitoring = (uuid, formId) => {
    navigate(`/control-center/data/draft/${formId}?uuid=${uuid}`, {
      state: { formId },
    });
  };

  const fetchData = useCallback(() => {
    if (!record?.id || dataset.length > 0) {
      return;
    }

    setLoading(true);
    api
      .get(`data/${record.id}`)
      .then((res) => {
        const transformedData = transformDetailData(
          res.data,
          questionGroups,
          validateDependency,
          QUESTION_TYPES
        );
        setDataset(transformedData);
      })
      .catch((e) => {
        console.error(e);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [record?.id, dataset.length, questionGroups]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return loading ? (
    <Space style={{ paddingTop: 18, color: "#9e9e9e" }} size="middle">
      <Spin indicator={<LoadingOutlined style={{ color: "#1b91ff" }} spin />} />
      <span>{text.loadingText}</span>
    </Space>
  ) : (
    <div className="data-detail">
      <div>
        {dataset
          .filter((r) => r?.question?.length)
          .map((r, rI) => (
            <div className="pending-data-wrapper" key={rI}>
              <h3>{r.label}</h3>
              <Table
                pagination={false}
                dataSource={r.question}
                rowClassName="expandable-row row-normal"
                rowKey="id"
                columns={[
                  {
                    title: text?.questionCol,
                    dataIndex: null,
                    width: "50%",
                    render: (_, row) =>
                      row.short_label ? row.short_label : row.label,
                    className: "table-col-question",
                  },
                  {
                    title: "Response",
                    width: "50%",
                    render: (row) => <ReadOnlyCell record={row} />,
                  },
                  Table.EXPAND_COLUMN,
                ]}
                expandable={{
                  expandIcon: ({ onExpand, record }) => {
                    if (!record?.history) {
                      return "";
                    }
                    return (
                      <HistoryOutlined
                        className="expand-icon"
                        onClick={(e) => onExpand(record, e)}
                      />
                    );
                  },
                  expandedRowRender: (record) => (
                    <HistoryTable record={record} />
                  ),
                  rowExpandable: (record) => record?.history,
                }}
              />
            </div>
          ))}
      </div>

      <div className="data-detail-actions">
        <Space>
          <Button
            type="danger"
            shape="round"
            onClick={() => onDelete(record, setDeleting)}
            loading={deleting}
          >
            {text.deleteText}
          </Button>
          <Button
            type="primary"
            shape="round"
            onClick={() => goToEdit(record)}
            disabled={deleting}
            ghost
          >
            {text.editButton}
          </Button>
          <Button
            type="primary"
            shape="round"
            onClick={() => goToEditAndPublish(record)}
            disabled={deleting}
          >
            {text.editAndPublishDraft}
          </Button>
          {record?.form === selectedForm &&
            childrenForms?.length > 0 &&
            !hideCreateDraftMonitoring && (
              <Dropdown
                trigger={["click"]}
                menu={{
                  items: childrenForms.map((form) => ({
                    key: form.id,
                    label: form.name,
                  })),
                  onClick: (e) => addDraftMonitoring(record?.uuid, e.key),
                }}
              >
                <Button shape="round" icon={<FormOutlined />}>
                  {text.createDraftMonitoring}
                </Button>
              </Dropdown>
            )}
        </Space>
      </div>
    </div>
  );
};

export default DraftDetail;
