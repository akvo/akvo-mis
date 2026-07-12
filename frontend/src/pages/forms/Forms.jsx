import React, {
  useEffect,
  useState,
  useMemo,
  useRef,
  useCallback,
} from "react";
import { Webform } from "akvo-react-form";
import "akvo-react-form/dist/index.css";
import "./style.scss";
import { useParams, useNavigate } from "react-router-dom";
import { Row, Col, Space, Progress, Result, Button, Modal } from "antd";
import {
  api,
  QUESTION_TYPES,
  store,
  uiText,
  getCascadeAnswerAPI,
  processFileUploads,
  processEntityCascades,
  processRepeatableQuestions,
  transformValue,
} from "../../lib";
import { pick, isEmpty } from "lodash";
import { PageLoader, Breadcrumbs, DescriptionPanel } from "../../components";
import { useNotification } from "../../util/hooks";
import moment from "moment";

const Forms = () => {
  const navigate = useNavigate();
  const { user: authUser } = store.useState((s) => s);
  const { formId, uuid } = useParams();
  const [loading, setLoading] = useState(true);
  const [preload, setPreload] = useState(true);
  const [forms, setForms] = useState({});
  const [percentage, setPercentage] = useState(0);
  const [submit, setSubmit] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [parentData, setParentData] = useState(null);
  const { notify } = useNotification();
  const { language, initialValue, forms: allForms } = store.useState((s) => s);
  const { active: activeLang } = language;
  const [hiddenQIds, setHiddenQIds] = useState([]);

  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const redirectToBatch = !authUser.is_superuser;

  const pagePath = [
    {
      title: text.controlCenter,
      link: "/control-center",
    },
    {
      title: text.manageDataTitle,
      link: "/control-center/data",
    },
    {
      title: forms.name,
    },
  ];

  const webformRef = useRef();
  /**
   * Idempotency token for the current submission attempt. Minted once and
   * reused across retries, so a POST that succeeded server-side but lost its
   * response does not create a second datapoint when the user presses submit
   * again. Cleared only after the backend confirms.
   */
  const submissionKeyRef = useRef(null);

  const backURL = useMemo(
    () =>
      parentData?.id && parentData?.form
        ? `/control-center/data/${parentData.form}/monitoring/${parentData.id}?form_id=${formId}`
        : `/control-center/data?form_id=${formId}`,
    [parentData, formId]
  );

  const submitFormData = async ({ datapoint, ...values }, refreshForm) => {
    // Get non-repeatable questions
    const nonRepeatableQuestions = forms.question_group
      .filter((group) => !group?.repeatable)
      .flatMap((group) => group.question);

    // Get repeatable questions
    const repeatableQuestions = forms.question_group
      .filter((group) => group?.repeatable)
      .flatMap((group) => group.question);

    // Validate required fields TODO: Identify why this validation was exist
    // Required validation has been done by Webform component
    // const questionIds = Object.keys(values).map((id) => parseInt(id, 10));
    // const requiredQuestions = nonRepeatableQuestions.filter(
    //   (q) => questionIds.includes(q?.id) && q.required
    // );

    // const hasEmptyRequired = requiredQuestions.some((q) => {
    //   const questionValue = values[q.id];
    //   const isEmptyValue =
    //     questionValue === null ||
    //     typeof questionValue === "undefined" ||
    //     (typeof questionValue === "string" && questionValue.trim() === "");

    //   if (isEmptyValue) {
    //     webformRef.current.setFields([
    //       {
    //         name: q.id,
    //         errors: [text.requiredError.replace("{{field}}", q.label)],
    //       },
    //     ]);
    //     return true;
    //   }
    //   return false;
    // });

    // if (hasEmptyRequired) {
    //   setSubmit(false);
    //   return;
    // }

    setSubmit(true);

    // Process non-repeatable File Uploads
    values = await processFileUploads(nonRepeatableQuestions, values);
    if (!values) {
      return; // Upload failed, function already showed error
    }
    // Process repeatable File Uploads
    values = await processFileUploads(repeatableQuestions, values);
    if (!values) {
      return; // Upload failed, function already showed error
    }

    // Process entity cascade questions
    values = await processEntityCascades(nonRepeatableQuestions, values);

    // Build answers array for non-repeatable questions
    const answers = Object.entries(values)
      .filter(([key, val]) => {
        // Skip keys that look like repeatable questions (contain a hyphen)
        if (key.includes("-")) {
          return false;
        }

        const questionId = parseInt(key, 10);
        const question = nonRepeatableQuestions?.find(
          (q) => q.id === questionId
        );
        if (!question) {
          return false;
        }

        if (question?.type === QUESTION_TYPES.date) {
          return typeof val !== "undefined" && moment(val).isValid();
        }

        // Skip hidden questions
        if (hiddenQIds.includes(questionId)) {
          return false;
        }

        // Skip empty non-required fields
        if (
          !question?.required &&
          (val === null ||
            typeof val === "undefined" ||
            (typeof val === "string" && val.trim() === ""))
        ) {
          return false;
        }

        return !isNaN(key);
      })
      .map(([key, val]) => {
        const questionId = parseInt(key, 10);
        const question = nonRepeatableQuestions.find(
          (q) => q.id === questionId
        );
        return transformValue(question, val, true);
      });

    // Process repeatable questions and add them to answers
    const repeatableAnswers = processRepeatableQuestions(
      values,
      repeatableQuestions
    );

    // Combine both answer sets
    const allAnswers = [...answers, ...repeatableAnswers];

    // Create datapoint name from meta fields or use default
    const names = allAnswers
      .filter(
        (x) =>
          x.meta &&
          ![
            QUESTION_TYPES.geo,
            QUESTION_TYPES.administration,
            QUESTION_TYPES.cascade,
          ].includes(x.type)
      )
      .map((x) => x.value)
      .flat()
      .join(" - ");

    const geo = allAnswers.find(
      (x) => x.type === QUESTION_TYPES.geo && x.meta
    )?.value;

    const administration = allAnswers.find(
      (x) => x.type === QUESTION_TYPES.administration
    )?.value;

    const datapointName = datapoint?.name
      ? datapoint.name
      : names.length
      ? names
      : `${authUser.administration.name} - ${moment().format("MMM YYYY")}`;

    if (!submissionKeyRef.current) {
      submissionKeyRef.current = crypto.randomUUID();
    }

    const dataPayload = {
      administration: administration
        ? Array.isArray(administration)
          ? administration[administration.length - 1]
          : administration
        : authUser.administration.id,
      name: datapointName,
      geo: geo || null,
      ...(uuid && { uuid }),
      submission_key: submissionKeyRef.current,
    };

    const payload = {
      data: dataPayload,
      answer: allAnswers
        .filter((a) => {
          // answer should have value defined
          return (
            Object.keys(a).includes("value") && typeof a.value !== "undefined"
          );
        })
        .map((x) => pick(x, ["question", "value", "index"])),
    };

    if (uuid) {
      window?.localStorage?.setItem("submitted", uuid);
    }

    try {
      await api.post(`form-pending-data/${formId}`, payload);
      // Confirmed. The next submission is a new one and must mint a new key;
      // reusing this one would make the backend treat it as a replay.
      submissionKeyRef.current = null;
      if (uuid) {
        store.update((s) => {
          s.initialValue = [];
        });
      }
      if (refreshForm) {
        refreshForm();
      }
      setHiddenQIds([]);
      setTimeout(() => setShowSuccess(true), 3000);
    } catch (error) {
      notify({
        type: "error",
        message: text.errorSomething,
      });
    } finally {
      setTimeout(() => setSubmit(false), 2000);
    }
  };

  const onFinishFailed = ({ errorFields }) => {
    if (errorFields.length) {
      notify({
        type: "error",
        message: text.errorMandatoryFields,
      });
    }
  };

  const onChange = ({ progress }) => {
    setPercentage(progress.toFixed(0));
  };

  const fetchInitialMonitoringData = useCallback(
    async ({ data: apiData }) => {
      try {
        const parentFormQuestions = allForms
          ?.find((f) => f?.id === apiData?.parent)
          ?.content?.question_group?.flatMap((qg) => qg?.question);
        const questions = apiData?.question_group?.flatMap(
          (qg) => qg?.question
        );
        const res = await fetch(
          `${window.location.origin}/datapoints/${uuid}.json`
        );
        const { answers: apiAnswers, id: parentId } = await res.json();
        setParentData({ id: parentId, form: apiData?.parent });
        const parentQuestionsMap = parentFormQuestions?.reduce((acc, q) => {
          acc[q.id] = q.name;
          return acc;
        }, {});
        const questionsMap = questions.reduce((acc, q) => {
          acc[q.name] = q.id;
          return acc;
        }, {});
        const answers = Object.entries(apiAnswers).reduce((acc, [key, val]) => {
          // split key with dash
          const [qKey, qIndex] = key.split("-");
          const qName = parentQuestionsMap?.[parseInt(qKey, 10)];
          const qId = questionsMap?.[qName];
          if (qIndex) {
            acc[`${qId}-${qIndex}`] = val;
            return acc;
          }
          acc[qId] = val;
          return acc;
        }, {});
        /**
         * Transform cascade answers
         */
        const cascadeQuestions = questions.filter(
          (q) =>
            q?.type === QUESTION_TYPES.cascade &&
            q?.extra?.type !== QUESTION_TYPES.entity &&
            q?.api?.endpoint
        );

        const cascadePromises = cascadeQuestions.map((q) =>
          getCascadeAnswerAPI(
            authUser?.administration?.level,
            q.id,
            q.api,
            answers?.[q.id]
          )
        );
        const cascadeResponses = await Promise.allSettled(cascadePromises);
        const cascadeValues = cascadeResponses
          .filter(({ status }) => status === "fulfilled")
          .map(({ value }) => value)
          .reduce((prev, curr) => {
            const [key, value] = Object.entries(curr)[0];
            prev[key] = value;
            return prev;
          }, {});
        /**
         * Transform answers to Webform format
         */
        const initialValue = Object.entries(answers)
          .filter(([key, val]) => {
            const questionId = parseInt(key, 10);
            const q = questions?.find((q) => q?.id === questionId);
            // if question required is false and value is empty then return false
            if (
              !q?.required &&
              (val === null ||
                typeof val === "undefined" ||
                (typeof val === "string" && val.trim() === ""))
            ) {
              return false;
            }
            return true;
          })
          .map(([key, val]) => {
            const questionId = isNaN(key) ? key : parseInt(key, 10);
            const q = questions?.find((q) => q?.id === questionId);
            const value = Object.keys(cascadeValues).includes(`${q?.id}`)
              ? cascadeValues[q.id]
              : transformValue(q?.type, val);
            return {
              question: questionId,
              value,
            };
          });
        store.update((s) => {
          s.initialValue = initialValue;
        });
      } catch (error) {
        Modal.error({
          title: text.updateDataError,
          content: String(error),
        });
      }
    },
    [uuid, text.updateDataError, allForms, authUser?.administration?.level]
  );

  useEffect(() => {
    if (isEmpty(forms) && formId) {
      api.get(`/form/web/${formId}`).then((res) => {
        const questionGroups = res.data.question_group.map((qg) => {
          const questions = qg.question
            .map((q) => {
              let qVal = { ...q };

              if (q?.extra) {
                delete qVal.extra;
                qVal = {
                  ...qVal,
                  ...q.extra,
                };
                if (q.extra?.allowOther) {
                  qVal = {
                    ...qVal,
                    allowOtherText: "Enter any OTHER value",
                  };
                }
                if (qVal?.type === "entity") {
                  qVal = {
                    ...qVal,
                    type: QUESTION_TYPES.cascade,
                    extra: q?.extra,
                  };
                }
              }
              return qVal;
            })
            .filter((x) => !x?.hidden); // filter out hidden questions
          return {
            ...qg,
            question: questions,
            repeatText: qg?.repeat_text,
          };
        });
        setForms({ ...res.data, question_group: questionGroups });
        // INITIAL VALUE FOR MONITORING
        if (uuid) {
          fetchInitialMonitoringData(res);
        }
        // EOL INITIAL VALUE FOR MONITORING
        setLoading(false);
      });
    }
    if (uuid && window?.localStorage?.getItem("submitted")) {
      /**
       * Redirect to the list when localStorage already has submitted item
       */
      window.localStorage.removeItem("submitted");
      navigate(backURL);
    }
    if (
      typeof webformRef?.current === "undefined" &&
      uuid &&
      initialValue?.length &&
      !loading
    ) {
      setPreload(true);
      setLoading(true);
    }

    if (
      webformRef?.current &&
      typeof webformRef?.current?.getFieldsValue()?.[0] === "undefined" &&
      uuid &&
      initialValue?.length
    ) {
      setTimeout(() => {
        initialValue.forEach((v) => {
          webformRef.current.setFieldsValue({ [v?.question]: v?.value });
        });
      }, 1000);
    }
  }, [
    formId,
    uuid,
    forms,
    loading,
    initialValue,
    backURL,
    navigate,
    fetchInitialMonitoringData,
  ]);

  const handleOnClearForm = useCallback((preload, initialValue) => {
    if (
      preload &&
      initialValue.length === 0 &&
      typeof webformRef?.current?.resetFields === "function"
    ) {
      setPreload(false);
      webformRef.current.resetFields();
      webformRef.current;
    }
  }, []);

  useEffect(() => {
    handleOnClearForm(preload, initialValue);
  }, [handleOnClearForm, preload, initialValue]);

  useEffect(() => {
    const handleBeforeUnload = (e) => {
      e.preventDefault();
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, []);

  return (
    <div id="form">
      <div className="description-container">
        <Row justify="center" gutter={[16, 16]}>
          <Col span={24} className="webform">
            <Space>
              <Breadcrumbs
                pagePath={pagePath}
                description={text.formDescription}
              />
            </Space>
            <DescriptionPanel description={text.formDescription} />
          </Col>
        </Row>
      </div>

      <div className="table-section">
        <div className="table-wrapper">
          {loading || isEmpty(forms) ? (
            <PageLoader message={text.fetchingForm} />
          ) : (
            !showSuccess && (
              <Webform
                formRef={webformRef}
                forms={forms}
                onFinish={submitFormData}
                onCompleteFailed={onFinishFailed}
                onChange={onChange}
                submitButtonSetting={{ loading: submit }}
                languagesDropdownSetting={{
                  showLanguageDropdown: false,
                }}
                initialValue={initialValue}
              />
            )
          )}
          {(!loading || !isEmpty(forms)) && !showSuccess && (
            <Progress className="progress-bar" percent={percentage} />
          )}
          {!loading && showSuccess && (
            <Result
              status="success"
              title={text?.formSuccessTitle}
              subTitle={
                redirectToBatch
                  ? text?.formSuccessSubTitle
                  : text?.formSuccessSubTitleForAdmin
              }
              extra={[
                <Button
                  type="primary"
                  key="back-button"
                  onClick={() => {
                    if (
                      typeof webformRef?.current?.resetFields === "function"
                    ) {
                      webformRef.current.resetFields();
                    }
                    setTimeout(() => {
                      setForms({});
                      setShowSuccess(false);
                    }, 500);
                  }}
                >
                  {text.newSubmissionBtn}
                </Button>,
                !redirectToBatch ? (
                  <Button key="manage-button" onClick={() => navigate(backURL)}>
                    {text.finishSubmissionBtn}
                  </Button>
                ) : (
                  <Button
                    key="batch-button"
                    onClick={() => navigate("/control-center/data/submissions")}
                  >
                    {text.finishSubmissionBatchBtn}
                  </Button>
                ),
              ]}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default Forms;
