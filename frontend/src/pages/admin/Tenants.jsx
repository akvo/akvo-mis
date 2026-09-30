import React, { useEffect, useMemo, useState } from "react";
import { Table, Input, Space, Tag, Radio, Button } from "antd";
import { Link } from "react-router-dom";
import { api, store, uiText } from "../../lib";
import { useNotification } from "../../util/hooks";
import useInspect from "./useInspect";

const { Search } = Input;

const COUNTS = ["users", "forms", "dashboards", "datapoints", "devices"];

const Tenants = () => {
  const { notify } = useNotification();
  const [loading, setLoading] = useState(true);
  const [dataset, setDataset] = useState([]);
  const [search, setSearch] = useState("");
  const [state, setState] = useState("all");
  const { inspect, inspecting } = useInspect();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const stateLabel = (value) =>
    ({
      active: text.consoleStateActive,
      suspended: text.consoleStateSuspended,
      deleted: text.consoleStateDeleted,
    }[value] || value);

  useEffect(() => {
    api
      .get("admin/tenants/summary")
      .then((res) => setDataset(res.data))
      .catch(() => notify({ type: "error", message: text.consoleTenants }))
      .finally(() => setLoading(false));
  }, [notify, text]);

  // Filtered here rather than at the endpoint: the summary is one
  // request for every workspace, so narrowing it is a client concern
  // and a keystroke costs nothing.
  const rows = useMemo(
    () =>
      dataset.filter((row) => {
        const matchesState = state === "all" || row.state === state;
        const needle = search.trim().toLowerCase();
        const matchesSearch =
          !needle ||
          row.subdomain.toLowerCase().includes(needle) ||
          (row.name || "").toLowerCase().includes(needle);
        return matchesState && matchesSearch;
      }),
    [dataset, search, state]
  );

  const columns = [
    {
      title: "Workspace",
      dataIndex: "subdomain",
      key: "subdomain",
      render: (subdomain, row) => (
        <>
          <Link to={`/admin/tenants/${row.id}`}>{subdomain}</Link>
          <div className="admin-subtle">{row.name}</div>
        </>
      ),
    },
    {
      title: "Status",
      dataIndex: "state",
      key: "state",
      render: (value) => (
        <Tag color={{ active: "green", suspended: "orange" }[value]}>
          {stateLabel(value)}
        </Tag>
      ),
    },
    ...COUNTS.map((key) => ({
      title: key[0].toUpperCase() + key.slice(1),
      dataIndex: key,
      key,
      align: "right",
      render: (value) => (value ?? 0).toLocaleString("en-US"),
    })),
    {
      title: "",
      key: "inspect",
      align: "right",
      render: (_, row) =>
        // Only an active workspace resolves; inspecting a suspended or
        // deleted one would open a 404, so the label renders without a
        // link rather than offering a dead one.
        row.state === "active" ? (
          <Button
            type="link"
            size="small"
            loading={inspecting === row.id}
            onClick={() => inspect(row)}
          >
            {text.consoleInspect}
          </Button>
        ) : (
          <span className="admin-disabled">{text.consoleInspect}</span>
        ),
    },
  ];

  return (
    <div>
      <Space
        style={{ width: "100%", justifyContent: "space-between" }}
        align="end"
      >
        <h1>{text.consoleTenants}</h1>
        <Space>
          <Search
            placeholder={text.consoleSearchTenants}
            allowClear
            onChange={(event) => setSearch(event.target.value)}
            style={{ width: 260 }}
          />
          <Radio.Group
            value={state}
            onChange={(event) => setState(event.target.value)}
          >
            <Radio.Button value="all">{text.consoleStateAll}</Radio.Button>
            <Radio.Button value="active">
              {text.consoleStateActive}
            </Radio.Button>
            <Radio.Button value="suspended">
              {text.consoleStateSuspended}
            </Radio.Button>
            <Radio.Button value="deleted">
              {text.consoleStateDeleted}
            </Radio.Button>
          </Radio.Group>
        </Space>
      </Space>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        pagination={false}
      />
    </div>
  );
};

export default Tenants;
