import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { View } from 'react-native';
import { useRoute } from '@react-navigation/native';
import * as Crypto from 'expo-crypto';
import { BaseLayout } from '../components';
import { FormNavigation, QuestionGroupList } from './support';
import QuestionGroup from './components/QuestionGroup';
import { transformForm, generateDataPointName } from './lib';
import { FormState } from '../store';
import { helpers } from '../lib';
import { SUBMISSION_TYPES } from '../lib/constants';

// TODO:: Allow other not supported yet

const checkValuesBeforeCallback = ({ values, hiddenQIds = [] }) =>
  Object.keys(values)
    .filter((key) => {
      // remove value where question is hidden
      if (hiddenQIds.includes(Number(key))) {
        return false;
      }
      // EOL remove value where question is hidden
      let value = values[key];
      if (typeof value === 'string') {
        value = value.trim();
      }
      // check array
      if (value && Array.isArray(value)) {
        const check = value.filter(
          (y) => typeof y !== 'undefined' && (y || Number.isNaN(Number(y))),
        );
        value = check.length ? check : null;
      }
      // check empty
      if (!value && value !== 0) {
        return false;
      }
      return true;
    })
    .map((key) => {
      const value = values[key];
      return { [key]: value };
    })
    .reduce((res, current) => ({ ...res, ...current }), {});

const style = {
  flex: 1,
};

