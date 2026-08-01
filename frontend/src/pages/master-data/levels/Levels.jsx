import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Button, Col, Divider, Input, Modal, Row, Table } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { Breadcrumbs, DescriptionPanel } from "../../../components";
import { api, store, uiText } from "../../../lib";
import { useNotification } from "../../../util/hooks";
import { fetchLevels } from "../../../util/level";

// A tenant's hierarchy depth is append-only: a tier can be renamed at any
// time, but adding and removing are frozen once administrative units exist
// below the top level, because changing the depth then would strand them.
// The server enforces all of this; the disabled controls here are a hint,
// so every rejection is still surfaced from the response.
const Levels = () => {
  const [dataset, setDataset] = useState([]);
  const [loading, setLoading] = useState(true);
  const [frozen, setFrozen] = useState(false);
  const [newName, setNewName] = useState("");
  const [saving, setSaving] = useState(false);
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

  const columns = [
    {
      title: text.levelLabel,
      dataIndex: "level",
      width: "10%",
    },
    {
      title: text.nameLabel,
      dataIndex: "name",
      render: (name, record) => {
        if (record.id !== editingId) {
          return name;
        }
        return (
          <Input
            value={editingName}
            onChange={(e) => {
              setEditingName(e.target.value);
            }}
            onPressEnter={() => handleOnRename(record)}
          />
        );
      },
    },
    {
      title: "Action",
      dataIndex: "id",
      width: "25%",
      render: (_, record) => {
        if (record.id === editingId) {
          return (
            <>
              <Button
                shape="round"
                type="primary"
                loading={saving}
                disabled={!editingName.trim()}
                onClick={() => handleOnRename(record)}
              >
                {text.saveButton}
              </Button>
              <Button
                shape="round"
                type="link"
                onClick={() => {
                  setEditingId(null);
                }}
              >
                {text.cancelButton}
              </Button>
            </>
          );
        }
        return (
          <>
            <Button
              shape="round"
              type="primary"
              onClick={() => {
                setEditingId(record.id);
                setEditingName(record.name);
              }}
            >
              {text.editButton}
            </Button>
            {record.id === deepest?.id && (
              <Button
                shape="round"
                type="link"
                danger
                disabled={frozen}
                onClick={() => handleOnDelete(record)}
              >
                {text.deleteText}
              </Button>
            )}
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
          {frozen && (
            <Alert
              type="info"
              showIcon
              message={text.levelFrozenHint}
              style={{ marginBottom: "1rem" }}
            />
          )}
          <Row justify="space-between" align="middle" gutter={[16, 16]}>
            <Col span={12}>
              <Input
                value={newName}
                onChange={(e) => {
                  setNewName(e.target.value);
                }}
                onPressEnter={handleOnAdd}
                placeholder={text.newLevelName}
                disabled={frozen}
                style={{ maxWidth: 260 }}
              />
            </Col>
            <Col>
              <Button
                type="primary"
                shape="round"
                icon={<PlusOutlined />}
                onClick={handleOnAdd}
                loading={saving}
                disabled={frozen || !newName.trim()}
              >
                {text.addLevel}
              </Button>
            </Col>
          </Row>
          <Divider />
          <div style={{ minHeight: "40vh" }}>
            <Table
              columns={columns}
              dataSource={dataset}
              loading={loading}
              rowClassName="editable-row"
              rowKey="id"
              pagination={false}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Levels;
