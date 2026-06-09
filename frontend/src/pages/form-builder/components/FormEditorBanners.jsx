import React from "react";
import { Alert, Button } from "antd";

const FormEditorBanners = ({
  previewingVersion,
  onExitPreview,
  infoBannerText,
  errorBannerText,
  text,
}) => {
  return (
    <>
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
