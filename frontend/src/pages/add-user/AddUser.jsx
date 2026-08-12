import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Row,
  Col,
  Form,
  Button,
  Input,
  Select,
  Checkbox,
  Modal,
  Table,
  Spin,
  Radio,
} from "antd";
import { useNavigate, useParams } from "react-router-dom";
import { api, store, config, uiText } from "../../lib";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { takeRight } from "lodash";
import { useNotification } from "../../util/hooks";
import { FormRoles } from "./components";
const { Option } = Select;

const AddUser = () => {
  const {
    user: authUser,
    administration,
    forms: allForms,
    loadingForm,
    language,
  } = store.useState((s) => s);
  const { active: activeLang } = language;
  const forms = allForms.filter((f) => !f?.content?.parent);

  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [roles, setRoles] = useState([]);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const { notify } = useNotification();
  const { id } = useParams();
  const [organisations, setOrganisations] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [modalContent, setModalContent] = useState([]);
  const [isUserFetched, setIsUserFetched] = useState(false);

  const isSelfData = id && authUser?.id === parseInt(id, 10);

  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);
  const panelTitle = id ? text.editUser : text.addUser;

  useEffect(() => {
    if (!organisations.length) {
      // filter by 1 for member attribute
      api.get("organisations?filter=1").then((res) => {
        setOrganisations(res.data);
      });
    }
  }, [organisations]);

  const pagePath = [
    {
      title: text.controlCenter,
      link: "/control-center",
    },
    {
      title: text.manageUsers,
      link: "/control-center/users",
    },
    {
      title: id ? text.editUser : text.addUser,
    },
  ];

  const onCloseModal = () => {
    setIsModalVisible(false);
    setModalContent([]);
  };

  const onFinish = (values) => {
    setSubmitting(true);
    const userAdm = authUser?.administration?.id;
    const payload = {
      ...values,
      roles: (values.roles || []).map((r) => ({
        role: r.role,
        administration: Array.isArray(r.administration)
          ? takeRight(r.administration, 1)?.[0] || userAdm
          : r.administration || userAdm,
      })),
    };
    api[id ? "put" : "post"](id ? `user/${id}` : "user", payload)
      .then(() => {
        notify({
          type: "success",
          message: `User ${id ? "updated" : "added"}`,
        });
        setSubmitting(false);
        navigate("/control-center/users");
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          setIsModalVisible(true);
          setModalContent(err?.response?.data?.message);
        } else {
          const details = err?.response?.data?.details || {};
          if (details.email) {
            form.setFields([
              {
                name: "email",
                errors: Array.isArray(details.email)
                  ? details.email
                  : [details.email],
              },
            ]);
            notify({
              type: "error",
              message:
                err?.response?.data?.message ||
                `User could not be ${id ? "updated" : "added"}`,
            });
          } else {
            notify({
              type: "error",
              message:
                err?.response?.data?.message ||
                `User could not be ${id ? "updated" : "added"}`,
            });
          }
        }
        setSubmitting(false);
      });
  };

  useEffect(() => {
    const fetchData = async (adminId, acc) => {
      const adm = await config.fn.administration(adminId);
      acc.unshift(adm);
      if (adm.level > 0) {
        fetchData(adm.parent, acc);
      } else {
        store.update((s) => {
          s.administration = acc;
        });
      }
    };
    if (id && !isUserFetched) {
      setIsUserFetched(true);
      setLoading(true);
      try {
        api.get(`user/${id}`).then((res) => {
          form.setFieldsValue({
            administration: res.data?.administration,
            email: res.data?.email,
            first_name: res.data?.first_name,
            last_name: res.data?.last_name,
            phone_number: res.data?.phone_number,
            forms: res.data?.forms?.map((f) => f.id) || [],
            organisation: res.data?.organisation?.id || [],
            trained: res?.data?.trained,
            is_superuser: res.data?.is_superuser || false,
            roles:
              res.data?.roles?.map((r) => ({
                role: r.role,
                administration: r.adm_path,
              })) || [],
            inform_user: !id
              ? true
              : authUser?.email === res.data?.email
                ? false
                : true,
          });
          setLoading(false);
          fetchData(res.data.administration?.id, []);
        });
      } catch (error) {
        notify({ type: "error", message: text.errorUserLoad });
        setLoading(false);
      }
    }
  }, [
    id,
    form,
    forms,
    notify,
    text.errorUserLoad,
    authUser?.email,
    isUserFetched,
    administration,
  ]);

  const fetchRoles = useCallback(async () => {
    try {
      const { data: apiData } = await api.get("/user/roles");
      setRoles(apiData);
    } catch (error) {
      console.error("Failed to fetch roles:", error);
    }
  }, []);

  useEffect(() => {
    fetchRoles();
  }, [fetchRoles]);

  return (
    <div id="add-user">
      <div className="description-container">
        <Row justify="space-between">
          <Col>
            <Breadcrumbs pagePath={pagePath} />
            <DescriptionPanel
              description={text.addUserDescription}
              title={panelTitle}
            />
          </Col>
        </Row>
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          {loading ? (
            <Row justify="center" align="middle" style={{ minHeight: 400 }}>
              <Col>
                <Spin tip={text.loadingText} spinning />
              </Col>
            </Row>
          ) : (
            <Form
              name="adm-form"
              form={form}
              labelCol={{ span: 6 }}
              wrapperCol={{ span: 18 }}
              initialValues={{
                first_name: "",
                last_name: "",
                phone_number: "",
                email: "",
                inform_user: true,
                organisation: null,
                is_superuser: false,
                roles: [{ role: roles?.[0]?.value, administration: [] }],
                forms: [],
              }}
              onFinish={onFinish}
            >
              {(_, formInstance) => (
                <>
                  <div className="form-row">
                    <Form.Item
                      label={text.userFirstName}
                      name="first_name"
                      rules={[
                        {
                          required: true,
                          message: text.valFirstName,
                        },
                      ]}
                    >
                      <Input />
                    </Form.Item>
                  </div>
                  <div className="form-row">
                    <Form.Item
                      label={text.userLastName}
                      name="last_name"
                      rules={[
                        {
                          required: true,
                          message: text.valLastName,
                        },
                      ]}
                    >
                      <Input />
                    </Form.Item>
                  </div>
                  <div className="form-row">
                    <Form.Item
                      label={text.userEmail}
                      name="email"
                      rules={[
                        {
                          required: true,
                          message: text.valEmail,
                          type: "email",
                        },
                      ]}
                    >
                      <Input />
                    </Form.Item>
                  </div>
                  <div className="form-row">
                    <Form.Item
                      label={text.userPhoneNumber}
                      name="phone_number"
                      rules={[
                        {
                          required: true,
                          message: text.valPhone,
                        },
                      ]}
                    >
                      <Input />
                    </Form.Item>
                  </div>
                  <div className="form-row">
                    <Form.Item
                      name="organisation"
                      label={text.userOrganisation}
                      rules={[
                        { required: true, message: text.valOrganization },
                      ]}
                    >
                      <Select
                        getPopupContainer={(trigger) => trigger.parentNode}
                        placeholder={text.selectOne}
                        allowClear
                        showSearch
                        optionFilterProp="children"
                        filterOption={(input, option) =>
                          option.children
                            .toLowerCase()
                            .indexOf(input.toLowerCase()) >= 0
                        }
                      >
                        {organisations?.map((o, oi) => (
                          <Option key={`org-${oi}`} value={o.id}>
                            {o.name}
                          </Option>
                        ))}
                      </Select>
                    </Form.Item>
                  </div>
                  {authUser?.is_superuser && (
                    <div className="form-row">
                      <Form.Item
                        label={text.isSuperAdminLabel}
                        name="is_superuser"
                      >
                        <Radio.Group disabled={isSelfData}>
                          <Radio value={true}>{text.yesText}</Radio>
                          <Radio value={false}>{text.noText}</Radio>
                        </Radio.Group>
                      </Form.Item>
                    </div>
                  )}
                  {!formInstance.getFieldValue("is_superuser") && (
                    <Row
                      justify="start"
                      align="stretch"
                      className="form-row"
                      style={{ marginTop: "24px" }}
                    >
                      <Col span={6} className=" ant-form-item-label">
                        <label>{text.rolesLabel}</label>
                      </Col>
                      <Col span={18}>
                        <FormRoles
                          form={formInstance}
                          roles={roles}
                          text={text}
                          disabled={isSelfData}
                        />
                      </Col>
                    </Row>
                  )}
                  {!formInstance.getFieldValue("is_superuser") && (
                    <div className="form-row" style={{ marginTop: 24 }}>
                      {loadingForm || loading ? (
                        <>
                          <div className="ant-form-item-label">
                            <label title={text.questionnairesLabel}>
                              {text.questionnairesLabel}
                            </label>
                          </div>
                          <p style={{ paddingLeft: 12, color: "#6b6b6f" }}>
                            {text.loadingText}
                          </p>
                        </>
                      ) : (
                        <Form.Item
                          name="forms"
                          label={text.questionnairesLabel}
                          rules={[{ required: false }]}
                        >
                          <Select
                            mode="multiple"
                            getPopupContainer={(trigger) => trigger.parentNode}
                            placeholder={text.selectText}
                            options={forms}
                            optionFilterProp="name"
                            fieldNames={{ label: "name", value: "id" }}
                            allowClear
                          />
                        </Form.Item>
                      )}
                    </div>
                  )}
                  <Row justify="center" align="middle">
                    <Col span={18} offset={6}>
                      <Form.Item
                        id="informUser"
                        label=""
                        valuePropName="checked"
                        name="inform_user"
                        rules={[{ required: false }]}
                      >
                        <Checkbox
                          disabled={
                            !id
                              ? true
                              : authUser?.email === form.getFieldValue("email")
                                ? true
                                : false
                          }
                        >
                          {text.informUser}
                        </Checkbox>
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row justify="center" align="middle">
                    <Col span={18} offset={6}>
                      <Button
                        type="primary"
                        htmlType="submit"
                        shape="round"
                        loading={submitting}
                      >
                        {id ? text.updateUser : text.addUser}
                      </Button>
                    </Col>
                  </Row>
                </>
              )}
            </Form>
          )}
        </div>
      </div>

      {/* Notification modal */}
      <Modal
        open={isModalVisible}
        onCancel={onCloseModal}
        centered
        width="575px"
        footer={
          <Row justify="center" align="middle">
            <Col>
              <Button className="light" onClick={onCloseModal}>
                {text.cancelButton}
              </Button>
            </Col>
          </Row>
        }
        bodystyle={{ textAlign: "center" }}
      >
        <img src="/assets/user.svg" height="80" />
        <br />
        <br />
        <p>{text.existingApproverTitle}</p>
        <Table
          columns={[
            {
              title: text.formColumn,
              dataIndex: "form",
            },
            {
              title: text.administrationLabel,
              dataIndex: "administration",
            },
          ]}
          dataSource={modalContent}
          rowKey="id"
          pagination={false}
        />
        <br />
        <p>{text.existingApproverDescription}</p>
      </Modal>
    </div>
  );
};

export default AddUser;
