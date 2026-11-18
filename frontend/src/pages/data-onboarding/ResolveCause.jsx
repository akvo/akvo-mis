import React, { useState } from "react";
import { Button, Select, Space, Typography } from "antd";

const { Text } = Typography;

// The columns a spec names; the profile is not sent to the page.
const sheetColumns = (spec) => [
  ...new Set([
    ...spec.key_columns,
    ...spec.administration_columns,
    ...spec.columns.map((c) => c.column),
    ...spec.unmapped_columns.map((c) => c.column),
  ]),
];

const LevelMapping = ({ form, spec, levels, onEdit, text }) => {
  const [columns, setColumns] = useState(spec.administration_columns);
  const [level, setLevel] = useState(1);
  return (
    <Space wrap>
      <Select
        mode="multiple"
        style={{ minWidth: 240 }}
        placeholder={text.dataOnboardingLocationColumns}
        value={columns}
        onChange={setColumns}
        options={sheetColumns(spec).map((c) => ({ label: c, value: c }))}
      />
      <Select
        style={{ minWidth: 160 }}
        aria-label={text.dataOnboardingFirstLevel}
        value={level}
        onChange={setLevel}
        options={levels.slice(1).map((name, i) => ({
          label: name,
          value: i + 1,
        }))}
      />
      <Button
        size="small"
        disabled={!columns.length}
        onClick={() =>
          onEdit({ op: "map_level", form: form.key, columns, level })
        }
      >
        {text.saveButton}
      </Button>
    </Space>
  );
};

// The control that settles one blocked cause, by its kind.
const ResolveCause = ({ cause, form, spec, levels, onEdit, text }) => {
  if (cause.kind === "near_match") {
    return cause.units.map((u) => (
      <Space key={u.name} wrap style={{ display: "flex" }}>
        <Text>
          {u.name} → {u.match}
        </Text>
        <Button
          size="small"
          onClick={() =>
            onEdit({ op: "resolve_near_match", ...u, use: "existing" })
          }
        >
          {text.dataOnboardingUseExisting}
        </Button>
        <Button
          size="small"
          onClick={() => onEdit({ op: "resolve_near_match", ...u, use: "new" })}
        >
          {text.dataOnboardingAddNew}
        </Button>
      </Space>
    ));
  }
  if (cause.kind === "shared_name") {
    return cause.units.map((u) => (
      <Space key={u.name} wrap style={{ display: "flex" }}>
        <Text>{u.name}</Text>
        <Select
          style={{ minWidth: 200 }}
          placeholder={text.dataOnboardingChooseParent}
          onChange={(parent) =>
            onEdit({ op: "choose_parent", name: u.name, parent })
          }
          options={u.parents.map((p) => ({ label: p.name, value: p.id }))}
        />
      </Space>
    ));
  }
  if (cause.kind === "level_mapping" && spec) {
    return (
      <LevelMapping
        form={form}
        spec={spec}
        levels={levels}
        onEdit={onEdit}
        text={text}
      />
    );
  }
  if (cause.kind === "no_location") {
    return (
      <Space wrap>
        <Select
          style={{ minWidth: 200 }}
          placeholder={text.dataOnboardingLocationColumn}
          onChange={(column) =>
            onEdit({ op: "set_location_column", form: form.key, column })
          }
          options={sheetColumns(spec).map((c) => ({ label: c, value: c }))}
        />
        <Button
          size="small"
          danger
          onClick={() => onEdit({ op: "drop_form", form: form.key })}
        >
          {text.dataOnboardingDropForm}
        </Button>
      </Space>
    );
  }
  return null;
};

export default ResolveCause;
