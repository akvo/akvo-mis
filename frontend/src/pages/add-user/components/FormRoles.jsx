import React from "react";
import { Form, Space, Select, Button, Row, Col } from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import AdministrationInput from "./AdministrationInput";
import { store } from "../../../lib";

const FormRoles = ({ form, text, roles = [], disabled = false }) => {
  const authUser = store.useState((s) => s.user);
  const maxRoleLevel = authUser?.is_superuser
    ? authUser.administration?.level
    : authUser?.roles?.length
    ? Math.min(...authUser.roles.map((r) => r?.administration?.level))
    : null;
  return (
    <Form.List
      name="roles"
      hasFeedback
      rules={[
        () => ({
          validator(_, value) {
            if (value?.length > 0) {
              return Promise.resolve();
            }
            return Promise.reject(new Error(text.rolesRequired));
          },
        }),
      ]}
    >
      {(fields, { add, remove }) => (
        <>
          {fields.map((field) => {
            // AdministrationInput treats maxLevel as a 1-indexed depth, so
            // pass the role's level + 1 (e.g. a Province role, level 1, must
            // allow selecting down to level 1 => depth 2). administration_level
            // is a Levels record id, not a depth, and using it let the user
            // pick an administration deeper than the role, which the backend
            // then rejects as "Role and administration level mismatch".
            const selectedRole = roles?.find(
              (r) =>
                r.value === form.getFieldValue(["roles", field.name, "role"])
            );
            const maxLevel =
              typeof selectedRole?.level === "number"
                ? selectedRole.level + 1
                : null;

            return (
              <Row key={field.key} gutter={8}>
                <Col>
                  <Space align="baseline">
                    <Form.Item
                      noStyle
                      shouldUpdate={(prevValues, currentValues) =>
                        prevValues.roles?.[field.name]?.role !==
                        currentValues.roles?.[field.name]?.role
                      }
                    >
                      {() => (
                        <Form.Item
                          {...field}
                          name={[field.name, "role"]}
                          rules={[
                            {
                              required: true,
                            },
                          ]}
                        >
                          <Select
                            showSearch
                            placeholder={text.selectRole}
                            options={roles.filter(
                              (r) => r?.level >= maxRoleLevel
                            )}
                            optionFilterProp="label"
                            filterOption={(input, option) =>
                              option.label
                                .toLowerCase()
                                .includes(input.toLowerCase())
                            }
                            style={{ minWidth: 240, width: "100%" }}
                            disabled={disabled}
                          />
                        </Form.Item>
                      )}
                    </Form.Item>
                    <Form.Item {...field} name={[field.name, "administration"]}>
                      <AdministrationInput
                        width="100%"
                        maxLevel={maxLevel}
                        disabled={disabled}
                      />
                    </Form.Item>
                    <MinusCircleOutlined
                      onClick={() => remove(field.name)}
                      disabled={disabled}
                    />
                  </Space>
                </Col>
              </Row>
            );
          })}

          <Form.Item>
            <Button
              type="dashed"
              onClick={() => {
                // Get the administration from the last item if it exists
                const lastIndex = fields.length - 1;
                const lastItemAdministration =
                  lastIndex >= 0
                    ? form.getFieldValue(["roles", lastIndex, "administration"])
                    : null;
                if (lastItemAdministration) {
                  // Add new item with default administration from previous item
                  add({ administration: lastItemAdministration });
                } else {
                  // If no previous item, just add a new empty item
                  add();
                }
              }}
              icon={<PlusOutlined />}
              disabled={disabled}
              block
            >
              {text.addRole}
            </Button>
          </Form.Item>
        </>
      )}
    </Form.List>
  );
};

export default FormRoles;
