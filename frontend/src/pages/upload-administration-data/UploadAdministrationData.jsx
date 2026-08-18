import React, { useState, useEffect, useMemo, useRef } from "react";
import "./style.scss";
import { Link } from "react-router-dom";
import {
  Row,
  Col,
  Card,
  Divider,
  Button,
  Space,
  Upload,
  Result,
  Alert,
} from "antd";
import { FileTextFilled } from "@ant-design/icons";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { useNavigate } from "react-router-dom";
import { api, store, uiText } from "../../lib";
import { useNotification } from "../../util/hooks";
import { snakeCase } from "lodash";
import moment from "moment";

const allowedFiles = [
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
];
const { Dragger } = Upload;

// How often to ask the backend whether the import has finished. The job
// is usually quick; the first check happens immediately and this only
// governs the ones after it.
const POLL_INTERVAL = 3000;

const UploadAdministrationData = () => {
  const { user } = store.useState((state) => state);
  const levels = store.useState((s) => s.levels);
  const [fileName, setFileName] = useState(null);
  const [uploading, setUploading] = useState(false);
  // One of null / "done" / "failed" — the job's own vocabulary. Two
  // booleans could encode a fourth state that means nothing.
  const [outcome, setOutcome] = useState(null);
  const { notify } = useNotification();
  const navigate = useNavigate();
  const { active: activeLang } = store.useState((s) => s.language);

  // The same predicate the backend enforces, read from the levels the
  // app already holds rather than from a new endpoint. The backend
  // check is the authoritative one — this only saves the operator
  // picking a file to be told no.
  const uploadReady = useMemo(() => {
    const rows = levels || [];
    return (
      rows.some((l) => l.level === 0 && (l.name || "").trim()) &&
      rows.some((l) => l.level >= 1)
    );
  }, [levels]);

  const text = useMemo(() => {
    return uiText?.[activeLang] || uiText.en;
  }, [activeLang]);

  const pagePath = [
    {
      title: text.controlCenter,
      link: "/control-center",
    },
    {
      title: text.manageAdministrativeList,
      link: "/control-center/master-data/administration",
    },
    {
      title: text.AdministrationDataUpload,
    },
  ];

  useEffect(() => {
    if (user) {
      const date = moment().format("YYYYMMDD");
      setFileName([date, snakeCase(user.name)].join("-"));
    }
  }, [user]);

  // Held in a ref rather than state: nothing renders from it, and the
  // cleanup below has to see the current handle, not the one captured
  // when the effect was first set up.
  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  // Leaving the page mid-import must not leave an interval behind
  // calling setState on an unmounted component.
  useEffect(() => stopPolling, []);

  const startPolling = (taskId) => {
    const check = () =>
      api
        .get(`download/status/${taskId}`)
        .then((res) => {
          const jobStatus = res?.data?.status;
          if (jobStatus !== "done" && jobStatus !== "failed") {
            return;
          }
          stopPolling();
          setUploading(false);
          if (jobStatus === "done") {
            notify({ type: "success", message: text.fileUploadSuccess });
          }
          setOutcome(jobStatus);
        })
        .catch(() => {
          // A single failed poll says nothing about the import — the
          // next one will ask again.
        });

    stopPolling();
    // Ask once straight away: most imports finish before the first
    // interval would elapse, and waiting would show a spinner for a job
    // that is already done.
    check();
    pollRef.current = setInterval(check, POLL_INTERVAL);
  };

  const onChange = (info) => {
    // Only the error branch remains. A finished *upload* used to be
    // reported as a finished *import*, which it never was: the response
    // means the file was received, and the rows are read minutes later
    // by a worker.
    if (info.file?.status === "error") {
      notify({
        type: "error",
        message: text.fileUploadFail,
      });
      setUploading(false);
    }
  };

  const uploadRequest = ({ file, onSuccess }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("is_update", false);
    setUploading(true);
    setOutcome(null);
    api
      .post(`upload/bulk-administrations`, formData)
      .then((res) => {
        onSuccess(res.data);
        startPolling(res.data?.task_id);
      })
      .catch(() => {
        notify({
          type: "error",
          message: text.fileUploadFail,
        });
        setUploading(false);
      });
  };

  const props = {
    name: fileName,
    multiple: false,
    maxCount: 1,
    showUploadList: false,
    accept: allowedFiles.join(","),
    disabled: !fileName || uploading || !uploadReady,
    onChange: onChange,
    customRequest: uploadRequest,
  };

  return (
    <div id="uploadMasterData">
      <div className="description-container">
        <Row justify="space-between">
          <Col>
            <Breadcrumbs pagePath={pagePath} />
            <DescriptionPanel
              description={text.dataAdministrationUploadText}
              title={text.AdministrationDataUpload}
            />
          </Col>
        </Row>
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          {outcome === "done" && (
            <div
              style={{ padding: 0, minHeight: "40vh" }}
              bodystyle={{ padding: 0 }}
            >
              <Result
                status="success"
                title={text.administrationUploadSuccessTitle}
                extra={[
                  <Divider key="divider" />,
                  <Button
                    type="primary"
                    key="back-button"
                    onClick={() => setOutcome(null)}
                    shape="round"
                  >
                    {text.uploadAnotherFileLabel}
                  </Button>,
                  <Button
                    key="page"
                    onClick={() =>
                      navigate("/control-center/master-data/administration")
                    }
                    shape="round"
                  >
                    {text.backToAdmLabel}
                  </Button>,
                ]}
              />
            </div>
          )}
          {outcome === "failed" && (
            <div style={{ padding: 0, minHeight: "40vh" }}>
              <Result
                status="error"
                title={text.administrationUploadFailedTitle}
                subTitle={text.administrationUploadFailedHint}
                extra={[
                  <Divider key="divider" />,
                  <Button
                    type="primary"
                    key="back-button"
                    onClick={() => setOutcome(null)}
                    shape="round"
                  >
                    {text.uploadAnotherFileLabel}
                  </Button>,
                ]}
              />
            </div>
          )}
          {!outcome && (
            <>
              {!uploadReady && (
                <Alert
                  type="info"
                  showIcon
                  message={text.uploadNotReadyHint}
                  style={{ marginBottom: "1rem" }}
                />
              )}
              <Card
                style={{ padding: 0, minHeight: "40vh" }}
                bodystyle={{ padding: 0 }}
              >
                <Space direction="vertical">
                  <Space align="center" size={32}>
                    <img src="/assets/data-upload.svg" />
                    <p>{text.uploadMasterDataLabel}</p>
                  </Space>
                  <div className="upload-wrap">
                    <Dragger {...props}>
                      <p className="ant-upload-drag-icon">
                        <FileTextFilled style={{ color: "#707070" }} />
                      </p>
                      <p className="ant-upload-text">
                        {uploading ? text.uploading : text.dropFile}
                      </p>
                      <Button
                        shape="round"
                        loading={uploading}
                        disabled={!uploadReady}
                      >
                        {text.browseComputer}
                      </Button>
                    </Dragger>
                  </div>
                  <Space align="center" size={32}>
                    <img src="/assets/data-download.svg" />
                    <p>
                      {text.templateDownloadAdministrationHint}
                      {/* The export endpoint refuses the same case, so
                          the link would only lead to an error. */}
                      {uploadReady ? (
                        <Link to="/control-center/master-data/administration/download">
                          {text.downloadHere}
                        </Link>
                      ) : (
                        text.downloadHere
                      )}
                    </p>
                  </Space>
                </Space>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default React.memo(UploadAdministrationData);
