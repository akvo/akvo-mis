import axios from "axios";
import { message } from "antd";
import { QUESTION_TYPES } from "./constants";
import api from "./api";
import uiText from "./ui-text";
import { transformValue } from "./transformers";
import moment from "moment";

export const getCascadeAnswerAPI = async (userLevel, id, questonAPI, value) => {
  const { initial, endpoint, query_params } = questonAPI;
  if (endpoint.includes("organisation")) {
    const res = await fetch(
      `${window.location.origin}${endpoint}${query_params}`
    );
    const apiData = await res.json();
    const findOrg = apiData?.children?.find((c) => c?.name === value);
    return { [id]: [findOrg?.id] };
  }
  if (initial) {
    const cascadeID = value || initial;
    const res = await fetch(
      `${window.location.origin}${endpoint}/${cascadeID}`
    );
    const apiData = await res.json();
    if (endpoint.includes("administration")) {
      const parents = apiData?.path
        ?.split(".")
        ?.filter((a) => a !== "")
        .slice(1);
      const startLevel = userLevel ? userLevel - 1 : 0;
      const admValues = [...parents, apiData?.id]
        .map((a) => parseInt(a, 10))
        .slice(startLevel);
      return {
        [id]: admValues,
      };
    }
    return { [id]: [apiData?.id] };
  }
  const res = await fetch(window.location.origin + endpoint);
  const apiData = await res.json();
  const findCascade = apiData?.find((d) => d?.name === value);
  return {
    [id]: [findCascade?.id],
  };
};

export const getEntityByName = async ({ id, value, apiURL }) => {
  try {
    const { data: apiData } = await axios.get(apiURL);
    const findData = apiData?.find((d) => d?.name === value);
    return { id, value: findData?.id };
  } catch {
    return null;
  }
};

export const processFileUploads = async (questions = [], values) => {
  const files = Object.entries(values)
    .filter(([key, val]) => {
      // Parse the key to handle both standard and repeatable question formats
      // For repeatable questions, key format is "questionID-repeatIndex"
      const [baseKey] = key.split("-");
      const questionId = parseInt(baseKey, 10);

      if (isNaN(questionId)) {
        return false;
      }
      const question = questions.find((q) => q.id === questionId);
      return (
        question?.type === QUESTION_TYPES.attachment && val instanceof File
      );
    })
    .map(([key, val]) => {
      // Keep the original key format to maintain the repeatable structure
      const [baseKey] = key.split("-");
      const questionId = parseInt(baseKey, 10);
      return {
        question_id: questionId,
        file: val,
        original_key: key, // Preserve the original key for mapping back
      };
    });

  if (!files.length) {
    return values;
  }

  const uploadPromises = files.map(({ question_id, file }) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post(`upload/attachments?question_id=${question_id}`, formData);
  });

  const results = await Promise.allSettled(uploadPromises);

  if (results.some((result) => result.status === "rejected")) {
    message.error({
      content: uiText.en.errorSomething,
      description: uiText.en.errorFileUpload,
    });
    return;
  }

  // Create a new values object with the uploaded files
  const updatedValues = { ...values };

  // Process each successfully uploaded file
  results.forEach((result, index) => {
    if (result.status === "fulfilled") {
      const data = result.value.data;
      const originalKey = files[index].original_key;
      updatedValues[originalKey] = data.file;
    }
  });

  return updatedValues;
};

export const processEntityCascades = async (questions, values) => {
  // Find entity cascade questions
  const entityQuestions = questions.filter(
    (q) =>
      q.type === QUESTION_TYPES.cascade &&
      q.extra?.type === QUESTION_TYPES.entity &&
      typeof values[q.id] === "string"
  );

  if (!entityQuestions.length) {
    return values;
  }

  const entityPromises = entityQuestions.map((q) => {
    const parent = questions.find((subq) => subq.id === q.extra.parentId);
    const parentVal = values[parent?.id];
    const pid = Array.isArray(parentVal) ? parentVal.slice(-1)[0] : parentVal;
    return getEntityByName({
      id: q.id,
      value: values[q.id],
      apiURL: `${q.api.endpoint}${pid}`,
    });
  });

  const settledEntities = await Promise.allSettled(entityPromises);

  // Process successfully resolved entities
  const updatedValues = { ...values };
  settledEntities.forEach(({ status, value: entity }) => {
    if (status === "fulfilled" && entity?.value && values[entity.id]) {
      updatedValues[entity.id] = entity.value;
    }
  });

  return updatedValues;
};

