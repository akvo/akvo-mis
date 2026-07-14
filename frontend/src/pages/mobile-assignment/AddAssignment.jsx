import React, {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useRef,
} from "react";
import {
  Row,
  Col,
  Form,
  Button,
  Input,
  Select,
  Space,
  Modal,
  TreeSelect,
} from "antd";
import { useNavigate, useParams } from "react-router-dom";
import { api, store, uiText } from "../../lib";
import {
  AdministrationDropdown,
  Breadcrumbs,
  DescriptionPanel,
} from "../../components";
import { useNotification } from "../../util/hooks";
import "./style.scss";

const AddAssignment = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const { notify } = useNotification();
  const {
    forms: userForms,
    user: authUser,
    language,
    levels,
    administration: selectedAdm,
  } = store.useState((s) => s);
  const [editAssignment, setEditAssignment] = useState(null);
  const userAdmLevel =
    levels.find((l) => l?.level === authUser.administration.level)?.id || null;
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [preload, setPreload] = useState(true);
  const [level, setLevel] = useState(userAdmLevel);
  const [admLevel, setAdmLevel] = useState(null);
  const [selectedAdministrations, setSelectedAdministrations] = useState([]);
  const [formFeedback, setFormFeedback] = useState(null);

  const lowestLevel = levels
    .slice()
    .sort((a, b) => a.level - b.level)
    .slice(-1)?.[0];

  const admLevels = levels
    .slice()
    .filter((l) => l?.id >= userAdmLevel)
    .sort((a, b) => a?.level - b?.level);

  const NATIONAL_LEVEL = levels?.find((l) => l.level === 0)?.id;

  const showLevel = userAdmLevel !== lowestLevel?.id;

  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);
  const pageTitle = id ? text.mobileEditText : text.mobileAddText;
  const descriptionData = (
    <p>{id ? text.mobilePanelEditDesc : text.mobilePanelAddDesc}</p>
  );
  const pagePath = [
    {
      title: text.controlCenter,
      link: "/control-center",
    },
    {
      title: text.mobilePanelTitle,
      link: "/control-center/mobile-assignment",
    },
    {
      title: pageTitle,
    },
  ];
  // Build tree data for form selection
  // Registration forms are parents, monitoring forms are children
  const formTreeData = useMemo(() => {
    const registrationForms = userForms.filter((f) => !f?.content?.parent);
    return registrationForms.map((reg) => {
      const monitoringForms = userForms.filter(
        (f) => f?.content?.parent === reg.id
      );
      return {
        title: reg.name,
        value: reg.id,
        key: `reg-${reg.id}`,
        children: monitoringForms.map((mon) => ({
          title: mon.name,
          value: mon.id,
          key: `mon-${mon.id}`,
        })),
      };
    });
  }, [userForms]);

  // Track previous form selection to detect unchecking
  const prevFormsRef = useRef([]);

  // Handle form selection change - auto-select parent when child is selected
  const handleFormChange = useCallback(
    (selectedValues) => {
      const prevValues = prevFormsRef.current;
      const currentIds = selectedValues.map((v) => v.value || v);
      const prevIds = prevValues.map((v) => v.value || v);

      // Detect unchecked registration forms (parents removed)
      const registrationForms = userForms.filter((f) => !f?.content?.parent);
      const uncheckedRegistrations = prevIds.filter(
        (formId) =>
          registrationForms.some((r) => r.id === formId) &&
          !currentIds.includes(formId)
      );

      // Remove children of unchecked registrations
      let filteredIds = currentIds.filter((formId) => {
        const formItem = userForms.find((f) => f.id === formId);
        if (formItem?.content?.parent) {
          return !uncheckedRegistrations.includes(formItem.content.parent);
        }
        return true;
      });

      // For each selected child, ensure its parent is also selected
      const selectedSet = new Set(filteredIds);
      filteredIds.forEach((formId) => {
        const formItem = userForms.find((f) => f.id === formId);
        if (formItem?.content?.parent) {
          selectedSet.add(formItem.content.parent);
        }
      });

      const newValues = Array.from(selectedSet);
      prevFormsRef.current = newValues;
      form.setFieldsValue({ forms: newValues });
    },
    [userForms, form]
  );

  const fetchUserAdmin = useCallback(async () => {
    try {
      const { data: _userAdm } = await api.get(
        `administration/${authUser.administration.id}`
      );
      store.update((s) => {
        s.administration = [_userAdm];
      });
    } catch (error) {
      console.error(error);
    }
  }, [authUser]);

  useEffect(() => {
    fetchUserAdmin();
  }, [fetchUserAdmin]);

  useEffect(() => {
    if (!editAssignment && id) {
      api
        .get(`/mobile-assignments/${id}`)
        .then(({ data }) => {
          setEditAssignment(data);
          const formIds = data.forms.map((f) => f?.id);
          prevFormsRef.current = formIds;
          form.setFieldsValue({
            ...data,
            administrations: data.administrations.map((a) => a?.id),
            forms: formIds,
          });
        })
        .catch((error) => {
          console.error(error);
        });
    }
  }, [id, form, editAssignment]);

  const deleteAssginment = async () => {
    try {
      await api.delete(`/mobile-assignments/${id}`);
      navigate("/control-center/mobile-assignment");
    } catch {
      Modal.error({
        title: text.mobileErrDelete,
        content: (
          <>
            {text.errDeleteCascadeText1}
            <br />
            <em>{text.errDeleteCascadeText2}</em>
          </>
        ),
      });
    }
  };

  const onDelete = () => {
    Modal.confirm({
      title: `${text.deleteText} ${editAssignment?.name}`,
      content: text.mobileConfirmDelete,
      onOk: () => {
        deleteAssginment();
      },
    });
  };

  const onSelectLevel = async (val) => {
    // reset administrations
    form.setFieldsValue({ administrations: [] });
    setSelectedAdministrations([]);
    setLevel(val);
    const findLevel = levels?.find((l) => l.id === val);
    setAdmLevel(findLevel);
  };

  const onFinish = async ({ name, forms }) => {
    setSubmitting(true);
    setFormFeedback(null);
    try {
      const administrations = selectedAdministrations?.length
        ? selectedAdministrations?.map((adm) => adm?.id || adm)
        : authUser?.is_superuser
        ? [authUser.administration.id]
        : authUser?.roles?.map((r) => r?.administration?.id);
      const payload = {
        name,
        forms,
        administrations,
      };
      if (id) {
        await api.put(`/mobile-assignments/${id}`, payload);
      } else {
        await api.post("/mobile-assignments", payload);
      }
      notify({
        type: "success",
        message: id ? text.mobileSuccessUpdated : text.mobileSuccessAdded,
      });
      setLoading(false);
      navigate("/control-center/mobile-assignment");
    } catch (error) {
      const { response: errorResponse } = error.request || {};
      const { forms: _formErrors } = JSON.parse(errorResponse || "{}");
      if (_formErrors) {
        const _formFeedback = _formErrors.map((f) => {
          // Handle parent/child validation errors
          if (f.required_registration) {
            return text.errorMonitoringRequiresRegistration(
              f.monitoring_form,
              f.required_registration
            );
          }
          // Handle entity validation errors
          if (f.exists === "True") {
            return text.errorEntityData(f.entity);
          }
          return text.errorEntityNotExists(f.entity);
        });
        setFormFeedback(_formFeedback);
      }
      setSubmitting(false);
    }
  };

  const fetchData = useCallback(async () => {
    if (id && preload && editAssignment?.id && selectedAdm) {
      setPreload(false);
      const adms = await Promise.all(
        (editAssignment.administrations.map((a) => a?.id) ?? [])
          .filter((p) => p)
          .map(async (pID) => {
            const apiResponse = await api.get(`administration/${pID}`);
            return apiResponse.data;
          })
      );
      if (adms) {
        setLevel(adms[0].level + 1);
        setAdmLevel(levels.find((l) => l?.level === adms[0].level));
        form.setFieldsValue({ level_id: adms[0].level + 1 });
        setSelectedAdministrations(adms.map((adm) => adm.id));
      }
      const parentAdm = await Promise.all(
        (adms?.[0]?.path?.split(".") ?? [])
          .filter((p) => p)
          .map(async (pID) => {
            const apiResponse = await api.get(`administration/${pID}`);
            return apiResponse.data;
          })
      );
      store.update((s) => {
        s.administration = [...parentAdm, ...adms]
          ?.slice(
            [...parentAdm, ...adms].findIndex(
              (r) => r.id === authUser.administration.id
            )
          )
          .map((a) => {
            const childLevel = levels.filter((l) => l?.level === a.level);
            return {
              ...a,
              childLevelName: childLevel?.name || null,
            };
          });
      });
    }
    if (!id && preload) {
      setPreload(false);
    }

    const admValues = selectedAdm
      ?.filter((adm) => adm?.level === admLevel?.level)
      ?.map((adm) => adm?.id);
    if (admValues?.length && selectedAdministrations?.length === 0) {
      setSelectedAdministrations(admValues);
      form.setFieldsValue({ administrations: admValues });
    }
  }, [
    id,
    preload,
    form,
    editAssignment,
    levels,
    selectedAdm,
    authUser,
    selectedAdministrations,
    admLevel,
  ]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div id="add-assignment">
      <div className="description-container">
        <Row justify="space-between">
          <Col>
            <Breadcrumbs pagePath={pagePath} />
            <DescriptionPanel description={descriptionData} title={pageTitle} />
          </Col>
        </Row>
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <Form
            name="adm-form"
            form={form}
            labelCol={{ span: 6 }}
            wrapperCol={{ span: 18 }}
            initialValues={{
              level_id: userAdmLevel,
            }}
            onFinish={onFinish}
          >
            <Row className="form-row">
              <Col span={24}>
                <Form.Item
                  name="name"
                  label={text.mobileLabelName}
                  rules={[
                    {
                      required: true,
                      message: text.mobileNameRequired,
                    },
                  ]}
                >
                  <Input />
                </Form.Item>
              </Col>
            </Row>
            {showLevel && (
              <div className="form-row">
                <Form.Item
                  name="level_id"
                  label={text.admLevel}
                  rules={[
                    {
                      required: true,
                      message: text.mobileLevelRequired,
                    },
                  ]}
                >
                  <Select
                    getPopupContainer={(trigger) => trigger.parentNode}
                    placeholder={text.selectLevel}
                    onChange={onSelectLevel}
                    fieldNames={{ value: "id", label: "name", level: "level" }}
                    options={admLevels}
                    allowClear
                  />
                </Form.Item>
              </div>
            )}
            {admLevel !== null &&
              level !== NATIONAL_LEVEL &&
              selectedAdm?.[0]?.level !== admLevel?.level && (
                <div className="form-row">
                  <Form.Item
                    name="administrations"
                    label={text.mobileLabelAdm}
                    rules={[
                      { required: true, message: text.mobileAdmRequired },
                    ]}
                  >
                    <AdministrationDropdown
                      size="large"
                      width="100%"
                      direction="vertical"
                      maxLevel={level}
                      onChange={(values) => {
                        if (values) {
                          setSelectedAdministrations(values);
                        }
                      }}
                      persist={id ? true : false}
                      allowMultiple
                      showSelectAll={true}
                      selectedAdministrations={selectedAdministrations}
                    />
                  </Form.Item>
                </div>
              )}
            <div className="form-row">
              <Form.Item
                name="forms"
                label={text.mobileLabelForms}
                rules={[{ required: true, message: text.mobileFormsRequired }]}
                validateStatus={formFeedback ? "error" : "success"}
                hasFeedback={formFeedback}
                help={
                  <ul>
                    {formFeedback?.map((feedback, fx) => (
                      <li key={fx}>{feedback}</li>
                    ))}
                  </ul>
                }
              >
                <TreeSelect
                  getPopupContainer={(trigger) => trigger.parentNode}
                  placeholder={text.mobileSelectForms}
                  treeData={formTreeData}
                  treeCheckable
                  treeCheckStrictly
                  showCheckedStrategy={TreeSelect.SHOW_ALL}
                  treeDefaultExpandAll
                  allowClear
                  loading={loading}
                  onChange={handleFormChange}
                  className="custom-select"
                  maxTagCount="responsive"
                />
              </Form.Item>
            </div>
            <Row justify="center" align="middle">
              <Col span={18} offset={6}>
                <Space>
                  <Button
                    type="primary"
                    htmlType="submit"
                    shape="round"
                    loading={submitting}
                  >
                    {text.mobileButtonSave}
                  </Button>
                  {id && (
                    <Button type="danger" shape="round" onClick={onDelete}>
                      {text.deleteText}
                    </Button>
                  )}
                </Space>
              </Col>
            </Row>
          </Form>
        </div>
      </div>
    </div>
  );
};

export default React.memo(AddAssignment);
