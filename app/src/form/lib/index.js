import * as Yup from 'yup';
// Imported directly, not via '../../lib': that barrel pulls expo-background-task and
// expo-notifications, native modules this pure-logic module never uses.
import i18n from '../../lib/i18n';
import { QUESTION_TYPES } from '../../lib/constants';
import FormState from '../../store/forms';
import BuildParamsState from '../../store/buildParams';
import { blockingMessage, isNoAnswer, runPolygonRules } from './polygon-rules';

export * from './geometry';
export * from './gps-vertex';
export * from './polygon-rules';

/**
 * Polygon rules, layered on top of Yup rather than inside it.
 *
 * Runs only when Yup has already passed AND there is an answer to judge: an absent required
 * polygon is Yup's error to report, and adding "a shape needs at least 3 points" next to
 * "... is required." would state the same absence twice (GEO-002 section 2.1.2).
 *
 * `trans` and the device settings are read here, at the caller, so the rules themselves stay
 * pure and testable without a store (GEO-013 D-1). Reading `lang` at call time also means a
 * language switch mid-form produces the message in the new language.
 *
 * Returns the blocking string, or null when nothing blocks - a `warn` never reaches this
 * surface; its channel is the inline hint (GEO-002 D-8).
 */
const polygonFeedback = (currentValue, field) => {
  if (field?.type !== QUESTION_TYPES.geoshape || isNoAnswer(currentValue)) {
    return null;
  }
  const { lang } = FormState.getRawState();
  const results = runPolygonRules(currentValue, field, BuildParamsState.getRawState());
  return blockingMessage(results, i18n.text(lang), field?.label);
};

export const intersection = (array1, array2) => {
  const set1 = new Set(array1);
  const result = [];
  // eslint-disable-next-line no-restricted-syntax
  for (const item of array2) {
    if (set1.has(item)) {
      result.push(item);
    }
  }
  return result;
};

/**
 * Helper to recursively check if a dependency and all its ancestors are satisfied
 * @param {Object} dep - Dependency to check
 * @param {Object} values - Current form values
 * @param {Array} allQuestions - All questions (for looking up ancestors)
 * @param {Object} currentGroup - Current question group (for repeat handling)
 * @param {number} repeat - Repeat index for repeatable groups
 * @returns {boolean}
 */
const isDependencyWithAncestorsSatisfied = (
  dep,
  values,
  allQuestions,
  currentGroup,
  repeat = 0,
) => {
  // Check if this is a dependency on a question in the same group and needs modification for repeats
  let dependencyId = dep.id;
  const questions = currentGroup.question.map((question) => question.id);

  // For repeat questions, modify the dependency id to include the repeat suffix
  if (questions.includes(dep.id) && repeat) {
    dependencyId = `${dep.id}-${repeat}`;
  }

  // First check if this dependency itself is satisfied
  const answer = values?.[dependencyId];
  if (!validateDependency(dep, answer)) {
    return false;
  }

  // For repeatable groups, dep.id might have a suffix like "123-0"
  // Strip the suffix to find the original question
  const depIdStr = String(dep.id);
  const baseDepId = depIdStr.includes('-') ? parseInt(depIdStr.split('-')[0], 10) : dep.id;

  // Find the question this dependency refers to (using base ID)
  const question = allQuestions?.find((q) => q.id === baseDepId);
  if (!question || !question.dependency) {
    // No ancestors, this dependency is satisfied
    return true;
  }

  // Recursively check ancestors with their dependency_rule
  const ancestorRule = (question.dependency_rule || 'AND').toUpperCase();
  if (ancestorRule === 'OR') {
    // At least one ancestor must be satisfied (recursively)
    return question.dependency.some((ancestorDep) =>
      isDependencyWithAncestorsSatisfied(ancestorDep, values, allQuestions, currentGroup, repeat),
    );
  }
  // All ancestors must be satisfied (recursively)
  return question.dependency.every((ancestorDep) =>
    isDependencyWithAncestorsSatisfied(ancestorDep, values, allQuestions, currentGroup, repeat),
  );
};

