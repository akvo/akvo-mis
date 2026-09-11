import React, { useState, useMemo, useCallback, useEffect } from "react";
import {
  Table,
  Checkbox,
  Button,
  Modal,
  Row,
  Col,
  Input,
  Divider,
  Space,
} from "antd";
import { FileTextFilled } from "@ant-design/icons";
import { api, store, uiText } from "../lib";
import { useNotification } from "../util/hooks";
import DocumentUploader from "./DocumentUploader";

const { TextArea } = Input;

const CreateBatchModal = ({
  onCancel,
  onSuccess,
  isOpen = false,
  selectedRows = [],
}) => {
  const [loading, setLoading] = useState(false);
  const [batchName, setBatchName] = useState("");
  const [comment, setComment] = useState("");
  const [fileList, setFileList] = useState([]);
  const [dataError, setDataError] = useState([]);
  const [dataset, setDataset] = useState([]);

  const selectedForm = store.useState((state) => state.selectedForm);
  const language = store.useState((s) => s.language);
  const { active: activeLang } = language;
  const { notify } = useNotification();

  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const sendBatch = () => {
    setLoading(true);

    // Always use FormData for consistency
    const formData = new FormData();
    formData.append("name", batchName);

    // Add data IDs as JSON string
    dataset.forEach((d, dx) => {
      if (d?.id) {
        formData.append(`data[${dx}]`, d.id);
      }
    });

    // Add comment if present
    if (comment.length) {
      formData.append("comment", comment);
    }

    // Append files if any exist
    if (fileList.length) {
      fileList.forEach((file, index) => {
        formData.append(`files[${index}]`, file.originFileObj);
      });
    }

    // Send with FormData and proper headers
    api
      .post("batch", formData)
      .then(() => {
        setBatchName("");
        setComment("");
        setFileList([]);
        if (typeof onSuccess === "function") {
          onSuccess();
        }
      })
      .catch((err) => {
        if (err.response?.status === 400 && err.response?.data?.detail?.data) {
          setDataError(err.response.data.detail.data);
        } else {
          notify({
            type: "error",
            message: text.notifyError,
          });
        }
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const handleOnCancel = () => {
    setDataError([]);
    setFileList([]);
    setBatchName("");
    setComment("");
    if (typeof onCancel === "function") {
      onCancel();
    }
  };

  const fetchDataBySelectedRows = useCallback(() => {
    if (!selectedRows || !selectedRows.length || !isOpen) {
      return;
    }
    // If selectedRows are provided, fetch data for those rows
    if (selectedRows.length) {
      const selectionIds = selectedRows
        .map((id) => `selection_ids=${id}`)
        .join("&");
      api
        .get(`/form-pending-data/${selectedForm}/?${selectionIds}`)
        .then(({ data }) => {
          setDataset(data || []);
        })
        .catch(() => {
          setDataset([]);
        });
    } else {
      setDataset([]);
    }
  }, [isOpen, selectedRows, selectedForm]);

  useEffect(() => {
    fetchDataBySelectedRows();
  }, [fetchDataBySelectedRows]);

  return (
    <Modal
      className="create-batch-modal"
      open={isOpen}
      onCancel={handleOnCancel}
      maskClosable={false}
      footer={
        <Row align="middle">
          <Col xs={8} align="left">
            <Checkbox checked={true} disabled={true} className="dev">
              {text.sendNewRequest}
            </Checkbox>
          </Col>
          <Col xs={16}>
            <Space>
              <Button className="light" shape="round" onClick={handleOnCancel}>
                {text.cancelButton}
              </Button>
              <Button
                type="primary"
                shape="round"
                onClick={sendBatch}
                disabled={!batchName?.trim()?.length}
                loading={loading}
              >
                {text.createNewBatch}
              </Button>
            </Space>
          </Col>
        </Row>
      }
    >
      <p>{text.batchHintText}</p>
      <p>
        <FileTextFilled style={{ color: "#666666", fontSize: 64 }} />
      </p>
      <p>{text.batchHintDesc}</p>
      <Table
        bordered
        size="small"
        dataSource={dataset}
        columns={[
          {
            title: "Dataset",
            dataIndex: "name",
            key: "name",
          },
          {
            title: "Date Uploaded",
            dataIndex: "created",
            key: "created",
            align: "right",
          },
        ]}
        pagination={false}
        scroll={{ y: 270 }}
        rowKey="id"
        style={{
          borderColor: dataError?.length ? "#ef7575" : "transparent",
          borderWidth: 1,
          borderStyle: "solid",
        }}
      />
      {dataError?.length > 0 && (
        <div style={{ color: "#ef7575", marginTop: 10 }}>
          <ul style={{ listStyleType: "none", paddingLeft: 0 }}>
            {dataError.map((error, index) => (
              <li key={index}>
                <i>{error}</i>
              </li>
            ))}
          </ul>
        </div>
      )}
      <Divider />
      <Row align="middle">
        <Col xs={24} align="left">
          <div className="batch-name-field">
            <label>{text.batchName}</label>
            <Input
              onChange={(e) => {
                // Ensure batch name is trimmed and not empty
                setBatchName(e.target.value);
              }}
              allowClear
              value={batchName || ""}
            />
          </div>
          <label>{text.submissionComment}</label>
          <TextArea
            rows={4}
            onChange={(e) => setComment(e.target.value)}
            value={comment}
          />
          <DocumentUploader
            setFileList={setFileList}
            fileList={fileList}
            multiple={true} // Allow multiple files
            name="files"
          />
        </Col>
      </Row>
    </Modal>
  );
};

export default CreateBatchModal;
