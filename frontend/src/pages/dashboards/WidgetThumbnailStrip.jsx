import React from "react";

const thumbHeight = (type) => {
  if (type === "text" || type === "section_title") {
    return 7;
  }
  if (type === "kpi") {
    return 20;
  }
  if (type === "table") {
    return 34;
  }
  if (type === "map") {
    return 40;
  }
  return 28;
};

const thumbBg = (widget) => {
  const { type, color } = widget;
  if (type === "text" || type === "section_title") {
    return "#dfe3e9";
  }
  if (type === "table") {
    return "#e3e8ef";
  }
  if (type === "map") {
    return "#d7e2da";
  }
  return (color || "#1890ff") + "38";
};

const GAP = 5;

const WidgetThumbnailStrip = ({ widgets }) => {
  const items = (widgets || []).slice(0, 8);
  if (items.length === 0) {
    return null;
  }
  return (
    <>
      {items.map((w, i) => (
        <div
          key={i}
          style={{
            flexBasis: `calc(${(w.col_span / 24) * 100}% - ${GAP}px)`,
            height: thumbHeight(w.type) + "px",
            borderRadius: 3,
            background: thumbBg(w),
          }}
        />
      ))}
    </>
  );
};

export default WidgetThumbnailStrip;
