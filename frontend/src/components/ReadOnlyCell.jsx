import React, { useEffect, useState } from "react";
import { Row, Col, Image, Button } from "antd";
import {
  config,
  IMAGE_EXTENSIONS,
  QUESTION_TYPES,
  getAnswerDisplayValue,
  getLastAnswerDisplayValue,
} from "../lib";
import moment from "moment";
import PropTypes from "prop-types";

// A single answer can be multiple MB (e.g. a long text field). Rendering the
// whole string into the DOM freezes the tab, so we cap what we show.
// Collapsed view shows MAX_DISPLAY_CHARS; "Read more" expands up to
// EXPAND_LIMIT only — the cap is what keeps expand/collapse responsive, since
// the freeze is proportional to characters laid out, not to the toggle itself.
const MAX_DISPLAY_CHARS = 2000;
const EXPAND_LIMIT = 50000;

// Non-string (arrays/JSX/numbers) and short strings render as-is.
const ExpandableText = ({ display }) => {
  const [expanded, setExpanded] = useState(false);
  if (typeof display !== "string" || display.length <= MAX_DISPLAY_CHARS) {
    return display;
  }
  const overCap = display.length > EXPAND_LIMIT;
  const shown = expanded
    ? display.slice(0, EXPAND_LIMIT)
    : display.slice(0, MAX_DISPLAY_CHARS);
  return (
    <>
      {shown}
      {expanded && overCap
        ? `… (showing first ${EXPAND_LIMIT} of ${display.length} characters)`
        : "… "}
      <Button
        type="link"
        size="small"
        style={{ padding: 0, height: "auto" }}
        onClick={() => setExpanded((prev) => !prev)}
      >
        {expanded ? "Read less" : "Read more"}
      </Button>
    </>
  );
};

ExpandableText.propTypes = {
  display: PropTypes.any,
};

const ReadOnlyCell = ({ record, lastValue = false }) => {
  const [locationName, setLocationName] = useState(null);
  const [value, setValue] = useState(null);
  const [oldValue, setOldValue] = useState(null);

  const fileExtension =
    record?.type === QUESTION_TYPES.attachment ? value?.split(".").pop() : null;
  const isImageType =
    [QUESTION_TYPES.image, QUESTION_TYPES.signature].includes(record?.type) ||
    (fileExtension && IMAGE_EXTENSIONS.includes(fileExtension));

  useEffect(() => {
    if (
      record &&
      (record.newValue ||
        record.newValue === 0 ||
        record.value ||
        record.value === 0)
    ) {
      const newValue =
        record.newValue || record.newValue === 0
          ? record.newValue
          : record.value;

      setValue(
        record.type === QUESTION_TYPES.date
          ? moment(newValue).format("YYYY-MM-DD")
          : record.type === QUESTION_TYPES.geo
          ? newValue?.join(", ")
          : newValue
      );
      setOldValue(
        record?.lastValue && record.type === QUESTION_TYPES.date
          ? moment(record.lastValue).format("YYYY-MM-DD")
          : record.type === QUESTION_TYPES.geo
          ? record?.lastValue?.join(", ")
          : record.lastValue
      );
    }
  }, [record]);

  useEffect(() => {
    if (
      record &&
      record.type === QUESTION_TYPES.cascade &&
      !record?.api?.endpoint &&
      !locationName &&
      !lastValue
    ) {
      /**
       * TODO: Handle recognizing entity cascade clearly
       */
      if (typeof record.value === "string") {
        setLocationName(record.value);
      } else {
        if (record.value) {
          config.fn.administration(record.value, false).then((res) => {
            const locName = res;
            setLocationName(locName?.full_name);
          });
        } else {
          setLocationName(null);
        }
      }
    }
    if (
      record &&
      record.type === QUESTION_TYPES.cascade &&
      !record?.api?.endpoint &&
      !locationName &&
      lastValue
    ) {
      /**
       * TODO: Handle recognizing entity cascade clearly
       */
      if (typeof record.lastValue === "string") {
        setLocationName(record.lastValue);
      } else {
        if (record.lastValue) {
          config.fn.administration(record.lastValue, false).then((res) => {
            const locName = res;
            setLocationName(locName?.full_name);
          });
        } else {
          setLocationName("-");
        }
      }
    }
  }, [record, locationName, lastValue]);

  const handleAttachmentClick = () => {
    // if type attachment, open file in new tab
    if (record.type === QUESTION_TYPES.attachment && value && !isImageType) {
      window.open(value, "_blank");
    }
  };

  return (
    <Row>
      <Col
        flex={1}
        style={{
          minWidth: 0,
          overflowWrap: "anywhere",
          wordBreak: "break-word",
          cursor:
            record.type === QUESTION_TYPES.attachment && value && !isImageType
              ? "pointer"
              : "default",
        }}
        onClick={handleAttachmentClick}
      >
        <span className={lastValue ? null : "blue"}>
          {record.type === QUESTION_TYPES.cascade && !record?.api?.endpoint ? (
            locationName
          ) : isImageType && value && !lastValue ? (
            <Image src={value} width={100} />
          ) : isImageType && lastValue && oldValue ? (
            <Image src={oldValue} width={100} />
          ) : lastValue ? (
            <ExpandableText
              display={getLastAnswerDisplayValue(record, oldValue)}
            />
          ) : (
            <ExpandableText display={getAnswerDisplayValue(record, value)} />
          )}
        </span>
      </Col>
    </Row>
  );
};

ReadOnlyCell.propTypes = {
  record: PropTypes.shape({
    id: PropTypes.number.isRequired,
    type: PropTypes.string.isRequired,
    value: PropTypes.oneOfType([PropTypes.any, PropTypes.oneOf([null])]),
    option: PropTypes.array,
    newValue: PropTypes.any,
    lastValue: PropTypes.any,
  }),
  lastValue: PropTypes.bool,
};

export default React.memo(ReadOnlyCell);