export const onFilterDependency = (currentGroup, values, q, repeat = 0, allQuestions = []) => {
  if (q?.dependency) {
    // Get the dependency rule (default to AND for backward compatibility)
    const dependencyRule = (q?.dependency_rule || 'AND').toUpperCase();

    // For AND rule: ALL dependencies (with their ancestors) must be fully satisfied
    if (dependencyRule === 'AND') {
      const allSatisfied = q.dependency.every((dep) =>
        isDependencyWithAncestorsSatisfied(dep, values, allQuestions, currentGroup, repeat),
      );
      if (!allSatisfied) {
        return false;
      }
    }

    // For OR rule: At least ONE dependency (with its ancestors) must be fully satisfied
    if (dependencyRule === 'OR') {
      const satisfied = q.dependency.some((dep) =>
        isDependencyWithAncestorsSatisfied(dep, values, allQuestions, currentGroup, repeat),
      );
      if (!satisfied) {
        return false;
      }
    }
  }
  return q;
};

export const transformForm = (
  forms,
  currentValues,
  lang = 'en',
  repeatState = {},
  prevAdmAnswer = null,
) => {
  const nonEnglish = lang !== 'en';
  const currentForm = nonEnglish ? i18n.transform(lang, forms) : forms;
  const questions = currentForm.question_group
    .map((x) => x.question)
    .flatMap((q) => q)
    .map((q) => (nonEnglish ? i18n.transform(lang, q) : q))
    .map((q) => {
      if (q.type === QUESTION_TYPES.option || q.type === QUESTION_TYPES.multiple_option) {
        const options = q.option.map((o) => (nonEnglish ? i18n.transform(lang, o) : o));
        return {
          ...q,
          option: options.sort((a, b) => a.order - b.order),
        };
      }
      if (q?.tooltip) {
        const transTooltip = nonEnglish ? i18n.transform(lang, q.tooltip) : q.tooltip;
        return {
          ...q,
          tooltip: transTooltip,
        };
      }
      return q;
    });

  const transformed = questions.map((x) => {
    let requiredSignTemp = x?.requiredSign || null;
    if (x?.required && !x?.requiredSign) {
      requiredSignTemp = '*';
    }
    if (x?.dependency) {
      const dependencyRule = x?.dependency_rule || 'AND';

      // DON'T flatten dependencies - keep original structure for ALL rules
      // Use recursive evaluation for both AND and OR rules
      return {
        ...x,
        requiredSign: requiredSignTemp,
        dependency: x.dependency, // Keep original, not flattened
        dependency_rule: dependencyRule,
      };
    }
    return {
      ...x,
      requiredSign: requiredSignTemp,
    };
  });

  // Transform question groups
  const questionGroups = forms.question_group
    .sort((a, b) => a.order - b.order)
    .map((qg, qgi) => {
      const translatedQg = nonEnglish ? i18n.transform(lang, qg) : qg;

      // Get repeats array but don't add them as properties
      const repeatsArray = repeatState?.[qgi] || repeatState?.[qg?.name] || [0];

      // Transform questions based on whether the group is repeatable or not
      const transformedQuestions = [];

      if (qg?.repeatable) {
        // Handle repeatable groups - prepare sections data
        const sectionData = repeatsArray.map((repeatIndex) => ({
          repeatIndex,
          title: repeatIndex !== 0 ? `${qg.label || qg.name} #${repeatIndex + 1}` : null,
          data: qg.question
            .map((q, qx) => {
              const transformedQuestion = transformed.find((t) => t.id === q.id);
              if (!transformedQuestion) {
                return null;
              }

              // Filter out questions based on dependencies, etc.
              // Pass the repeatIndex to handle repeat-specific dependencies
              if (
                !onFilterDependency(qg, currentValues, transformedQuestion, repeatIndex, questions)
              ) {
                return null;
              }

              return {
                ...transformedQuestion,
                id:
                  repeatIndex === 0
                    ? transformedQuestion.id
                    : `${transformedQuestion.id}-${repeatIndex}`,
                keyform: `${repeatIndex + 1}.${qx + 1}`, // Ensure keyform is defined
                group_id: qgi,
                group_name: qg?.name,
              };
            })
            .filter((q) => q),
        }));

        // Flatten sections data into questions
        sectionData.forEach((section) => {
          transformedQuestions.push(...section.data);
        });

        // Return both the sections data and transformed questions
        if (transformedQuestions.length > 0) {
          return {
            ...translatedQg,
            id: qg?.id || qgi,
            sections: sectionData, // Include sections data
            question: transformedQuestions,
          };
        }
      } else {
        // Handle non-repeatable groups
        /**
         * Only ENTITY cascades are gated, and only until an administration answer exists
         * to scope them by.
         *
         * `extra.type` is a cascade sub-type, and "administration" is the other member —
         * so the previous `|| !q?.extra?.type` clause, meant to let ordinary questions
         * through, silently dropped every administration cascade from the rendered form.
         * The enumerator could not answer it, `keyform` renumbered over the gap, and a
         * required administration question then reached the server unanswered and was
         * refused.
         */
        const questionList = qg.question.filter(
          (q) => q?.extra?.type !== 'entity' || prevAdmAnswer?.length > 0,
        );

        // Process questions with numbering
        const questionWithNumber = questionList.reduce((curr, q, i) => {
          const transformedQuestion = transformed.find((t) => t.id === q.id);
          if (!transformedQuestion) return curr;

          // Filter out questions based on dependencies, etc.
          if (!onFilterDependency(qg, currentValues, transformedQuestion, 0, questions)) {
            return curr;
          }

          if (q?.default_value && i === 0) {
            return [
              {
                ...transformedQuestion,
                keyform: 0,
                group_id: qg?.id,
                group_name: qg?.name,
              },
            ];
          }
          if (q?.default_value && i > 0 && curr.length > 0) {
            // Only access curr[i-1] if curr has elements
            return [
              ...curr,
              {
                ...transformedQuestion,
                keyform: curr[i - 1]?.keyform || i, // Fallback to index if keyform is undefined
                group_id: qg?.id,
                group_name: qg?.name,
              },
            ];
          }
          if (i === 0) {
            return [
              {
                ...transformedQuestion,
                keyform: 1,
                group_id: qg?.id,
                group_name: qg?.name,
              },
            ];
          }

          // Add a safety check to prevent undefined keyform
          const prevKeyform = curr[i - 1]?.keyform;
          return [
            ...curr,
            {
              ...transformedQuestion,
              keyform: prevKeyform !== undefined ? prevKeyform + 1 : i + 1, // Fallback to index+1 if undefined
              group_id: qg?.id,
              group_name: qg?.name,
            },
          ];
        }, []);

        transformedQuestions.push(...questionWithNumber);
      }

      if (transformedQuestions.length > 0) {
        return {
          ...translatedQg,
          id: qg?.id || qgi,
          question: transformedQuestions,
        };
      }
      return undefined;
    })
    .filter((qg) => qg)
    .filter((qg) => qg.question.length);

  return {
    ...forms,
    question_group: questionGroups,
  };
};

