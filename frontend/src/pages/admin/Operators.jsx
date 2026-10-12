import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Table, Button, Space, Tag, Modal, Form, Input } from "antd";
import { api, store, uiText } from "../../lib";
import { useNotification } from "../../util/hooks";

const Operators = () => {
  const { notify } = useNotification();
  const [dataset, setDataset] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inviting, setInviting] = useState(false);
  const [email, setEmail] = useState("");
  const { user, language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const load = useCallback(() => {
    api
      .get("admin/operators")
      .then((res) => setDataset(res.data))
      .catch(() =>
        notify({ type: "error", message: "Could not load operators" })
      )
      .finally(() => setLoading(false));
  }, [notify]);

  useEffect(load, [load]);

  const invite = () => {
    api
      .post("admin/operators", { email })
      .then(() => {
        setInviting(false);
        setEmail("");
        load();
      })
      .catch((err) =>
        notify({
          type: "error",
          message: err?.response?.data?.message || "Could not invite",
        })
      );
  };

  const revoke = (operator) => {
    Modal.confirm({
      title: `Revoke ${operator.email}?`,
      content:
        "They lose console access immediately, including any inspection " +
        "session already open. The account itself remains.",
      okText: text.consoleRevoke,
      okButtonProps: { danger: true },
      // Returned, not fired and forgotten: antd keeps the dialog's OK
      // button spinning until this settles, so a rejection with no
      // catch leaves it spinning for ever and tells the operator
      // nothing about why the revoke did not happen.
      onOk: () =>
        api
          .delete(`admin/operators/${operator.id}`)
          .then(load)
          .catch((err) =>
            notify({
              type: "error",
              message: err?.response?.data?.message || "Could not revoke",
            })
          ),
    });
  };

  const columns = [
    { title: "Name", dataIndex: "name", key: "name" },
    { title: "Email", dataIndex: "email", key: "email" },
    {
      title: "Status",
      dataIndex: "state",
      key: "state",
      render: (state, row) => (
        <Space>
          <Tag color={state === "active" ? "green" : "orange"}>{state}</Tag>
          {row.id === user?.id && <Tag>You</Tag>}
        </Space>
      ),
    },
    {
      title: "",
      key: "action",
      align: "right",
      // No self-revoke. Doing it would end the session mid-request and
      // leave the console reachable only by whoever else holds the flag.
      render: (_, row) =>
        row.id === user?.id ? null : (
          <Button size="small" danger onClick={() => revoke(row)}>
            {text.consoleRevoke}
          </Button>
        ),
    },
  ];

  return (
    <div>
      <Space
        style={{ width: "100%", justifyContent: "space-between" }}
        align="end"
      >
        <h1>{text.consoleOperators}</h1>
        <Button type="primary" shape="round" onClick={() => setInviting(true)}>
          {text.consoleInviteOperator}
        </Button>
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={dataset}
        loading={loading}
        pagination={false}
      />

      <Modal
        open={inviting}
        title={text.consoleInviteOperator}
        okText="Invite"
        onCancel={() => setInviting(false)}
        onOk={invite}
      >
        <Form layout="vertical">
          {/* Explicit id: Form.Item derives htmlFor from a field `name`,
              which this controlled input does not have. */}
          <Form.Item label="Email" htmlFor="invite-email">
            <Input
              id="invite-email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Operators;
