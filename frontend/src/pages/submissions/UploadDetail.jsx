import React, { useState, useEffect, useMemo, useCallback } from "react";
import { Table, Tabs, Button, Space, List, Spin, Row, Col, Modal } from "antd";
import {
  LeftCircleOutlined,
  DownCircleOutlined,
  LoadingOutlined,
  PaperClipOutlined,
} from "@ant-design/icons";
import {
  api,
  columnsRawData,
  QUESTION_TYPES,
  store,
  uiText,
  transformRawData,
} from "../../lib";
import { ApproverDetailTable, RawDataTable } from "../../components";
import { isEqual, flatten } from "lodash";
import { useNotification } from "../../util/hooks";
import { getTimeDifferenceText } from "../../util/date";
import { getForms } from "../../util/form";
import UploadAttachmentModal from "./UploadAttachmentModal";
const { TabPane } = Tabs;

const getSummaryColumns = (data) => {
  const uniqueForms = new Set(data.map((d) => d.form));
  const hasMultipleForms = uniqueForms.size > 1;

  const formColumn = [];
  if (hasMultipleForms) {
    // Precompute rowSpan map: { [key]: rowSpan } for first row of each form
    const spanMap = {};
    const formCount = {};
    const formFirstKey = {};
    data.forEach((d) => {
      formCount[d.form] = (formCount[d.form] || 0) + 1;
      if (!formFirstKey[d.form]) {
        formFirstKey[d.form] = d.key;
      }
    });
    Object.keys(formFirstKey).forEach((form) => {
      spanMap[formFirstKey[form]] = formCount[form];
    });
    formColumn.push({
      title: "Form",
      dataIndex: "form_name",
      key: "form_name",
      width: "20%",
      onCell: (record) => {
        const rowSpan = spanMap[record.key];
        if (rowSpan) {
          return { rowSpan, style: { verticalAlign: "top" } };
        }
        return { rowSpan: 0 };
      },
    });
  }

  return [
    ...formColumn,
    {
      title: "Question",
      dataIndex: "question",
      key: "question",
      width: hasMultipleForms ? "30%" : "50%",
    },
    {
      title: "Value",
      dataIndex: "value",
      className: "blue",
      render: (value, row) => {
        if (row.type === "Option" || row.type === "Multiple_Option") {
          const filtered = value
            .filter((x) => x.total)
            .map((val) => `${val.type} - (${val.total})`);
          return (
            <ul className="option-list">
              {filtered.map((d, di) => (
                <li key={di}>{d}</li>
              ))}
            </ul>
          );
        }
        return value;
      },
    },
  ];
};

