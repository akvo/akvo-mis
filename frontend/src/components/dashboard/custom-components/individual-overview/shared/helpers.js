/**
 * Pure lookup + formatting helpers for the Individual Overview pattern.
 *
 * Centralises every walk over the published forms (from getForms()) and
 * every transform applied to a `/data/<id>` answer payload, so shell
 * components stay free of form-walking code.
 */

import { api } from "../../../../../lib";
import { getForms } from "../../../../../util/form";

const toNumericId = (id) => {
  if (typeof id === "number") {
    return id;
  }
  const n = Number(id);
  return Number.isNaN(n) ? id : n;
};

/**
 * Find a question definition by id across every published form (getForms()).
 *
 * forms shape (fetched at app startup into the store):
 *   [{ id, name, content: { question_group: [{ question: [{ id, label, type, option }] }] } }]
 *
 * @param {number|string} questionId
 * @returns {object|null}
 */
export const findQuestion = (questionId) => {
  if (questionId === null || typeof questionId === "undefined") {
    return null;
  }
  const target = toNumericId(questionId);
  const forms = getForms();
  for (let i = 0; i < forms.length; i += 1) {
    const groups = forms[i]?.content?.question_group || [];
    for (let j = 0; j < groups.length; j += 1) {
      const questions = groups[j]?.question || [];
      const found = questions.find((q) => q?.id === target);
      if (found) {
        return found;
      }
    }
  }
  return null;
};

/**
 * Find an answer entry for `questionId` from a /data/<id> response.
 *
 * @param {Array} values
 * @param {number|string} questionId
 * @returns {object|null}
 */
export const findAnswer = (values, questionId) => {
  if (
    !Array.isArray(values) ||
    questionId === null ||
    typeof questionId === "undefined"
  ) {
    return null;
  }
  const target = toNumericId(questionId);
  return values.find((v) => v?.question === target) || null;
};

const formatOptionAnswer = (value, question) => {
  const options = question?.option || [];
  const lookup = new Map(options.map((o) => [o?.value, o?.label || o?.value]));
  const list = Array.isArray(value) ? value : [value];
  return list
    .filter((v) => v !== null && typeof v !== "undefined" && v !== "")
    .map((v) => lookup.get(v) || v)
    .join(", ");
};

const formatGeoAnswer = (value) => {
  if (Array.isArray(value) && value.length >= 2) {
    return `${value[0]}, ${value[1]}`;
  }
  if (value && typeof value === "object" && "lat" in value && "lng" in value) {
    return `${value.lat}, ${value.lng}`;
  }
  return null;
};

const formatAdministrationAnswer = (value, lookups) => {
  const map = lookups?.administration;
  const list = Array.isArray(value) ? value : [value];
  const items = list
    .map((v) => {
      if (v === null || typeof v === "undefined" || v === "") {
        return null;
      }
      const id = toNumericId(v);
      if (map && map.get(id)) {
        return map.get(id);
      }
      return String(v);
    })
    .filter((s) => s !== null);
  if (!items.length) {
    return null;
  }
  return items.join(" - ");
};

/**
 * Pretty-print an answer value for display in tables. Returns null for
 * empty/missing values so callers can skip rendering.
 *
 * @param {object|null} answer
 * @param {object|null} question
 * @param {object} [lookups]
 * @param {Map<number,string>} [lookups.administration]
 *   Resolved administration id → display name. When missing the helper
 *   falls back to the raw id so callers that have not pre-fetched names
 *   still render something.
 * @returns {string|null}
 */
