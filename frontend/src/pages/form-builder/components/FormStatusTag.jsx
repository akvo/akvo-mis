import React from "react";
import { Tag } from "antd";

const FormStatusTag = ({ status, text }) => {
  const isPublished = status === "published";
  return (
    <Tag color={isPublished ? "green" : "default"}>
      {isPublished
        ? text.formBuilderStatusPublished
        : text.formBuilderStatusDraft}
    </Tag>
  );
};

export default FormStatusTag;