export const validateDependency = (dependency, value) => {
  if (dependency?.options && typeof value !== 'undefined') {
    const v = typeof value === 'string' ? [value] : value;
    return intersection(dependency.options, v)?.length > 0;
  }
  let valid = false;
  if (dependency?.min) {
    valid = value >= dependency.min;
  }
  if (dependency?.max) {
    valid = value <= dependency.max;
  }
  if (dependency?.equal) {
    valid = value === dependency.equal;
  }
  if (dependency?.notEqual) {
    valid = value !== dependency.notEqual && !!value;
  }
  return valid;
};

export const generateValidationSchemaFieldLevel = async (currentValue, field) => {
  const { label, type, required, rule } = field;
  const requiredError = `${label} is required.`;
  let yupType;
  switch (type) {
    case 'number':
      // number rules
      yupType = currentValue === '' ? Yup.string() : Yup.number();
      if (currentValue !== '' && rule?.min) {
        yupType = yupType.min(rule.min);
      }
      if (currentValue !== '' && rule?.max) {
        yupType = yupType.max(rule.max);
      }
      if (currentValue !== '' && !rule?.allowDecimal) {
        // by default decimal is allowed
        yupType = yupType.integer();
      }
      break;
    case 'date':
      if (currentValue === '') {
        yupType = Yup.string();
      } else {
        yupType = Yup.date();
      }
      break;
    case 'option':
      yupType = Yup.array().nullable();
      if (required) {
        yupType = Yup.array().min(1, requiredError);
      }
      break;
    case 'multiple_option':
      yupType = Yup.array().nullable();
      if (required) {
        yupType = Yup.array().min(1, requiredError);
      }
      break;
    case 'cascade':
      yupType = Yup.array();
      break;
    case 'geo':
      yupType = Yup.array();
      break;
    case 'geoshape':
    case 'geotrace':
      /**
       * Nullable, mirroring multiple_option rather than geo: an unanswered question arrives
       * here as null (see FormNavigation's defaultVal list) and a bare Yup.array() rejects
       * null, flagging an optional polygon the enumerator simply never opened.
       */
      yupType = Yup.array().nullable();
      if (required) {
        yupType = Yup.array().min(1, requiredError);
      }
      break;
    default:
      yupType = Yup.string();
      break;
  }
  if (required) {
    yupType = yupType.required(requiredError);
  }
  try {
    await yupType.validateSync(currentValue);
  } catch (error) {
    return {
      [field?.id]: error.message,
    };
  }
  return {
    [field?.id]: polygonFeedback(currentValue, field) || true,
  };
};