export const processRepeatableQuestions = (values, repeatableQuestions) => {
  // Group repeatable question values (e.g., "12345", "12345-1", "12345-2")
  const repeatableAnswers = [];
  const processedQuestionIds = new Set();

  // Extract base IDs and their variants
  const repeatableMap = {};

  // Get all valid repeatable question IDs for validation
  const validQuestionIds = new Set(repeatableQuestions.map((q) => q.id));

  // Extract and group repeatable questions by base ID
  Object.entries(values).forEach(([key, value]) => {
    // Skip non-numeric keys that don't match our pattern
    if (!/^\d+(-\d+)?$/.test(key)) {
      return;
    }

    // Skip empty values, null values, or undefined values
    if (
      value === null ||
      typeof value === "undefined" ||
      (typeof value === "string" && value.trim() === "")
    ) {
      return;
    }

    // Parse the key to get question ID and repetition index
    const [baseId, repetitionIndex] = key.includes("-")
      ? key.split("-")
      : [key, "0"];

    const baseIdNum = parseInt(baseId, 10);

    // Skip if this is not a valid repeatable question ID
    if (!validQuestionIds.has(baseIdNum)) {
      return;
    }

    // Initialize array for this question if it doesn't exist
    if (!repeatableMap[baseId]) {
      repeatableMap[baseId] = [];
    }

    // Store the value with its repetition index for sorting later
    repeatableMap[baseId].push({
      index: parseInt(repetitionIndex || "0", 10),
      value,
    });

    // Mark this question ID as processed
    processedQuestionIds.add(baseId);
  });

  // Process each question ID and format its answers
  processedQuestionIds.forEach((baseId) => {
    const questionId = parseInt(baseId, 10);
    const question = repeatableQuestions.find((q) => q.id === questionId);

    // Skip if question not found in repeatable questions
    if (!question) {
      return;
    }

    // Sort by repetition index to maintain order
    repeatableMap[baseId]
      .sort((a, b) => a.index - b.index)
      .forEach((item) => {
        // Use our enhanced transformValue function with forApi=true
        repeatableAnswers.push(
          transformValue(question, item.value, true, item.index)
        );
      });
  });

  return repeatableAnswers;
};

export const getAnswerDisplayValue = (record, value) => {
  switch (record.type) {
    case QUESTION_TYPES.date:
      return value ? moment(value).format("YYYY-MM-DD") : "-";
    case QUESTION_TYPES.multiple_option:
      return value?.length
        ? value
            ?.map((v) => {
              const option = record?.option?.find((o) => o.value === v);
              return option?.label;
            })
            ?.join(", ") || "-"
        : "-";
    case QUESTION_TYPES.option:
      return value?.length
        ? record?.option?.find((o) => o.value === value[0])?.label || "-"
        : "-";
    default:
      return value || value === 0 ? value : "-";
  }
};

export const getLastAnswerDisplayValue = (record, oldValue) => {
  switch (record.type) {
    case QUESTION_TYPES.multiple_option:
      return oldValue?.length
        ? oldValue
            ?.map((v) => {
              const option = record?.option?.find((o) => o.value === v);
              return option?.label;
            })
            ?.join(", ") || "-"
        : "-";
    case QUESTION_TYPES.option:
      return oldValue?.length
        ? record?.option?.find((o) => o.value === oldValue[0])?.label || "-"
        : "-";
    default:
      return oldValue || oldValue === 0 ? oldValue : "-";
  }
};

/**
 * Flatten a `/form/web` question for akvo-react-form.
 *
 * `extra` is spread onto the question (allowOther, api hints, ...) but
 * `extra.type` is a cascade sub-type ("administration" | "entity"), not a
 * render type — the library only knows "cascade", so an unknown type falls
 * back to a plain text input. Always keep the backend `type`.
 */
export const normalizeWebformQuestion = (q) => {
  if (!q?.extra) {
    return { ...q };
  }
  const { extra, ...rest } = q;
  let qVal = { ...rest, ...extra, type: q.type };
  if (extra.allowOther) {
    qVal = {
      ...qVal,
      allowOtherText: extra.allowOtherText || "Enter any OTHER value",
    };
  }
  if (extra.type === QUESTION_TYPES.entity) {
    qVal = { ...qVal, type: QUESTION_TYPES.cascade, extra };
  }
  return qVal;
};
