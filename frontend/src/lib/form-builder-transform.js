const _camelToSnake = (obj) => {
  const result = {};
  Object.keys(obj).forEach((key) => {
    const snakeKey = key.replace(/([A-Z])/g, "_$1").toLowerCase();
    result[snakeKey] = obj[key];
  });
  return result;
};

const _snakeToCamel = (obj) => {
  const result = {};
  Object.keys(obj).forEach((key) => {
    const camelKey = key.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
    result[camelKey] = obj[key];
  });
  return result;
};

const EDITOR_TYPE_ALIASES = { entity: "cascade" };

const _resolveEditorType = (typeStr, question) => {
  if (
    typeStr === "cascade" &&
    question.extra &&
    question.extra.type === "entity"
  ) {
    return "entity";
  }
  return typeStr;
};

const _snakeOrNull = (label) => {
  if (!label) {
    return null;
  }
  return String(label)
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_]/g, "");
};

export const editorToApi = (editorOutput) => {
  const { name, description, question_group } = editorOutput;
  return {
    name: name || "",
    description: description || null,
    question_group: (question_group || []).map((group, gi) => ({
      id: group.id || null,
      name: group.name || _snakeOrNull(group.label),
      label: group.label || null,
      order: gi + 1,
      repeatable: group.repeatable || false,
      repeat_text: group.repeatText || group.repeat_text || null,
      question: (group.question || []).map((q, qi) => {
        const s = _camelToSnake(q);
        delete s.question_group_id;
        return {
          id: s.id || null,
          order: qi + 1,
          label: s.label,
          short_label: s.short_label || null,
          name: s.name || _snakeOrNull(s.label),
          type: EDITOR_TYPE_ALIASES[s.type] || s.type,
          meta: s.meta || false,
          required: s.required !== false,
          rule: s.rule || null,
          dependency: s.dependency || null,
          dependency_rule: s.dependency_rule || "AND",
          api: s.api || null,
          extra: s.extra || null,
          tooltip: s.tooltip || null,
          fn: s.fn || null,
          pre: s.pre && Object.keys(s.pre).length > 0 ? s.pre : null,
          display_only: s.display_only || false,
          option: (s.option || []).map((opt, oi) => ({
            order: oi + 1,
            label: opt.label,
            value:
              opt.value || String(opt.label).toLowerCase().replace(/\s+/g, "_"),
            other: opt.other || false,
            color: opt.color || null,
          })),
        };
      }),
    })),
  };
};

export const apiToEditor = (apiResponse) => {
  const {
    id,
    name,
    description,
    version,
    latest_version,
    status,
    published_at,
    active_version_id,
    question_group,
  } = apiResponse;
  return {
    id,
    name,
    description: description || null,
    version,
    latest_version,
    status,
    published_at,
    active_version_id,
    question_group: (question_group || []).map((group) => ({
      id: group.id,
      name: group.name,
      label: group.label,
      repeatable: group.repeatable,
      repeat_text: group.repeat_text,
      question: (group.question || []).map((q) => {
        const c = _snakeToCamel(q);
        return {
          ...c,
          type: _resolveEditorType(c.type, c),
          option: (q.option || []).map((opt) => ({
            order: opt.order,
            label: opt.label,
            value: opt.value,
            other: opt.other,
            color: opt.color,
          })),
        };
      }),
    })),
  };
};