export const generateDataPointName = (forms, currentValues, cascades = {}, datapoint = null) => {
  const dataPointNameValues = forms?.question_group?.length
    ? forms.question_group
        .filter((qg) => !qg?.repeatable)
        .flatMap((qg) => qg.question.filter((q) => q?.meta))
        ?.filter((q) => currentValues?.[q.id] || cascades?.[q.id])
        ?.map((q) => {
          let value = currentValues?.[q.id];
          if (q?.type === QUESTION_TYPES.cascade && q?.source?.file === 'administrator.sqlite') {
            value = cascades?.[q.id] || value;
          }
          if (q?.type === QUESTION_TYPES.date) {
            const dateValue = currentValues?.[q.id];
            const date = new Date(dateValue);
            const formattedDate = date.toISOString().split('T')[0]; // "2025-06-03"
            const fullDate = date.toString(); // "Tue Jun 03 2025 16:21:51 GMT+0700"
            value = `${formattedDate} - ${fullDate}`;
          }
          return { id: q.id, type: q.type, value };
        })
        ?.sort((a, b) => a.order - b.order)
    : [];
  const dpName = dataPointNameValues
    .filter(
      (d) =>
        ![QUESTION_TYPES.geo, QUESTION_TYPES.geoshape, QUESTION_TYPES.geotrace].includes(d.type) &&
        (d.value || d.value === 0),
    )
    .map((x) => x.value)
    .join(' - ');
  if (datapoint?.geo && typeof datapoint.geo === 'string') {
    if (datapoint.geo.includes('|')) {
      // If geo is already in the format "lat|lng"
      return { dpName, dpGeo: datapoint.geo };
    }
    // Check datapoint.geo is a JSON array string
    const dpGeo =
      datapoint.geo.startsWith('[') && datapoint.geo.endsWith(']') ? JSON.parse(datapoint.geo) : [];
    if (!dpName || `${dpName}`.trim() === '') {
      return { dpName: datapoint.name || '', dpGeo: dpGeo.join('|') };
    }
    return { dpName, dpGeo: dpGeo.join('|') };
  }
  const geoQuestion = forms?.question_group
    ?.flatMap((qg) => qg?.question)
    ?.find((q) => q?.type === QUESTION_TYPES.geo);
  const [lat, lng] =
    dataPointNameValues.find((d) => d.type === QUESTION_TYPES.geo)?.value ||
    currentValues?.[geoQuestion?.id] ||
    [];
  const dpGeo = lat && lng ? `${lat}|${lng}` : null;
  return { dpName, dpGeo };
};

