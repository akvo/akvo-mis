import React from "react";
import { Alert, Button, Space } from "antd";

const FormEditorBanners = ({
  draftRestored,
  onDismissDraft,
  onResetDraft,
  previewingVersion,
  onExitPreview,
  infoBannerText,
  errorBannerText,
  text,
  topSpacing,
}) => {
  const draftStyle = topSpacing
    ? { marginTop: 16, marginBottom: 8 }
    : { marginBottom: 8 };

  return (
    <>
      {draftRestored && (
        <Alert
          type="info"
          message={text.formBuilderDraftRestored}
          action={
            onResetDraft && (
              <Space>
                <Button size="small" onClick={onResetDraft}>
                  {text.formBuilderResetDraft}
                </Button>
              </Space>
            )
          }
          closable
          style={draftStyle}
          onClose={onDismissDraft}
        />
      )}
      {previewingVersion && (
        <Alert
          type="warning"
          message={text.formBuilderPreviewingBanner(previewingVersion.version)}
          action={
            <Button size="small" onClick={onExitPreview}>
              {text.formBuilderBackToSaved}
            </Button>
          }
          style={{ marginBottom: 8 }}
          showIcon
        />
      )}
      {infoBannerText && (
        <Alert
          type="info"
          message={infoBannerText}
          style={{ marginBottom: 8 }}
          showIcon
        />
      )}
      {errorBannerText && (
        <Alert
          type="error"
          message={errorBannerText}
          style={{ marginBottom: 8 }}
          showIcon
        />
      )}
    </>
  );
};

export default FormEditorBanners;
