import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Table, Input, Space, Tag, Radio, Button, Card, Row, Col } from "antd";
import { Link } from "react-router-dom";
import debounce from "lodash.debounce";
import { api, store, uiText } from "../../lib";
import { useNotification } from "../../util/hooks";
import useInspect from "./useInspect";

const { Search } = Input;

const COUNTS = ["users", "forms", "dashboards", "datapoints", "devices"];

// Workspaces first, then the five counts in the order the columns
// run. The workspace count is not in `summary` -- it is the
// envelope's `total`, which the pager reads too, so one number has
// one source.
const TILES = [
  ["workspaces", "consoleTotalWorkspaces"],
  ["users", "consoleTotalUsers"],
  ["forms", "consoleTotalForms"],
  ["dashboards", "consoleTotalDashboards"],
  ["datapoints", "consoleTotalDatapoints"],
  ["devices", "consoleTotalDevices"],
];
const PAGE_SIZE = 25;
const DEFAULT_ORDER = "subdomain";

// Sorting is the server's. With paging server-side, antd's own sorter
// would reorder the 25 rows in hand and present the result as a ranking
// of the whole deployment.
const orderParam = (sorter) => {
  if (!sorter || !sorter.order) {
    return DEFAULT_ORDER;
  }
  return sorter.order === "descend" ? `-${sorter.columnKey}` : sorter.columnKey;
};

const Tenants = () => {
  const { notify } = useNotification();
  const [loading, setLoading] = useState(true);
  const [dataset, setDataset] = useState([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [state, setState] = useState("all");
  const [ordering, setOrdering] = useState(DEFAULT_ORDER);
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
    const params = new URLSearchParams({ page, ordering });
    if (search) {
      params.set("search", search);
    }
    if (state !== "all") {
      params.set("state", state);
    }
    setLoading(true);
    // The third argument is a cancel key: a new request on the same key
    // aborts the one in flight. Debouncing the search box is not enough
    // on its own -- the state buttons and the sort headers fire
    // immediately, and two of those in quick succession are two
    // requests with nothing making the first one lose. If it lands
    // second, the rows and the totals describe the filter the operator
    // just moved away from.
    api
      .get(`admin/tenants/summary?${params.toString()}`, {}, "tenants")
      .then((res) => {
        setDataset(res.data.data);
        setTotal(res.data.total);
        setSummary(res.data.summary);
        setLoading(false);
      })
      .catch((error) => {
        // Both early returns leave `loading` set, deliberately. A newer
        // request is already in flight and owns it. Clearing it here --
        // which a `.finally` would do, since it runs for an abandoned
        // request too -- un-blanks the tiles onto the previous filter's
        // numbers and leaves them there until the newer request lands.
        // The operator would see the new filter selected, no spinner,
        // and the old totals: wrong in exactly the way they would
        // believe.

        // An abandoned request is not a failure. This component asked
        // for it and then changed its mind.
        if (api.isCancel(error)) {
          return;
        }
        // A workspace deleted between two requests can shrink the
        // result out from under the page an operator is standing on,
        // and the endpoint answers 404. Going back to the first page is
        // the right response to a page that merely stopped existing;
        // an error banner is not. The re-run owns `loading` from here.
        if (error?.response?.status === 404 && page !== 1) {
          setPage(1);
          return;
        }
        notify({ type: "error", message: text.consoleTenants });
        setLoading(false);
      });
  }, [page, search, state, ordering, notify, text]);

  // Debounced because the filter is no longer local: per-keystroke was
  // free over an array in memory and is a request per character now.
  const applySearch = useMemo(
    () =>
      debounce((value) => {
        setSearch(value.trim());
        setPage(1);
      }, 400),
    []
  );

  useEffect(() => () => applySearch.cancel(), [applySearch]);

  // antd fires one onChange for paging and for sorting alike. A changed
  // sort resets to the first page; otherwise the pager's own page wins.
  const handleChange = useCallback(
    (pagination, filters, sorter) => {
      const next = orderParam(sorter);
      if (next !== ordering) {
        setOrdering(next);
        setPage(1);
        return;
      }
      setPage(pagination.current);
    },
    [ordering]
  );

  // Drives the header caret from the order the server was asked for,
  // rather than letting the table remember an order of its own.
  const sortOrderFor = (key) => {
    if (ordering === key) {
      return "ascend";
    }
    if (ordering === `-${key}`) {
      return "descend";
    }
    return null;
  };

  const columns = [
    {
      title: "Workspace",
      dataIndex: "subdomain",
      key: "subdomain",
      sorter: true,
      sortOrder: sortOrderFor("subdomain"),
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
      // Not sortable: the segmented filter above the table already
      // answers "show me the suspended ones", and answers it better.
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
      sorter: true,
      sortOrder: sortOrderFor(key),
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
            onChange={(event) => applySearch(event.target.value)}
            style={{ width: 260 }}
          />
          <Radio.Group
            value={state}
            onChange={(event) => {
              setState(event.target.value);
              setPage(1);
            }}
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
      <Row
        gutter={14}
        // Symmetric with the top margin. The tiles are a band
        // between the filters and the table, not a header welded
        // to either of them.
        style={{ marginTop: 16, marginBottom: 16 }}
        id="tenant-totals"
      >
        {TILES.map(([key, label]) => (
          <Col span={4} key={key}>
            <Card size="small">
              <div className="admin-subtle">{text[label]}</div>
              <div className="admin-tile-value">
                {loading ? (
                  <span className="admin-tile-pending" />
                ) : (
                  // Both halves coalesce. A response without the key
                  // is not something the endpoint sends, but the
                  // alternative to a zero here is `undefined.
                  // toLocaleString()`, which white-screens the whole
                  // console over a tile.
                  (key === "workspaces"
                    ? total ?? 0
                    : summary?.[key] ?? 0
                  ).toLocaleString("en-US")
                )}
              </div>
            </Card>
          </Col>
        ))}
      </Row>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={dataset}
        loading={loading}
        summary={() =>
          // The same object the tiles read. Rendering five numbers
          // twice is only a risk if there are two sources; there is
          // one, so they cannot disagree. The label cell says "Total"
          // rather than restating the workspace count, which the tile
          // above already carries.
          summary ? (
            <Table.Summary>
              <Table.Summary.Row>
                <Table.Summary.Cell index={0}>
                  {text.consoleTotalsRow}
                </Table.Summary.Cell>
                <Table.Summary.Cell index={1} />
                {COUNTS.map((key, position) => (
                  <Table.Summary.Cell
                    key={key}
                    index={2 + position}
                    align="right"
                  >
                    {(summary[key] ?? 0).toLocaleString("en-US")}
                  </Table.Summary.Cell>
                ))}
                <Table.Summary.Cell index={7} />
              </Table.Summary.Row>
            </Table.Summary>
          ) : null
        }
        onChange={handleChange}
        pagination={{
          current: page,
          total,
          pageSize: PAGE_SIZE,
          showSizeChanger: false,
          // Left on deliberately. hideOnSinglePage would take the
          // result line with it, and "9 of 9" is the answer to the
          // question the filter just asked.
          hideOnSinglePage: false,
          showTotal: (count, range) =>
            (text.consoleResultCount || "")
              .replace("{from}", range[0])
              .replace("{to}", range[1])
              .replace("{total}", count),
        }}
      />
    </div>
  );
};

export default Tenants;