export const getCurrentTimestamp = () => Math.floor(Date.now() / 1000);

export const getDurationInMinutes = (startTime) => {
  // Get the current timestamp in seconds
  const endTime = getCurrentTimestamp();
  // Calculate the duration in seconds
  const durationInSeconds = endTime - startTime;

  return Math.floor(durationInSeconds / 60);
};

const transformValue = (question, value, prefilled = []) => {
  const findPrefilled = prefilled.find((p) => p?.id === question?.id);
  const defaultEmpty = [QUESTION_TYPES.multiple_option, QUESTION_TYPES.option].includes(
    question?.type,
  )
    ? []
    : '';
  let answer = defaultEmpty;
  if (value || value === 0) {
    answer = value;
  }
  if (findPrefilled?.answer) {
    answer = findPrefilled.answer;
  }

  if (question?.type === QUESTION_TYPES.cascade) {
    return [answer];
  }
  if (
    [QUESTION_TYPES.geo, QUESTION_TYPES.geoshape, QUESTION_TYPES.geotrace].includes(question?.type)
  ) {
    return answer === '' ? [] : value;
  }
  if (question?.type === QUESTION_TYPES.number && typeof answer !== 'undefined') {
    return `${answer}`;
  }
  if (question?.default_value?.monitoring) {
    return [QUESTION_TYPES.multiple_option, QUESTION_TYPES.option].includes(question?.type)
      ? [question.default_value.monitoring]
      : question.default_value.monitoring;
  }
  return answer;
};

export const transformMonitoringData = (formDataJson, lastValues) => {
  const formData = JSON.parse(formDataJson.json);
  const allQuestions = formData?.question_group?.flatMap((qg) => qg?.question);
  const prefilled = allQuestions
    ?.filter((q) => lastValues?.[q?.id] && q?.pre)
    ?.filter((q) => lastValues[q.id] === q.pre.answer || lastValues[q.id].includes(q.pre.answer))
    ?.flatMap((q) => q?.pre?.fill || []);

  // Initialize with an empty object
  const currentValues = {};

  // Loop through the lastValues object keys
  if (lastValues && Object.keys(lastValues).length) {
    Object.keys(lastValues).forEach((key) => {
      const [questionId] = key.split('-');
      const question = allQuestions?.find((q) => `${q?.id}` === questionId);
      if (question) {
        currentValues[key] = transformValue(question, lastValues[key], prefilled);
      }
    });
  }

  const admQuestion = allQuestions.find(
    (q) => q?.type === QUESTION_TYPES.cascade && q?.source?.file === 'administrator.sqlite',
  );
  const prevAdmAnswer = lastValues?.[admQuestion?.id] ? [lastValues?.[admQuestion?.id]] : [];
  return { currentValues, prevAdmAnswer };
};

/**
 * Sanitizes the function string by removing any occurrences of "fetch" or "return fetch"
 * and replacing them with a console.error statement.
 */
const sanitize = [
  {
    prefix: /return fetch|fetch/g,
    re: /return fetch(\(.+)\} +|fetch(\(.+)\} +/,
    log: 'Fetch is not allowed.',
  },
];
/**
 * Checks if the function string contains any occurrences of "fetch" or "return fetch"
 * and replaces them with a console.error statement.
 * @param {string} fnString - The function string to check.
 * @returns
 */
