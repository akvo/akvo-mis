import React from "react";
import { Tag } from "antd";

const FormStatusTag = ({ status, text }) => {
  const tagMap = {
    published: { color: "green", label: text.formBuilderStatusPublished },
    archived: { color: "red", label: text.formBuilderStatusArchived },
    draft: { color: "default", label: text.formBuilderStatusDraft },
  };
  const tag = tagMap[status] || tagMap.draft;
  return <Tag color={tag.color}>{tag.label}</Tag>;
};

export default FormStatusTag;
