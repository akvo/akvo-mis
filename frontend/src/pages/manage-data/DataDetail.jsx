import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Table, Button, Space, Spin, Alert, Row, Col, Switch } from "antd";
import {
  LoadingOutlined,
  HistoryOutlined,
  LinkOutlined,
} from "@ant-design/icons";
import { EditableCell } from "../../components";
import {
  api,
  QUESTION_TYPES,
  store,
  uiText,
  transformDetailData,
} from "../../lib";
import { useNotification } from "../../util/hooks";
import { flatten, isEqual } from "lodash";
import { HistoryTable } from "../../components";
import { validateDependency } from "../../util";
import { AbilityContext } from "../../components/can";

const DataDetail = ({
  record,
  updater,
  updateRecord,
  setDeleteData,
  editedRecord,
  setEditedRecord,
  isPublic = false,
  isFullScreen = false,
  goToParentContext = null,
}) => {
  const [dataset, setDataset] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resetButton, setresetButton] = useState({});
  const [isAllQuestions, setIsAllQuestions] = useState(false);
  const pendingData = record?.pending_data?.created_by || false;
  const { notify } = useNotification();
  const {
    language,
    allForms: rawAllForms,
    forms: rawForms,
    user: authUser,
  } = store.useState((s) => s);
  const allForms = useMemo(
    () => rawAllForms || rawForms || [],
    [rawAllForms, rawForms]
  );
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);
  const ability = useContext(AbilityContext);

  const isEditor = ability.can("edit", "data") || authUser?.is_superuser;

  const questionGroups = useMemo(() => {
    const formList = allForms || [];
    const targetFormId = record?.form?.id || record?.form;
    const numericFormId =
      typeof targetFormId === "number"
        ? targetFormId
        : parseInt(targetFormId, 10);
    return formList?.find(
      (f) => f.id === targetFormId || f.id === numericFormId
    )?.content?.question_group;
  }, [record?.form, allForms]);

  const updateCell = (key, parentId, value) => {
    setresetButton({ ...resetButton, [key]: true });
    let prev = JSON.parse(JSON.stringify(dataset));
    let hasEdits = false;
    let questionFound = false;

    prev = prev.map((qg) => {
      if (qg.id === parentId) {
        const updatedQuestions = qg.question.map((qi) => {
          if (qi.id === key) {
            questionFound = true;
            if (isEqual(qi.value, value)) {
              if (qi.newValue) {
                delete qi.newValue;
              }
            } else {
              qi.newValue = value;
            }
            const edited = !isEqual(qi.value, value);
            if (edited && !hasEdits) {
              hasEdits = true;
            }
            return qi;
          }
          return qi;
        });
        return { ...qg, question: updatedQuestions };
      }
      return qg;
    });

    // If question not found in dataset, add it from filteredDataset
    if (!questionFound && isAllQuestions) {
      const sourceGroup = filteredDataset.find((qg) => qg.id === parentId);
      const sourceQuestion = sourceGroup?.question?.find((q) => q.id === key);

      if (sourceQuestion) {
        // Check if the question group exists in dataset
        const existingGroupIndex = prev.findIndex((qg) => qg.id === parentId);

        if (existingGroupIndex >= 0) {
          // Add question to existing group
          prev[existingGroupIndex].question.push({
            ...sourceQuestion,
            newValue: value,
          });
        } else {
          // Add new question group with the question
          prev.push({
            ...sourceGroup,
            question: [
              {
                ...sourceQuestion,
                newValue: value,
              },
            ],
          });
        }
        hasEdits = true;
      }
    }

    const hasNewValue = prev
      ?.flatMap((p) => p?.question)
      ?.some((q) => typeof q?.newValue !== "undefined");
    setEditedRecord({ ...editedRecord, [record.id]: hasNewValue });
    setDataset(prev);
  };

  const resetCell = (key, parentId) => {
    let prev = JSON.parse(JSON.stringify(dataset));
    prev = prev.map((qg) =>
      qg.id === parentId
        ? {
            ...qg,
            question: qg.question.map((qi) => {
              if (qi.id === key) {
                delete qi.newValue;
              }
              return qi;
            }),
          }
        : qg
    );
    /**
     * Check whether it still has newValue or not
     * in all groups of questions
     */
    const hasNewValue = prev
      ?.flatMap((p) => p?.question)
      ?.find((q) => q?.newValue);
    setEditedRecord({ ...editedRecord, [record.id]: hasNewValue });
    setDataset(prev);
  };

  const handleSave = () => {
    const data = [];
    const formId = flatten(dataset.map((qg) => qg.question))[0].form;

    // Create a set of repeatable group IDs for quick lookup
    const repeatableGroupIds = new Set(
      questionGroups?.filter((qg) => qg.repeatable).map((qg) => qg.id) || []
    );

    dataset.map((rd) => {
      rd.question.map((rq) => {
        if (rq.newValue || rq.newValue === 0) {
          let value = rq.newValue;
          if (rq.type === QUESTION_TYPES.number) {
            value =
              parseFloat(value) % 1 !== 0 ? parseFloat(value) : parseInt(value);
          }

          // Handle repeatable question IDs with suffix (e.g., "1749631662652-1")
          const questionId = rq.id;
          const isStringId = typeof questionId === "string";
          const hasSuffix = isStringId && questionId.includes("-");

          if (hasSuffix) {
            // Parse the ID to extract base question ID and index
            const lastDashIndex = questionId.lastIndexOf("-");
            const baseId = parseInt(questionId.substring(0, lastDashIndex), 10);
            const index = parseInt(questionId.substring(lastDashIndex + 1), 10);
            data.push({
              question: baseId,
              index: index,
              value: value,
            });
          } else if (repeatableGroupIds.has(rq.question_group)) {
            // Question is in a repeatable group but has no suffix (index 0)
            data.push({
              question: isStringId ? parseInt(questionId, 10) : questionId,
              index: 0,
              value: value,
            });
          } else {
            // Non-repeatable question
            data.push({
              question: questionId,
              value: value,
            });
          }
        }
      });
    });
    setSaving(true);
    api
      .put(`form-data/${formId}?data_id=${record.id}`, data)
      .then(() => {
        notify({
          type: "success",
          message: "Data updated successfully",
        });
        updater(
          updateRecord === record.id
            ? false
            : updateRecord === null
            ? false
            : record.id
        );
        fetchData(record.id);
        const resetObj = {};
        data.map((d) => {
          resetObj[d.question] = false;
        });
        setresetButton({ ...resetButton, ...resetObj });
        setEditedRecord({ ...editedRecord, [record.id]: false });
      })
      .catch((e) => {
        console.error(e);
        notify({
          type: "error",
          message: "Could not update data",
        });
      })
      .finally(() => {
        setSaving(false);
      });
  };

  const fetchData = useCallback(
    (id) => {
      setLoading(true);
      api
        .get(`data/${id}`)
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
    },
    [questionGroups]
  );

  useEffect(() => {
    if (record?.id && !dataset.length) {
      fetchData(record.id);
    }
  }, [record, dataset.length, fetchData]);

  const edited = useMemo(() => {
    return dataset.length
      ? flatten(dataset.map((qg) => qg.question)).findIndex(
          (fi) => fi.newValue
        ) > -1
      : false;
  }, [dataset]);

  const filteredDataset = useMemo(() => {
    if (!isAllQuestions) {
      // Show only questions with answers (current dataset from API)
      return dataset;
    }

    // Show all questions from form definition, merging with existing answers
    if (!questionGroups?.length) {
      return dataset;
    }

    // Create a map of existing answers for quick lookup
    // Key format: questionId or questionId-index for repeatable
    const answerMap = {};
    dataset.forEach((qg) => {
      qg.question.forEach((q) => {
        answerMap[q.id] = q;
      });
    });

    // Build complete dataset from questionGroups with merged answers
    const result = [];

    questionGroups.forEach((qg) => {
      if (qg.repeatable) {
        // For repeatable groups, find existing instances from dataset
        // Pattern: group label ends with " #N" where N is instance number
        const repeatInstances = dataset.filter(
          (d) =>
            d.id === qg.id ||
            (d.label && d.label.startsWith(qg.label || qg.name))
        );

        if (repeatInstances.length === 0) {
          // No instances exist, show one empty instance with all questions
          result.push({
            ...qg,
            label: `${qg.label || qg.name} #1`,
            question: qg.question
              .filter((q) => !q.hidden)
              .map((q) => ({
                ...q,
                question_group: qg.id,
                value: null,
                history: false,
              })),
          });
        } else {
          // Process each repeat instance
          repeatInstances.forEach((instance, idx) => {
            const instanceQuestions = qg.question
              .filter((q) => !q.hidden)
              .map((q) => {
                // Build the question ID as it appears in dataset
                const questionId = idx > 0 ? `${q.id}-${idx}` : q.id;
                const existingAnswer = answerMap[questionId];

                if (existingAnswer) {
                  return {
                    ...existingAnswer,
                    question_group: existingAnswer.question_group || qg.id,
                  };
                }
                // Return question without answer
                return {
                  ...q,
                  id: questionId,
                  question_group: qg.id,
                  value: null,
                  history: false,
                };
              });

            result.push({
              ...instance,
              question: instanceQuestions,
            });
          });
        }
      } else {
        // Non-repeatable group: show all questions with merged answers
        const groupQuestions = qg.question
          .filter((q) => !q.hidden)
          .map((q) => {
            const existingAnswer = answerMap[q.id];
            if (existingAnswer) {
              return {
                ...existingAnswer,
                question_group: existingAnswer.question_group || qg.id,
              };
            }
            // Return question without answer
            return {
              ...q,
              question_group: qg.id,
              value: null,
              history: false,
            };
          });

        result.push({
          ...qg,
          label: qg.label || qg.name,
          question: groupQuestions,
        });
      }
    });

    return result;
  }, [dataset, questionGroups, isAllQuestions]);

  return loading ? (
    <Space style={{ paddingTop: 18, color: "#9e9e9e" }} size="middle">
      <Spin indicator={<LoadingOutlined style={{ color: "#1b91ff" }} spin />} />
      <span>{text.loadingText}</span>
    </Space>
  ) : (
    <>
      <div className={`data-detail ${isFullScreen ? "full-screen" : ""}`}>
        {pendingData && (
          <Alert
            message={`Can't edit/update this data, because data in pending data by ${pendingData}`}
            type="warning"
          />
        )}
        {filteredDataset
          .filter((r) => r?.question?.length)
          .map((r, rI) => (
            <div className="pending-data-wrapper" key={rI}>
              <h3>{r.label}</h3>
              <Table
                pagination={false}
                dataSource={r.question}
                rowClassName={(record) => {
                  const rowEdited =
                    (record.newValue || record.newValue === 0) &&
                    !isEqual(record.newValue, record.value)
                      ? "row-edited"
                      : "row-normal";
                  return `expandable-row ${rowEdited}`;
                }}
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
                    render: (row) => (
                      <EditableCell
                        record={row}
                        parentId={row.question_group}
                        updateCell={updateCell}
                        resetCell={resetCell}
                        pendingData={pendingData}
                        isPublic={isPublic}
                        resetButton={resetButton}
                        readonly={!isEditor}
                      />
                    ),
                    width: "50%",
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
      <div className="button-save">
        <Row type="flex" justify="space-between" align="middle" gutter={16}>
          <Col>
            <Space>
              {goToParentContext && (
                <Button
                  type="link"
                  icon={<LinkOutlined />}
                  onClick={goToParentContext}
                >
                  {text.viewFullContext}
                </Button>
              )}
              <Switch
                checked={isAllQuestions}
                onChange={(checked) => setIsAllQuestions(checked)}
              />
              <span>{text.showAllQuestionsSwitch}</span>
            </Space>
          </Col>
          <Col>
            {!isPublic && isEditor && (
              <Space>
                <Button
                  type="primary"
                  onClick={handleSave}
                  disabled={!edited || saving}
                  loading={saving}
                  shape="round"
                >
                  {text.saveEditButton}
                </Button>
                {ability.can("delete", "data") && (
                  <Button
                    type="danger"
                    onClick={() => setDeleteData(record)}
                    shape="round"
                  >
                    {text.deleteText}
                  </Button>
                )}
              </Space>
            )}
          </Col>
        </Row>
      </div>
    </>
  );
};

export default React.memo(DataDetail);