const checkDirty = (fnString) =>
  sanitize.reduce((prev, sn) => {
    const dirty = prev.match(sn.re);
    if (dirty) {
      return prev.replace(sn.prefix, '').replace(dirty[1], `console.error("${sn.log}");`);
    }
    return prev;
  }, fnString);

/**
 * Fucntion to convert a function string into an array of tokens.
 * It handles hex color codes by temporarily replacing them with placeholders.
 * The function uses a regular expression to match various tokens, including
 * operators, numbers, and identifiers.
 * @param {string} fnString - The function string to be tokenized.
 * @returns
 */
const fnToArray = (fnString) => {
  // First handle hex color codes by temporarily replacing them
  const hexColorPattern = /"#[0-9A-Fa-f]{6}"/g;
  const hexColors = [];
  let modifiedString = fnString;

  // Extract and replace hex colors with placeholders
  let index = 0;
  let match = hexColorPattern.exec(fnString);
  while (match !== null) {
    const placeholder = `__HEX_COLOR_${index}__`;
    hexColors.push({ placeholder, value: match[0] });
    modifiedString = modifiedString.replace(match[0], placeholder);
    index += 1;
    match = hexColorPattern.exec(fnString);
  }

  // Normal tokenization
  const regex =
    // eslint-disable-next-line no-useless-escape
    /\#\d+|[(),?;&.'":()+\-*/.!]|<=|<|>|>=|!=|==|[||]{2}|=>|__HEX_COLOR_[0-9]+__|\w+| /g;
  const tokens = modifiedString.match(regex) || [];

  // Restore hex colors
  return tokens.map((token) => {
    const hexColor = hexColors.find((hc) => hc.placeholder === token);
    return hexColor ? hexColor.value : token;
  });
};

/**
 * Handles numeric values by removing quotes and trimming whitespace.
 * It uses a regular expression to check if the value is numeric.
 * If the value is numeric, it returns the trimmed value without quotes.
 * Otherwise, it returns the original value.
 * @param {*} val
 * @returns
 */
