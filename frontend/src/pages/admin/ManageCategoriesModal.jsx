import React, { useCallback, useEffect, useState } from "react";
import { Modal, Input, Button, List, Popconfirm, Space } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { api } from "../../lib";
import { useNotification } from "../../util/hooks";

const ManageCategoriesModal = ({ open, text, onClose }) => {
  const { notify } = useNotification();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [newName, setNewName] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api
      .get("/manage/form-categories")
      .then((res) => setCategories(res.data || []))
      .catch(() => setCategories([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (open) {
      load();
      setNewName("");
    }
  }, [open, load]);

  const onAdd = () => {
    const name = newName.trim();
    if (!name) {
      return;
    }
    setAdding(true);
    api
      .post("/manage/form-categories", { name })
      .then(() => {
        setNewName("");
        load();
      })
      .catch((err) => {
        notify({
          type: "error",
          message: err?.response?.data?.message || text.consoleFLCategoryError,
        });
      })
      .finally(() => setAdding(false));
  };

  const onDelete = (id) => {
    api
      .delete(`/manage/form-categories/${id}`)
      .then(load)
      .catch((err) => {
        notify({
          type: "error",
          message: err?.response?.data?.message || text.consoleFLCategoryError,
        });
      });
  };

  return (
    <Modal
      open={open}
      title={text.consoleFLManageCategories}
      footer={[
        <Button key="close" onClick={onClose}>
          {text.closeButton || "Close"}
        </Button>,
      ]}
      onCancel={onClose}
    >
      <Space.Compact style={{ width: "100%", marginBottom: 16 }}>
        <Input
          value={newName}
          placeholder={text.consoleFLCategoryPlaceholder}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={onAdd}
        />
        <Button
          type="primary"
          icon={<PlusOutlined />}
          loading={adding}
          onClick={onAdd}
        >
          {text.consoleFLCategoryAdd}
        </Button>
      </Space.Compact>
      <List
        loading={loading}
        dataSource={categories}
        locale={{ emptyText: text.consoleFLCategoryEmpty }}
        renderItem={(c) => (
          <List.Item
            actions={[
              <Popconfirm
                key="del"
                title={text.consoleFLCategoryDeleteConfirm}
                okText={text.consoleFLDeleteButton}
                okButtonProps={{ danger: true }}
                onConfirm={() => onDelete(c.id)}
              >
                <Button type="link" danger size="small">
                  {text.consoleFLDeleteButton}
                </Button>
              </Popconfirm>,
            ]}
          >
            {c.name}
          </List.Item>
        )}
      />
    </Modal>
  );
};

export default ManageCategoriesModal;
