import React, { useEffect, useState } from "react";
import { Button, DatePicker, Input, Select, Row, Col, Image } from "antd";
import {
  config,
  IMAGE_EXTENSIONS,
  QUESTION_TYPES,
  getAnswerDisplayValue,
  getLastAnswerDisplayValue,
} from "../lib";
import { isEqual } from "lodash";
const { Option } = Select;
import { UndoOutlined, SaveOutlined } from "@ant-design/icons";
import moment from "moment";
import PropTypes from "prop-types";

const EditableCell = ({
  record,
  parentId,
  updateCell,
  resetCell,
  pendingData,
  disabled = false,
  readonly = false,
  isPublic = false,
  resetButton = {},
  lastValue = false,
}) => {
  const [editing, setEditing] = useState(false);
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

  const notEditable =
    [
      QUESTION_TYPES.cascade,
      QUESTION_TYPES.geo,
      QUESTION_TYPES.image,
      QUESTION_TYPES.attachment,
      QUESTION_TYPES.signature,
    ].includes(record?.type) || readonly;
  const edited =
    record &&
    (record.newValue || record.newValue === 0) &&
    !isEqual(record.value, record.newValue);

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

  const renderAnswerInput = () => {
    return record.type === QUESTION_TYPES.option ? (
      <Select
        style={{ width: "100%" }}
        value={value?.length ? value[0] : null}
        onChange={(e) => {
          setValue([e]);
        }}
        disabled={disabled}
      >
        {record.option.map((o) => (
          <Option key={o.id} value={o?.value} title={o?.label}>
            {o?.label}
          </Option>
        ))}
      </Select>
    ) : record.type === QUESTION_TYPES.multiple_option ? (
      <Select
        mode="multiple"
        style={{ width: "100%" }}
        value={value?.filter(Boolean)}
        onChange={(e) => {
          setValue(e);
        }}
        disabled={disabled}
      >
        {record.option.map((o) => (
          <Option key={o.id} value={o?.value} title={o?.label}>
            {o?.label}
          </Option>
        ))}
      </Select>
    ) : record.type === QUESTION_TYPES.date ? (
      <DatePicker
        size="small"
        value={moment(value)}
        format="YYYY-MM-DD"
        animation={false}
        onChange={(d, ds) => {
          if (d) {
            setValue(ds);
          }
        }}
        disabled={disabled}
      />
    ) : (
      <Input
        autoFocus
        type={record.type === QUESTION_TYPES.number ? "number" : "text"}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
        }}
        onPressEnter={() => {
          updateCell(record.id, parentId, value);
          setEditing(false);
        }}
        disabled={disabled}
      />
    );
  };

  return editing ? (
    <Row direction="horizontal">
      <Col flex={1}>{renderAnswerInput()}</Col>
      <Button
        type="primary"
        shape="round"
        onClick={() => {
          updateCell(record.id, parentId, value);
          setEditing(false);
        }}
        icon={<SaveOutlined />}
        style={{ marginRight: "8px" }}
      >
        Save
      </Button>
      <Button
        danger
        shape="round"
        onClick={() => {
          setEditing(false);
        }}
      >
        Close
      </Button>
    </Row>
  ) : (
    <Row>
      <Col
        flex={1}
        style={{
          cursor: !notEditable && !pendingData ? "pointer" : "not-allowed",
        }}
        onClick={() => {
          // if type attachment, open file in new tab
          if (
            record.type === QUESTION_TYPES.attachment &&
            value &&
            !isImageType
          ) {
            window.open(value, "_blank");
          }
          if (!notEditable && !pendingData && !isPublic) {
            setEditing(!editing);
          }
        }}
      >
        <span className={lastValue ? null : "blue"}>
          {record.type === QUESTION_TYPES.cascade && !record?.api?.endpoint ? (
            locationName
          ) : isImageType && value && !lastValue ? (
            <Image src={value} width={100} />
          ) : isImageType && lastValue && oldValue ? (
            <Image src={oldValue} width={100} />
          ) : lastValue ? (
            getLastAnswerDisplayValue(record, oldValue)
          ) : (
            getAnswerDisplayValue(record, value)
          )}
        </span>
      </Col>
      {edited && resetButton[record.id] && (
        <Button
          shape="round"
          onClick={() => {
            resetCell(record.id, parentId);
          }}
          icon={<UndoOutlined />}
        >
          Reset
        </Button>
      )}
    </Row>
  );
};

EditableCell.propTypes = {
  record: PropTypes.shape({
    id: PropTypes.number.isRequired,
    type: PropTypes.string.isRequired,
    value: PropTypes.oneOfType([PropTypes.any, PropTypes.oneOf([null])]),
    option: PropTypes.array,
    newValue: PropTypes.any,
  }),
  parentId: PropTypes.number.isRequired,
  updateCell: PropTypes.func,
  resetCell: PropTypes.func,
  pendingData: PropTypes.oneOfType([PropTypes.string, PropTypes.bool]),
  disabled: PropTypes.bool,
  readonly: PropTypes.bool,
};
export default React.memo(EditableCell);
