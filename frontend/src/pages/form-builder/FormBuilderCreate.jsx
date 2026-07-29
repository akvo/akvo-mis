import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import WebformEditor from "akvo-react-form-editor";
import "akvo-react-form-editor/dist/index.css";
import { Breadcrumbs } from "../../components";
import {
  api,
  store,
  uiText,
  buildAdministrationCascade,
  QUESTION_TYPES,
  REGISTRATION_FORM,
  MONITORING_FORM,
} from "../../lib";
import { useNotification } from "../../util/hooks";
import { FormEditorBanners } from "./components";
import "./style.scss";

const FormBuilderCreate = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const parentId = searchParams.get("parent_id");
  const { notify } = useNotification();
  const [saving, setSaving] = useState(false);
  const [parentForm, setParentForm] = useState(null);
  const [parentError, setParentError] = useState(false);

  const { language, user: authUser } = store.useState((s) => s);
  // The cascade is authenticated now and starts at this tenant's own
  // root administration, which the profile resolves.
  const cascadeURL = useMemo(
    () => buildAdministrationCascade(api.token, authUser?.administration?.id),
    [authUser]
  );
  const { active: activeLang } = language;
  const text = useMemo(() => uiText[activeLang], [activeLang]);

  const loadParentForm = useCallback(() => {
    if (!parentId) {
      return;
    }
    api
      .get(`/manage/forms/${parentId}`)
      .then((res) => {
        if (
          res.data.status !== "published" ||
          res.data.type !== REGISTRATION_FORM
        ) {
          setParentError(true);
        } else {
          setParentForm(res.data);
        }
      })
      .catch(() => setParentError(true));
  }, [parentId]);

  useEffect(() => {
    loadParentForm();
  }, [loadParentForm]);

  const pagePath = [
    { title: text.controlCenter, link: "/control-center" },
    {
      title: text.menuFormBuilder,
      link: "/control-center/form-builder",
    },
    { title: text.formBuilderCreateTitle },
  ];

  const onSave = (editorOutput) => {
    setSaving(true);
    const payload = parentId
      ? { ...editorOutput, type: MONITORING_FORM, parent: Number(parentId) }
      : editorOutput;
    api
      .post("/manage/forms", payload)
      .then((res) => {
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

  return (
    <div id="form-builder-create">
      <div className="description-container">
        <Breadcrumbs pagePath={pagePath} />
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <FormEditorBanners
            infoBannerText={
              parentForm ? text.formBuilderMonitoringFor(parentForm.name) : null
            }
            errorBannerText={
              parentError ? text.formBuilderParentFormError : null
            }
            text={text}
          />
          <div style={{ marginTop: 16 }}>
            <WebformEditor
              initialValue={{}}
              onSave={saving || parentError ? null : onSave}
              limitQuestionType={Object.keys(QUESTION_TYPES)}
              settingCascadeURL={cascadeURL}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default FormBuilderCreate;