export const formatAnswerValue = (answer, question, lookups) => {
  if (!answer) {
    return null;
  }
  const value = answer.value;
  if (value === null || typeof value === "undefined" || value === "") {
    return null;
  }
  const type = question?.type;
  if (type === "option" || type === "multiple_option") {
    const text = formatOptionAnswer(value, question);
    return text || null;
  }
  if (type === "geo") {
    return formatGeoAnswer(value);
  }
  if (["cascade", "administration"].includes(type)) {
    return formatAdministrationAnswer(value, lookups);
  }
  if (Array.isArray(value)) {
    const items = value.filter(
      (v) => v !== null && typeof v !== "undefined" && v !== ""
    );
    if (!items.length) {
      return null;
    }
    return items.join(", ");
  }
  /**
   * Dates are stored as ISO strings but we want to display them in a more
   * human-friendly format.
   */
  if (type === "date") {
    const d = new Date(value);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleDateString("en-US", {
        weekday: "short",
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    }
  }
  return String(value);
};

const administrationNameCache = new Map();
const administrationInflight = new Map();

const buildAdministrationDisplayName = (data) => {
  if (!data) {
    return null;
  }
  if (typeof data.full_name === "string" && data.full_name.length > 0) {
    return data.full_name.split("|").join(" - ");
  }
  return data.name || null;
};

const fetchAdministrationName = (id) => {
  if (administrationNameCache.has(id)) {
    return Promise.resolve(administrationNameCache.get(id));
  }
  if (administrationInflight.has(id)) {
    return administrationInflight.get(id);
  }
  const promise = api
    .get(`administration/${id}`)
    .then(({ data }) => {
      const name = buildAdministrationDisplayName(data);
      if (name) {
        administrationNameCache.set(id, name);
      }
      administrationInflight.delete(id);
      return name;
    })
    .catch((error) => {
      administrationInflight.delete(id);
      console.error(`fetchAdministrationName(${id}) failed`, error);
      return null;
    });
  administrationInflight.set(id, promise);
  return promise;
};

/**
 * Walk a /data/<id> answer payload and collect every administration id
 * that needs name resolution. IDs are returned as numbers; duplicates and
 * non-numeric values are dropped.
 *
 * @param {Array} values
 * @returns {Array<number>}
 */
export const collectAdministrationIds = (values) => {
  if (!Array.isArray(values)) {
    return [];
  }
  const ids = new Set();
  values.forEach((entry) => {
    if (!entry || entry.value === null || typeof entry.value === "undefined") {
      return;
    }
    const question = findQuestion(entry.question);
    if (!question || !["cascade", "administration"].includes(question.type)) {
      return;
    }
    const list = Array.isArray(entry.value) ? entry.value : [entry.value];
    list.forEach((v) => {
      const num = toNumericId(v);
      if (typeof num === "number" && Number.isFinite(num)) {
        ids.add(num);
      }
    });
  });
  return Array.from(ids);
};

/**
 * Resolve a list of administration ids to display names via the
 * `/administration/<id>` API. Successful lookups are cached process-wide
 * so subsequent calls for the same id are free.
 *
 * @param {Array<number>} ids
 * @returns {Promise<Map<number,string>>}
 */
export const fetchAdministrationNames = async (ids) => {
  if (!Array.isArray(ids) || ids.length === 0) {
    return new Map();
  }
  const entries = await Promise.all(
    ids.map(async (id) => {
      const name = await fetchAdministrationName(id);
      return [id, name];
    })
  );
  return new Map(entries.filter(([, name]) => Boolean(name)));
};

export const __resetAdministrationNameCache = () => {
  administrationNameCache.clear();
  administrationInflight.clear();
};

/**
 * Extract a photo URL from an answer. Photo answers store the URL directly
 * in `value`. Non-string / blank values resolve to null.
 *
 * @param {Array} values
 * @param {number|string} questionId
 * @returns {string|null}
 */
export const extractPhotoUrl = (values, questionId) => {
  const answer = findAnswer(values, questionId);
  if (!answer) {
    return null;
  }
  const v = answer.value;
  if (typeof v === "string" && v.trim().length > 0) {
    return v;
  }
  return null;
};

/**
 * Find a question group definition by its id across every published form
 * (getForms()). Returns null when not found.
 *
 * @param {number|string} groupId
 * @returns {object|null}
 */
export const findQuestionGroup = (groupId) => {
  if (groupId === null || typeof groupId === "undefined") {
    return null;
  }
  const target = toNumericId(groupId);
  const forms = getForms();
  for (let i = 0; i < forms.length; i += 1) {
    const groups = forms[i]?.content?.question_group || [];
    const found = groups.find((g) => g?.id === target);
    if (found) {
      return found;
    }
  }
  return null;
};

/**
 * Walk every question in a question group, drop `type: "photo"`
 * questions and any whose answer resolves to null/empty, then join the
 * surviving formatted answers with `separator`. Used to combine all
 * answers inside a scope question group into a single cell (e.g. the
 * EPS Construction Information "Implementation / Construction" column).
 *
 * @param {number|string} groupId
 * @param {Array} values
 * @param {object} [options]
 * @param {string} [options.separator=", "]
 * @returns {string}            Empty string when the group is unknown
 *                               or every answer is empty.
 */
export const collectGroupAnswers = (groupId, values, options) => {
  const separator = options?.separator || ", ";
  const group = findQuestionGroup(groupId);
  if (!group) {
    return "";
  }
  const questions = group.question || [];
  const parts = [];
  for (let i = 0; i < questions.length; i += 1) {
    const q = questions[i];
    if (!q || q.type === "photo") {
      continue;
    }
    const answer = findAnswer(values, q.id);
    const formatted = formatAnswerValue(answer, q);
    if (formatted !== null && formatted !== "") {
      parts.push(formatted);
    }
  }
  return parts.join(separator);
};

/**
 * Convenience: findAnswer + findQuestion + formatAnswerValue.
 *
 * @param {Array} values
 * @param {number|string} questionId
 * @returns {string|null}
 */
export const resolveAnswerLabel = (values, questionId) => {
  const answer = findAnswer(values, questionId);
  if (!answer) {
    return null;
  }
  const question = findQuestion(questionId);
  return formatAnswerValue(answer, question);
};

/**
 * Sort an array of `{ date, ...rest }` ascending by date. Stable; entries
 * with null/missing dates sort first.
 *
 * @param {Array<{date: string|null}>} rows
 * @returns {Array}
 */
export const sortByDateAscending = (rows) => {
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows
    .map((row, idx) => ({ row, idx }))
    .sort((a, b) => {
      const ad = a.row?.date;
      const bd = b.row?.date;
      if (!ad && !bd) {
        return a.idx - b.idx;
      }
      if (!ad) {
        return -1;
      }
      if (!bd) {
        return 1;
      }
      const at = new Date(ad).getTime();
      const bt = new Date(bd).getTime();
      if (at === bt) {
        return a.idx - b.idx;
      }
      return at - bt;
    })
    .map((entry) => entry.row);
};