const handeNumericValue = (val) => {
  const regex = /^"\d+"$|^\d+$/;
  const isNumeric = regex.test(val);
  if (isNumeric) {
    return String(val).trim().replace(/['"]/g, '');
  }
  return val;
};

/**
 * Generates the function body by replacing placeholders with actual values.
 * It handles hex color codes, numeric values, and string values.
 * The function uses a regular expression to check if the processed string
 * matches a valid numeric format. If it does, it returns the generated function body.
 * If not, it returns a default value based on the original function string.
 * @param {*} fnMetadata
 * @param {*} values
 * @param {*} questions
 * @returns
 */
const generateFnBody = (fnMetadata, values, questions = []) => {
  if (!fnMetadata) {
    return false;
  }

  // Create a map of question names to IDs for faster lookup
  const questionMap = {};
  if (questions && questions.length) {
    questions.forEach((q) => {
      if (q.name && q.id) {
        questionMap[q.name] = q.id;
      }
    });
  }

  let defaultVal = null;
  // Replace variables with numeric placeholders
  let processedString = fnMetadata;
  // Iterate over keys of the values object and replace placeholders with '0'
  Object.keys(values).forEach((key) => {
    processedString = processedString.replace(new RegExp(`#${key}#`, 'g'), '0');
  });

  // Check if the processed string matches the regular expression
  const validNumericRegex = /^[\d\s+\-*/().]*$/;
  if (!validNumericRegex.test(processedString)) {
    // update defaultVal into empty string for non numeric equation
    defaultVal = fnMetadata.includes('!') ? String(null) : '';
  }

  const fnMetadataTemp = fnToArray(fnMetadata);

  // generate the fnBody
  const fnBody = fnMetadataTemp.map((f) => {
    // First check for literal hex color codes in quotes - don't process them
    if (f.startsWith('"#') && f.endsWith('"') && /^"#[0-9A-Fa-f]{6}"$/.test(f)) {
      return f; // Return hex color as-is
    }
    // Check if the token is a number or a string
    if (questionMap?.[f]) {
      let val = values?.[questionMap[f]];

      if (!val && val !== 0) {
        return defaultVal;
      }
      if (typeof val === 'object') {
        if (Array.isArray(val)) {
          val = val.join(',');
        } else if (val?.lat) {
          val = `${val.lat},${val.lng}`;
        } else {
          val = defaultVal;
        }
      }
      if (typeof val === 'number') {
        val = Number(val);
      }
      if (typeof val === 'string') {
        val = `"${val}"`;
      }

      return val;
    }
    return f;
  });

  // all fn conditions meet, return generated fnBody
  if (!fnBody.filter((x) => !x).length) {
    return fnBody
      .map(handeNumericValue)
      .join('')
      .replace(/(?:^|\s)\.includes\(['"][^'"]+['"]\)/g, "''$1")
      .replace(/''\s*\./g, "''.");
  }

  // remap fnBody if only one fnBody meet the requirements
  return fnBody
    .filter((x) => x)
    .map(handeNumericValue)
    .join('')
    .replace(/(?:^|\s)\.includes\(['"][^'"]+['"]\)/g, " ''$&")
    .replace(/''\s*\./g, "''.");
};

/**
 * Function to fix incomplete math operations in a string expression.
 * It checks if the expression ends with an incomplete math operation
 * (e.g., '+', '-', '*', '/') and appends '0' to complete the operation.
 * If the expression ends with '*' or '/', it removes the operator.
 * @param {string} expression - The string expression to be fixed.
 * @returns
 */
const fixIncompleteMathOperation = (expression) => {
  // Regular expression to match incomplete math operations
  const incompleteMathRegex = /[+\-*/]\s*$/;

  // Check if the input ends with an incomplete math operation
  if (incompleteMathRegex.test(expression)) {
    // If the expression ends with '+' or '-', append '0' to complete the operation
    if (expression.trim().endsWith('+') || expression.trim().endsWith('-')) {
      return `${expression.trim()}0`;
    }
    // If the expression ends with '*' or '/', it's safer to remove the operator
    if (expression.trim().endsWith('*') || expression.trim().endsWith('/')) {
      return expression.trim().slice(0, -1);
    }
  }
  return expression;
};
/**
 * Function to convert a function string into an actual function.
 * It sanitizes the function string, generates the function body,
 * and creates a new function using the Function constructor.
 * If an error occurs during the process, it returns null.
 * @param {string} fnString - The function string to be converted.
 * @param {object} values - An object containing values to be used in the function.
 * @param {array} questions - An array of question objects to be used in the function.
 * @returns {function|null} - The generated function or null if an error occurs.
 * @throws {Error} - Throws an error if the function string is invalid or if the function cannot be created.
 */
export const strToFunction = (fnString, values, questions = []) => {
  try {
    const fnStr = checkDirty(fnString);
    const fnBody = fixIncompleteMathOperation(generateFnBody(fnStr, values, questions));
    // eslint-disable-next-line no-new-func
    return new Function(`return ${fnBody}`);
  } catch {
    return null;
  }
};

export const transformAnswers = (answersObj, formJSON) => {
  const answers = {};
  if (answersObj && typeof answersObj === 'object') {
    Object.entries(answersObj).forEach(([key, val]) => {
      if (val === undefined || val === null) return;
      const [questionId] = key.split('-');
      const question = formJSON.question_group
        .flatMap((group) => group.question)
        .find((q) => `${q.id}` === questionId);
      answers[key] = val;
      if (question?.type === 'cascade' && Array.isArray(val) && val.length) {
        const [lastValue] = val.slice(-1);
        answers[key] = lastValue;
      }
      if (question?.type === 'number') {
        answers[key] = parseFloat(val);
      }
    });
  }
  return answers;
};
