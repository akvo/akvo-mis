import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Col,
  Input,
  Modal,
  Row,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { Breadcrumbs, DescriptionPanel } from "../../../components";
import { api, store, uiText } from "../../../lib";
import { useNotification } from "../../../util/hooks";
import { fetchLevels } from "../../../util/level";

const { Text } = Typography;

// A tenant's hierarchy depth is append-only: a tier can be renamed at any
// time, but adding and removing are frozen once administrative units exist
// below the top level, because changing the depth then would strand them.
// The server enforces all of this; the disabled controls here are a hint,
// so every rejection is still surfaced from the response.
const Levels = () => {
  const [dataset, setDataset] = useState([]);
  const [loading, setLoading] = useState(true);
  const [frozen, setFrozen] = useState(false);
  const [saving, setSaving] = useState(false);
  // Adding appends a draft row to the table rather than opening a separate
  // form, so the new tier is seen in the position it will occupy.
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  // Rename happens inline: the edited row's name cell becomes an input.
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState("");

  const language = store.useState((s) => s.language);
  const { active: activeLang } = language;
  const { notify } = useNotification();

  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const pagePath = [
    {
      title: text.controlCenter,
      link: "/control-center",
    },
    {
      title: text.manageLevels,
    },
  ];

  const rejected = useCallback(
    (error) => {
      notify({
        type: "error",
        message: error?.response?.data?.message || text.errorSomething,
      });
    },
    [notify, text.errorSomething]
  );

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("levels-management");
      setDataset(data);
      // The same count the server's freeze gate uses: anything beyond the
      // single root unit means the hierarchy is populated.
      const { data: units } = await api.get("administrations?page=1");
      setFrozen(units?.total > 1);
    } catch (error) {
      rejected(error);
    } finally {
      setLoading(false);
    }
  }, [rejected]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Every mutation shares one shell: run it, then refresh both this table
  // and the levels store — dependent screens read the hierarchy's shape
  // from there — and surface whatever the server rejected.
  const mutate = useCallback(
    async (call) => {
      setSaving(true);
      try {
        await call();
        await fetchData();
        await fetchLevels();
      } catch (error) {
        rejected(error);
      } finally {
        setSaving(false);
      }
    },
    [fetchData, rejected]
  );

  // Both handlers trim before sending and refuse a blank result. DRF trims
  // too and would answer 400, so this is not the validation — it just keeps
  // a name of spaces from costing a round-trip and a generic error toast.
  // The `saving` guard is what the buttons already get for free from antd,
  // which swallows clicks while `loading`; Enter has no such protection, and
  // two of them in quick succession is a real double-submit.
  const handleOnAdd = () => {
    const name = newName.trim();
    if (!name || saving) {
      return;
    }
    mutate(async () => {
      await api.post("levels-management", { name });
      setNewName("");
      setAdding(false);
    });
  };

  const handleOnRename = (record) => {
    const name = editingName.trim();
    if (!name || saving) {
      return;
    }
    mutate(async () => {
      await api.put(`levels-management/${record.id}`, { name });
      setEditingId(null);
    });
  };

  const handleOnDelete = (record) => {
    Modal.confirm({
      title: text.levelDeleteTitle,
      content: record.name,
      centered: true,
      okText: text.deleteText,
      cancelText: text.cancelButton,
      onOk: () => mutate(() => api.delete(`levels-management/${record.id}`)),
    });
  };

  const deepest = dataset[dataset.length - 1];
  const nextLevel = dataset.length ? deepest.level + 1 : 0;
  // The draft row is a table row like any other, distinguished by id: -1.
  const rows = adding
    ? [...dataset, { id: -1, level: nextLevel, name: "" }]
    : dataset;

  // Why delete is unavailable, in the same words the server would use.
  const deleteReason = (record) => {
    if (frozen) {
      return "Frozen — units exist below root";
    }
    if (record.level === 0) {
      return "The top level cannot be removed";
    }
    return "Only the deepest tier can be removed";
  };

  const columns = [
    {
      title: "Depth",
      dataIndex: "level",
      width: "20%",
      render: (level, record) => (
        <>
          <Tag color={level === 0 ? "blue" : "default"}>Level {level}</Tag>
          {level === 0 && <Text type="secondary">top</Text>}
          {record.id === -1 && <Text type="secondary">new</Text>}
        </>
      ),
    },
    {
      title: "Name",
      dataIndex: "name",
      render: (name, record) => {
        if (record.id === -1) {
          return (
            <Input
              autoFocus
              value={newName}
              placeholder="e.g. Province, District, Ward"
              style={{ maxWidth: 280 }}
              onChange={(e) => {
                setNewName(e.target.value);
              }}
              onPressEnter={handleOnAdd}
            />
          );
        }
        if (record.id !== editingId) {
          return name || <Text type="secondary">(unnamed)</Text>;
        }
        return (
          <Input
            value={editingName}
            style={{ maxWidth: 280 }}
            onChange={(e) => {
              setEditingName(e.target.value);
            }}
            onPressEnter={() => handleOnRename(record)}
          />
        );
      },
    },
    {
      title: "Actions",
      dataIndex: "id",
      width: "25%",
      align: "right",
      render: (_, record) => {
        if (record.id === -1) {
          return (
            <>
              <Button
                size="small"
                type="primary"
                loading={saving}
                disabled={!newName.trim()}
                onClick={handleOnAdd}
              >
                {text.saveButton}
              </Button>{" "}
              <Button
                size="small"
                onClick={() => {
                  setAdding(false);
                  setNewName("");
                }}
              >
                {text.cancelButton}
              </Button>
            </>
          );
        }
        if (record.id === editingId) {
          return (
            <>
              <Button
                size="small"
                type="primary"
                loading={saving}
                disabled={!editingName.trim()}
                onClick={() => handleOnRename(record)}
              >
                {text.saveButton}
              </Button>{" "}
              <Button
                size="small"
                onClick={() => {
                  setEditingId(null);
                }}
              >
                {text.cancelButton}
              </Button>
            </>
          );
        }
        const canDelete =
          record.id === deepest?.id && record.level !== 0 && !frozen;
        return (
          <>
            <Button
              size="small"
              onClick={() => {
                setEditingId(record.id);
                setEditingName(record.name);
              }}
            >
              Rename
            </Button>{" "}
            {/* Tooltip rather than a title attribute: a title becomes the
                button's accessible name, so screen readers would announce
                the reason instead of "Delete". The span gives the tooltip
                something to hang on, since a disabled button fires no
                mouse events. */}
            <Tooltip
              title={canDelete ? "Remove this tier" : deleteReason(record)}
            >
              <span>
                <Button
                  size="small"
                  danger
                  disabled={!canDelete}
                  onClick={() => handleOnDelete(record)}
                >
                  {text.deleteText}
                </Button>
              </span>
            </Tooltip>
          </>
        );
      },
    },
  ];

  return (
    <div id="masterDataLevels">
      <div className="description-container">
        <Row justify="space-between" align="bottom">
          <Col>
            <Breadcrumbs pagePath={pagePath} />
            <DescriptionPanel
              description={text.manageLevelText}
              title={text.manageLevels}
            />
          </Col>
        </Row>
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <Row
            justify="space-between"
            align="middle"
            style={{ marginBottom: "1rem" }}
          >
            <Col>
              <div style={{ fontWeight: 600, fontSize: 16 }}>
                Administration levels
              </div>
              <Text type="secondary">
                Define the tiers of your hierarchy, deepest last.
              </Text>
            </Col>
            <Col>
              <Tooltip
                title={
                  frozen ? "Frozen — units exist below root" : "Append a tier"
                }
              >
                <span>
                  <Button
                    type="primary"
                    shape="round"
                    icon={<PlusOutlined />}
                    disabled={frozen || adding}
                    onClick={() => {
                      setAdding(true);
                    }}
                  >
                    {text.addLevel}
                  </Button>
                </span>
              </Tooltip>
            </Col>
          </Row>
          {frozen && (
            <Alert
              type="warning"
              showIcon
              message={text.levelFrozenHint}
              style={{ marginBottom: "1rem" }}
            />
          )}
          <div style={{ minHeight: "40vh" }}>
            <Table
              columns={columns}
              dataSource={rows}
              loading={loading}
              rowClassName="editable-row"
              rowKey="id"
              pagination={false}
            />
          </div>
          <Alert
            type="info"
            style={{ marginTop: "1rem" }}
            message="Add always appends the next tier down · delete removes only the deepest tier · rename is allowed at any time · once administrative units exist below your root, add and delete are frozen."
          />
        </div>
      </div>
    </div>
  );
};

export default Levels;