const UploadDetail = ({ record: batch, setReload }) => {
  const [values, setValues] = useState([]);
  const [rawValues, setRawValues] = useState([]);
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dataLoading, setDataLoading] = useState(null);
  const [saving, setSaving] = useState(null);
  const [selectedTab, setSelectedTab] = useState("data-summary");
  const [expandedRowKeys, setExpandedRowKeys] = useState([]);
  const [comments, setComments] = useState([]);
  const [questionGroups, setQuestionGroups] = useState([]);
  const [resetButton, setresetButton] = useState({});
  const [attachments, setAttachments] = useState([]);
  const [attachmentModalOpen, setAttachmentModalOpen] = useState(false);
  const [editAttachment, setEditAttachment] = useState(null);

  const { notify } = useNotification();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const handleSave = (data) => {
    setSaving(data.id);
    const formData = [];
    data.data.map((rd) => {
      rd.question.map((rq) => {
        if (
          (rq.newValue || rq.newValue === 0) &&
          !isEqual(rq.value, rq.newValue)
        ) {
          let value = rq.newValue;
          if (rq.type === QUESTION_TYPES.number) {
            value =
              parseFloat(value) % 1 !== 0 ? parseFloat(value) : parseInt(value);
          }
          formData.push({
            question: rq.id,
            value: value,
          });
        }
      });
    });
    api
      .put(
        `form-pending-data/${batch.form?.id}?pending_data_id=${data.id}`,
        formData
      )
      .then(() => {
        fetchData(data.id, questionGroups);
        setReload(data.id);
        notify({
          type: "success",
          message: "Data updated",
        });
        const resetObj = {};
        formData.map((d) => {
          resetObj[d.question] = false;
        });
        setresetButton({ ...resetButton, ...resetObj });
      })
      .catch((e) => {
        console.error(e);
      })
      .finally(() => {
        setSaving(null);
      });
  };

  const fetchAttachments = useCallback(async () => {
    try {
      const response = await api.get(`/batch/attachments/${batch.id}`);
      setAttachments(response.data);
    } catch (error) {
      console.error("Error fetching attachments:", error);
    }
  }, [batch.id]);

  useEffect(() => {
    fetchAttachments();
  }, [fetchAttachments]);

  const fetchComments = useCallback(async () => {
    try {
      const response = await api.get(`/batch/comment/${batch.id}`);
      setComments(response.data);
    } catch (error) {
      console.error("Error fetching comments:", error);
    }
  }, [batch.id]);

  useEffect(() => {
    fetchComments();
  }, [fetchComments]);

  const handleTabSelect = (e) => {
    if (loading) {
      return;
    }
    if (e === "data-summary") {
      setColumns(getSummaryColumns(values));
    } else {
      setExpandedRowKeys([]);
      setColumns([...columnsRawData, Table.EXPAND_COLUMN]);
    }
    setSelectedTab(e);
  };

  useEffect(() => {
    setLoading(true);
    if (selectedTab === "data-summary") {
      api
        .get(`/batch/summary/${batch.id}`)
        .then((res) => {
          const sorted = [...res.data].sort((a, b) => a.form - b.form);
          const data = sorted.map((r, i) => {
            return { key: `Q-${i}`, ...r };
          });
          setColumns(getSummaryColumns(data));
          setValues(data);
          setLoading(false);
        })
        .catch((err) => {
          console.error(err);
          setLoading(false);
        });
    }
    if (selectedTab === "raw-data") {
      api
        .get(`/form-pending-data-batch/${batch.id}`)
        .then((res) => {
          setColumns([...columnsRawData, Table.EXPAND_COLUMN]);
          setRawValues(
            res.data.map((x) => ({
              key: x.id,
              data: [],
              loading: false,
              ...x,
            }))
          );
          setLoading(false);
        })
        .catch((e) => {
          console.error(e);
          setLoading(false);
        });
    }
  }, [selectedTab, batch]);

  const onDeleteAttachment = (attachmentId) => {
    Modal.confirm({
      title: text.deleteAttachmentTitle,
      content: text.deleteAttachmentDesc,
      okText: text.deleteText,
      okType: "danger",
      cancelText: text.cancelButton,
      onOk: () => {
        api
          .delete(`/batch/attachment/${attachmentId}`)
          .then(() => {
            notify({
              type: "success",
              message: text.deleteAttachmentSuccess,
            });
            setAttachments((prevAttachments) =>
              prevAttachments.filter((att) => att.id !== attachmentId)
            );
            fetchComments();
          })
          .catch((error) => {
            console.error("Error deleting attachment:", error);
            notify({
              type: "error",
              message: text.deleteAttachmentError,
            });
          });
      },
    });
  };

  const updateCell = (key, parentId, value) => {
    setresetButton({ ...resetButton, [key]: true });
    let prev = JSON.parse(JSON.stringify(rawValues));
    prev = prev.map((rI) => {
      let hasEdits = false;
      const data = rI.data.map((rd) => ({
        ...rd,
        question: rd.question.map((rq) => {
          if (rq.id === key && rI.id === parentId) {
            if (
              isEqual(rq.value, value) &&
              (rq.newValue || rq.newValue === 0)
            ) {
              delete rq.newValue;
            } else {
              rq.newValue = value;
            }
            const edited = !isEqual(rq.value, value);
            if (edited && !hasEdits) {
              hasEdits = true;
            }
            return rq;
          }
          if (
            (rq.newValue || rq.newValue === 0) &&
            !isEqual(rq.value, rq.newValue) &&
            !hasEdits
          ) {
            hasEdits = true;
          }
          return rq;
        }),
      }));
      return {
        ...rI,
        data,
        edited: hasEdits,
      };
    });
    setRawValues(prev);
  };

  const resetCell = (key, parentId) => {
    let prev = JSON.parse(JSON.stringify(rawValues));
    prev = prev.map((rI) => {
      let hasEdits = false;
      const data = rI.data.map((rd) => ({
        ...rd,
        question: rd.question.map((rq) => {
          if (rq.id === key && rI.id === parentId) {
            delete rq.newValue;
            return rq;
          }
          if (
            (rq.newValue || rq.newValue === 0) &&
            !isEqual(rq.value, rq.newValue) &&
            !hasEdits
          ) {
            hasEdits = true;
          }
          return rq;
        }),
      }));
      return {
        ...rI,
        data,
        edited: hasEdits,
      };
    });
    setRawValues(prev);
  };

  const initData = (record) => {
    setRawValues((rv) =>
      rv.map((rI) => (rI.id === record?.id ? { ...rI, loading: true } : rI))
    );
    const qg = getForms().find((f) => f.id === record?.form).content
      .question_group;
    setQuestionGroups(qg);
    fetchData(record?.id, qg);
  };

  const fetchData = (recordId, questionGroups) => {
    setDataLoading(recordId);
    api
      .get(`data/${recordId}`)
      .then((res) => {
        const data = transformRawData(questionGroups, res.data);
        setRawValues((rv) =>
          rv.map((rI) =>
            rI.id === recordId ? { ...rI, data, loading: false } : rI
          )
        );
      })
      .catch((e) => {
        console.error(e);
        setRawValues((rv) =>
          rv.map((rI) => (rI.id === recordId ? { ...rI, loading: false } : rI))
        );
      })
      .finally(() => {
        setDataLoading(null);
      });
  };

  const isEdited = (id) => {
    return (
      !!flatten(
        rawValues.find((d) => d.id === id)?.data?.map((g) => g.question)
      )?.filter(
        (d) => (d.newValue || d.newValue === 0) && !isEqual(d.value, d.newValue)
      )?.length || false
    );
  };

  const isEditable =
    (batch.approvers || []).filter((a) => a.status_text === "Rejected").length >
    0;

  return (
    <div id="upload-detail">
      <ApproverDetailTable data={batch?.approvers} />
      <Tabs centered activeKey={selectedTab} onTabClick={handleTabSelect}>
        <TabPane tab={text.uploadTab1} key="data-summary" />
        <TabPane tab={text.uploadTab2} key="raw-data" />
      </Tabs>
      <Table
        loading={loading}
        dataSource={selectedTab === "raw-data" ? rawValues : values}
        pagination={selectedTab === "raw-data" ? { pageSize: 10 } : false}
        columns={columns}
        style={{ borderBottom: "solid 1px #ddd" }}
        rowKey="id"
        expandable={
          selectedTab === "raw-data"
            ? {
                expandedRowKeys,
                expandedRowRender: (expanded) => {
                  return (
                    <>
                      {expanded.loading ? (
                        <Space
                          style={{ paddingTop: 18, color: "#9e9e9e" }}
                          size="middle"
                        >
                          <Spin
                            indicator={
                              <LoadingOutlined
                                style={{ color: "#1b91ff" }}
                                spin
                              />
                            }
                          />
                          <span>{text.loadingText}</span>
                        </Space>
                      ) : (
                        <div className={`pending-data-outer`}>
                          {expanded.data
                            ?.filter((r) => r?.question?.length)
                            ?.map((r, rI) => (
                              <div className="pending-data-wrapper" key={rI}>
                                <h3>{r.label}</h3>
                                <RawDataTable
                                  updateCell={updateCell}
                                  resetCell={resetCell}
                                  dataLoading={dataLoading}
                                  isEditable={isEditable}
                                  resetButton={resetButton}
                                  expanded={expanded}
                                  questions={r.question}
                                />
                              </div>
                            ))}
                        </div>
                      )}
                      {isEditable && !expanded.loading && (
                        <div className="pending-data-action-reject">
                          <Button
                            onClick={() => handleSave(expanded)}
                            type="primary"
                            loading={expanded.id === saving}
                            disabled={
                              expanded.id === dataLoading ||
                              isEdited(expanded.id) === false
                            }
                            shape="round"
                          >
                            Save Edits
                          </Button>
                        </div>
                      )}
                    </>
                  );
                },
                expandIcon: ({ expanded, onExpand, record }) =>
                  expanded ? (
                    <DownCircleOutlined
                      onClick={(e) => {
                        setExpandedRowKeys([]);
                        onExpand(record, e);
                      }}
                      style={{ color: "#1651B6", fontSize: "19px" }}
                    />
                  ) : (
                    <LeftCircleOutlined
                      onClick={(e) => {
                        setExpandedRowKeys([record.id]);
                        if (!record.data?.length) {
                          initData(record);
                        }
                        onExpand(record, e);
                      }}
                      style={{ color: "#1651B6", fontSize: "19px" }}
                    />
                  ),
              }
            : false
        }
        onRow={(record) => ({
          onClick: () => {
            if (expandedRowKeys.includes(record.id)) {
              setExpandedRowKeys((prevExpandedKeys) =>
                prevExpandedKeys.filter((key) => key !== record.id)
              );
            } else {
              if (!record.data?.length) {
                initData(record);
              }
              setExpandedRowKeys((prevExpandedKeys) => [
                ...prevExpandedKeys,
                record.id,
              ]);
            }
          },
        })}
        rowClassName={(record) => {
          const rowEdited =
            (record.newValue || record.newValue === 0) &&
            !isEqual(record.value, record.newValue)
              ? "row-edited"
              : "row-normal sticky";
          return `expandable-row ${rowEdited}`;
        }}
        expandRowByClick
      />
      {attachments.length > 0 && (
        <div className="attachments">
          <div className="detail-list-header">
            <Row align="middle" justify="space-between">
              <Col span={8}>
                <h3>{text.batchAttachments}</h3>
              </Col>
              <Col span={4} style={{ textAlign: "right" }}>
                <Button
                  type="link"
                  icon={<PaperClipOutlined />}
                  onClick={() => {
                    setAttachmentModalOpen(true);
                  }}
                  size="small"
                >
                  {text.addAttachment}
                </Button>
              </Col>
            </Row>
          </div>
          <div className="detail-list">
            <List
              itemLayout="horizontal"
              dataSource={attachments}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button
                      type="link"
                      key={`${item.id}-delete`}
                      onClick={() => onDeleteAttachment(item.id)}
                      danger
                    >
                      {text.deleteText}
                    </Button>,
                    <Button
                      type="link"
                      key={`${item.id}-edit`}
                      disabled={!item.id}
                      onClick={() => {
                        setEditAttachment(item);
                        setAttachmentModalOpen(true);
                      }}
                    >
                      {text.editText}
                    </Button>,
                    <a
                      href={item.file_path}
                      target="_blank"
                      rel="noopener noreferrer"
                      download={item.file_path}
                      key={`${item.id}-view`}
                    >
                      {text.viewText}
                    </a>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <div style={{ fontSize: "12px" }}>
                        <span style={{ color: "#ACAAAA", marginLeft: "6px" }}>
                          {getTimeDifferenceText(
                            item.created,
                            "YYYY-MM-DD hh:mm a"
                          )}
                        </span>
                      </div>
                    }
                    description={item.name}
                  />
                </List.Item>
              )}
            />
          </div>
        </div>
      )}
      <UploadAttachmentModal
        isOpen={attachmentModalOpen}
        onCancel={() => {
          if (editAttachment) {
            setEditAttachment(null);
          }
          setAttachmentModalOpen(false);
        }}
        onSuccess={() => {
          if (editAttachment) {
            setEditAttachment(null);
          }
          setAttachmentModalOpen(false);
          fetchAttachments();
          fetchComments();
        }}
        editData={editAttachment}
        batch={batch}
      />
      <div className="detail-list-header">
        <h3>{text.notesFeedback}</h3>
      </div>
      {!!comments.length && (
        <div className="detail-list">
          <List
            itemLayout="horizontal"
            dataSource={comments}
            renderItem={(item) => (
              <List.Item
                actions={
                  item.file_path
                    ? [
                        <a
                          href={item.file_path}
                          target="_blank"
                          rel="noopener noreferrer"
                          download={item.file_path}
                          key={`${item.id}-view`}
                        >
                          <Button
                            type="link"
                            icon={<PaperClipOutlined />}
                            style={{ padding: 0 }}
                          >
                            {text.viewAttachment}
                          </Button>
                        </a>,
                      ]
                    : []
                }
              >
                <List.Item.Meta
                  title={
                    <div style={{ fontSize: "12px" }}>
                      {item.user.name}
                      <span style={{ color: "#ACAAAA", marginLeft: "6px" }}>
                        {getTimeDifferenceText(
                          item.created,
                          "YYYY-MM-DD hh:mm a"
                        )}
                      </span>
                    </div>
                  }
                  description={item.comment}
                />
              </List.Item>
            )}
          />
        </div>
      )}
    </div>
  );
};

export default React.memo(UploadDetail);
