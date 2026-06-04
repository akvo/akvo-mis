import React, { useState, useRef, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Spin } from "antd";
import WebformEditor from "akvo-react-form-editor";
import "akvo-react-form-editor/dist/index.css";
import { Breadcrumbs } from "../../components";
import { api, store, uiText } from "../../lib";
import { editorToApi } from "../../lib/form-builder-transform";
import { useNotification } from "../../util/hooks";
import { FormEditorBanners } from "./components";
import "./style.scss";

const DRAFT_KEY = "form-builder-draft-new";

const FormBuilderCreate = () => {
  const navigate = useNavigate();
  const { notify } = useNotification();
  const [saving, setSaving] = useState(false);
  const [draftRestored, setDraftRestored] = useState(false);
  const [initialValue, setInitialValue] = useState(null);
  const draftTimerRef = useRef(null);

  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const pagePath = [
    { title: text.controlCenter, link: "/control-center" },
    {
      title: text.menuFormBuilder,
      link: "/control-center/form-builder",
    },
    { title: text.formBuilderCreateTitle },
  ];

  useEffect(() => {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (raw) {
      try {
        const draft = JSON.parse(raw);
        setInitialValue(draft.value);
        setDraftRestored(true);
      } catch (_e) {
        setInitialValue({});
      }
    } else {
      setInitialValue({});
    }
    return () => {
      if (draftTimerRef.current) {
        clearTimeout(draftTimerRef.current);
      }
    };
  }, []);

  const onResetDraft = () => {
    localStorage.removeItem(DRAFT_KEY);
    setDraftRestored(false);
    setInitialValue({});
  };

  const onSave = (editorOutput) => {
    if (draftTimerRef.current) {
      clearTimeout(draftTimerRef.current);
    }
    draftTimerRef.current = setTimeout(() => {
      localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({
          value: editorOutput,
          savedAt: new Date().toISOString(),
        })
      );
    }, 2000);

    setSaving(true);
    const payload = editorToApi(editorOutput);
    api
      .post("/manage/forms", payload)
      .then((res) => {
        localStorage.removeItem(DRAFT_KEY);
        notify({ type: "success", message: text.formBuilderCreateSuccess });
        navigate(`/control-center/form-builder/${res.data.id}/edit`);
      })
      .catch((err) => {
        const msg = err.response?.data?.message || text.formBuilderCreateError;
        notify({ type: "error", message: msg });
      })
      .finally(() => {
        setSaving(false);
      });
  };

  if (initialValue === null) {
    return (
      <div style={{ textAlign: "center", paddingTop: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div id="form-builder-create">
      <div className="description-container">
        <Breadcrumbs pagePath={pagePath} />
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <FormEditorBanners
            draftRestored={draftRestored}
            onDismissDraft={() => {
              setDraftRestored(false);
            }}
            onResetDraft={onResetDraft}
            text={text}
            topSpacing
          />
          <div style={{ marginTop: 16 }}>
            <WebformEditor
              initialValue={initialValue}
              onSave={saving ? null : onSave}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default FormBuilderCreate;