const FormContainer = ({ forms = {}, onSubmit, setShowDialogMenu }) => {
  const [activeGroup, setActiveGroup] = useState(0);
  const [showQuestionGroupList, setShowQuestionGroupList] = useState(false);
  const [isDefaultFilled, setIsDefaultFilled] = useState(false);
  const currentValues = FormState.useState((s) => s.currentValues);
  const cascades = FormState.useState((s) => s.cascades);
  const activeLang = FormState.useState((s) => s.lang);
  const repeats = FormState.useState((s) => s.repeats);
  const prevAdmAnswer = FormState.useState((s) => s.prevAdmAnswer);
  const route = useRoute();

  const dependantQuestions =
    forms?.question_group
      ?.flatMap((qg) => qg.question)
      .filter((q) => q?.dependency && q?.dependency?.length)
      ?.map((q) => ({ id: q.id, dependency: q.dependency })) || [];

  const formDefinition = transformForm(
    forms,
    currentValues,
    activeLang,
    route.params.submission_type,
    repeats,
    prevAdmAnswer,
  );
  const activeQuestions = formDefinition?.question_group?.flatMap((qg) => qg?.question);
  const currentGroup = useMemo(
    () => formDefinition?.question_group?.[activeGroup],
    [activeGroup, formDefinition?.question_group],
  );

  const hiddenQIds = useMemo(
    () =>
      forms?.question_group
        ?.flatMap((qg) => qg?.question)
        .map((q) => {
          const subTypeName = helpers.flipObject(SUBMISSION_TYPES)?.[route.params.submission_type];
          const hidden = q?.hidden ? q.hidden?.submission_type?.includes(subTypeName) : false;
          if (hidden) {
            return q.id;
          }
          return false;
        })
        .filter((x) => x),
    [forms, route.params.submission_type],
  );

  const handleOnSubmitForm = () => {
    // Use currentValues directly as our base to ensure we preserve all values
    const reIndexedValues = { ...currentValues };

    // Find all questions that belong to repeatable groups
    const repeatableGroups = formDefinition?.question_group?.filter((qg) => qg.repeatable) || [];

    // Process each repeatable question group
    repeatableGroups.forEach((group) => {
      const groupId = group.id || group.name;
      const groupRepeats = repeats[groupId] || [0];

      if (!groupRepeats || groupRepeats.length <= 1) {
        // No repeats to re-index
        return;
      }

      // Get all questions in this group
      const questions = group.question || [];

      // Process each question in the repeatable group
      questions.forEach((question) => {
        const questionId = question.id;

        // Find all repeat instances of this question in currentValues
        // This would match both `123` and `123-0`, `123-1`, etc.
        const questionEntries = Object.entries(currentValues)
          .filter(([key]) => {
            const [qId, repeatIndex] = key.includes('-') ? key.split('-') : [key, null];
            return qId === `${questionId}` && repeatIndex !== null;
          })
          .sort(([keyA], [keyB]) => {
            // Sort by repeat index
            const [, indexA] = keyA.split('-');
            const [, indexB] = keyB.split('-');
            return parseInt(indexA, 10) - parseInt(indexB, 10);
          });

        // If there are entries to re-index
        if (questionEntries.length > 0) {
          // First, remove all the existing entries from reIndexedValues
          questionEntries.forEach(([key]) => {
            delete reIndexedValues[key];
          });

          // Now add back the entries with sequential indices
          // Skip index 0 in groupRepeats as it's the base non-repeat
          const repeatsExcludingBase = groupRepeats.slice(1);

          // Map each actual repeat value to a new sequential index
          repeatsExcludingBase.forEach((actualIndex, newIndex) => {
            // Find the matching entry for this repeat
            questionEntries.forEach(([key, value]) => {
              const [baseId, repeatIndex] = key.split('-');
              if (parseInt(repeatIndex, 10) === actualIndex) {
                // Re-add with a sequential index
                reIndexedValues[`${baseId}-${newIndex + 1}`] = value;
              }
            });
          });
        }
      });
    });

    // Filter and process values as before, but with the re-indexed values
    const validValues = Object.keys(reIndexedValues)
      .filter((key) => {
        const [questionId] = `${key}`.split('-');
        return activeQuestions.map((q) => `${q.id}`).includes(questionId);
      })
      .reduce((prev, current) => ({ ...prev, [current]: reIndexedValues[current] }), {});

    const results = checkValuesBeforeCallback({ values: validValues, hiddenQIds });
    if (onSubmit) {
      const { dpName, dpGeo } = generateDataPointName(forms, validValues, cascades);
      onSubmit({ name: dpName, geo: dpGeo, answers: results });
    }
  };

  const handleOnActiveGroup = (page) => {
    const group = formDefinition?.question_group?.[page];
    const currentPrefilled = group.question
      ?.filter((q) => q?.pre && q?.id)
      ?.filter(
        (q) => currentValues?.[q.id] === null || typeof currentValues?.[q.id] === 'undefined',
      )
      ?.map((q) => {
        const questionName = Object.keys(q.pre)?.[0];
        const findQuestion = activeQuestions.find((aq) => aq?.name === questionName);
        const prefillValue = q.pre?.[questionName]?.[currentValues?.[findQuestion?.id]];
        return { [q.id]: prefillValue };
      })
      ?.reduce((prev, current) => ({ ...prev, ...current }), {});
    if (Object.keys(currentPrefilled).length) {
      FormState.update((s) => {
        s.loading = true;
        s.currentValues = {
          ...s.currentValues,
          ...currentPrefilled,
        };
      });
      const interval = group?.question?.length || 0;
      setTimeout(() => {
        setActiveGroup(page);
        FormState.update((s) => {
          s.loading = false;
        });
      }, interval);
    } else {
      setActiveGroup(page);
    }
  };

  const handleOnDefaultValue = useCallback(() => {
    if (!isDefaultFilled) {
      setIsDefaultFilled(true);
      const defaultValues = activeQuestions
        .filter((aq) => aq?.default_value || aq?.meta_uuid)
        .map((aq) => {
          if (aq?.meta_uuid) {
            const UUID = Crypto.randomUUID();
            return {
              [aq.id]: UUID,
            };
          }
          const submissionType = route.params?.submission_type || SUBMISSION_TYPES.registration;
          const subTypeName = helpers.flipObject(SUBMISSION_TYPES)[submissionType];
          const defaultValue = aq?.default_value?.submission_type?.[subTypeName];
          if (['option', 'multiple_option'].includes(aq.type)) {
            return {
              [aq.id]: defaultValue ? [defaultValue] : [],
            };
          }
          return {
            [aq.id]: defaultValue || Number(defaultValue) === 0 ? defaultValue : '',
          };
        })
        .reduce((prev, current) => ({ ...prev, ...current }), {});
      if (Object.keys(defaultValues).length) {
        FormState.update((s) => {
          s.currentValues = { ...s.currentValues, ...defaultValues };
        });
      }
    }
  }, [activeQuestions, route.params, isDefaultFilled]);

  useEffect(() => {
    handleOnDefaultValue();
  }, [handleOnDefaultValue]);

  return (
    <>
      <BaseLayout.Content>
        <View style={style}>
          {!showQuestionGroupList ? (
            <QuestionGroup
              index={activeGroup}
              group={currentGroup}
              activeQuestions={activeQuestions}
              dependantQuestions={dependantQuestions}
            />
          ) : (
            <QuestionGroupList
              form={formDefinition}
              activeQuestionGroup={activeGroup}
              setActiveQuestionGroup={setActiveGroup}
              setShowQuestionGroupList={setShowQuestionGroupList}
            />
          )}
        </View>
      </BaseLayout.Content>
      <View>
        <FormNavigation
          currentGroup={currentGroup}
          onSubmit={handleOnSubmitForm}
          activeGroup={activeGroup}
          setActiveGroup={handleOnActiveGroup}
          totalGroup={formDefinition?.question_group?.length || 0}
          showQuestionGroupList={showQuestionGroupList}
          setShowQuestionGroupList={setShowQuestionGroupList}
          setShowDialogMenu={setShowDialogMenu}
        />
      </View>
    </>
  );
};

export default FormContainer;
