import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Row, Col, Card, Table, Switch, Button, Space, Tag, Modal } from "antd";
import { Link, useParams } from "react-router-dom";
import { api, store, uiText } from "../../lib";
import { useNotification } from "../../util/hooks";

const TILES = [
  ["users", "Users"],
  ["forms", "Forms"],
  ["dashboards", "Dashboards"],
  ["datapoints", "Datapoints"],
  ["devices", "Devices"],
];

const TenantDetail = () => {
  const { id } = useParams();
  const { notify } = useNotification();
  const [tenant, setTenant] = useState(null);
  const [users, setUsers] = useState([]);
  const [saving, setSaving] = useState(false);
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const load = useCallback(() => {
    // Cleared first: without this, editing the id in the address bar
    // leaves the previous workspace's name, counts, features and user
    // list on screen under the new id until the fetch lands — and for
    // good if it fails.
    setTenant(null);
    setUsers([]);
    Promise.all([
      api.get(`admin/tenants/${id}`),
      api.get(`admin/tenants/${id}/users`),
    ])
      .then(([detail, people]) => {
        setTenant(detail.data);
        setUsers(people.data);
      })
      .catch(() =>
        notify({ type: "error", message: "Could not load the workspace" })
      );
  }, [id, notify]);

  useEffect(load, [load]);

  const toggleFeature = (key, enabled) => {
    setSaving(true);
    api
      .put(`admin/tenants/${id}/features`, { [key]: enabled })
      .then((res) => setTenant(res.data))
      .catch(() =>
        notify({ type: "error", message: "Could not save entitlements" })
      )
      .finally(() => setSaving(false));
  };

  // Reloads rather than patching the row in place: deactivating a user
  // changes the workspace's device count too, and the tiles above the
  // table would otherwise disagree with the row that caused it.
  const setUserActive = (userId, active) => {
    api
      .post(`admin/users/${userId}/${active ? "activate" : "deactivate"}`)
      .then(load)
      .catch(() =>
        notify({ type: "error", message: "Could not update the user" })
      );
  };

  const setTenantActive = (active) => {
    api
      .post(`admin/tenants/${id}/${active ? "activate" : "deactivate"}`)
      .then((res) => setTenant(res.data))
      .catch(() =>
        notify({ type: "error", message: "Could not update the workspace" })
      );
  };

  const confirmDelete = () => {
    Modal.confirm({
      title: `Delete ${tenant.subdomain}?`,
      // States the consequence rather than asking "are you sure". Soft
      // delete is reversible only from a shell, so this dialog is the
      // last point a mis-click can be caught.
      content:
        "The address stops resolving and every session ends. Data is " +
        "retained, but restoring the workspace is a shell operation.",
      okText: text.consoleDelete,
      okButtonProps: { danger: true },
      onOk: () =>
        api
          .delete(`admin/tenants/${id}`)
          .then((res) => setTenant(res.data))
          .catch(() =>
            notify({
              type: "error",
              message: "Could not delete the workspace",
            })
          ),
    });
  };

  if (!tenant) {
    return null;
  }

  const userColumns = [
    { title: "Name", dataIndex: "name", key: "name" },
    { title: "Email", dataIndex: "email", key: "email" },
    {
      title: "Status",
      dataIndex: "state",
      key: "state",
      render: (state, row) => (
        <>
          <span>{state}</span>
          {state === "deactivated" && row.devices > 0 && (
            <div className="admin-subtle">{`${row.devices} devices blocked`}</div>
          )}
        </>
      ),
    },
    { title: "Devices", dataIndex: "devices", key: "devices" },
    {
      title: "",
      key: "action",
      align: "right",
      render: (_, row) => (
        <Button
          size="small"
          onClick={() => setUserActive(row.id, row.state !== "active")}
        >
          {row.state === "active"
            ? text.consoleDeactivate
            : text.consoleReactivate}
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Link to="/admin/tenants">{text.consoleTenants}</Link>
      <h1>
        {tenant.subdomain} <Tag>{tenant.state}</Tag>
      </h1>
      <div className="admin-subtle">{tenant.name}</div>

      {/* Nothing here applies to a deleted workspace. Restore only
          flips is_active, which the deleted state ignores, so the
          button would report success and change nothing visible; and
          deleting again would only re-stamp deleted_at. Undoing a
          delete is a shell operation, exactly as the delete dialog
          says — offering a button that contradicts it is worse than
          offering nothing. */}
      {tenant.state !== "deleted" && (
        <Space style={{ marginTop: 8 }}>
          <Button onClick={() => setTenantActive(tenant.state !== "active")}>
            {tenant.state === "active"
              ? text.consoleSuspend
              : text.consoleRestore}
          </Button>
          <Button danger onClick={confirmDelete}>
            {text.consoleDelete}
          </Button>
        </Space>
      )}

      <Row gutter={14} style={{ marginTop: 16 }}>
        {TILES.map(([key, label]) => (
          <Col span={4} key={key}>
            <Card size="small">
              <div className="admin-subtle">{label}</div>
              <div className="admin-tile-value">
                {(tenant[key] ?? 0).toLocaleString("en-US")}
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={16}>
          <Card title={text.consoleUsers} size="small">
            <Table
              rowKey="id"
              columns={userColumns}
              dataSource={users}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col span={8}>
          {/* One switch per FeatureFlags key on the backend, which
              today means one. The backend rejects a key it does not
              know with a 400, so a switch added here out of step fails
              loudly rather than storing a flag nothing reads. */}
          <Card title={text.consoleFeatures} size="small">
            <Space
              align="start"
              style={{ width: "100%", justifyContent: "space-between" }}
            >
              <div>
                <div>Embedded dashboard</div>
                <div className="admin-subtle">
                  Lets this workspace publish dashboards into third-party pages.
                </div>
              </div>
              <Switch
                aria-label="Embedded dashboard"
                disabled={saving}
                checked={Boolean(tenant.features?.embedded_dashboard)}
                onChange={(checked) =>
                  toggleFeature("embedded_dashboard", checked)
                }
              />
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default TenantDetail;
