import React, { useMemo, useState, useEffect } from 'react';
import { ScrollView, View } from 'react-native';
import { Text, Divider } from '@rneui/themed';
import QuestionGroupListItem from './QuestionGroupListItem';
import {
  onFilterDependency,
  generateDataPointName,
  generateValidationSchemaFieldLevel,
} from '../lib';
import styles from '../styles';
import { FormState } from '../../store';

export const checkCompleteQuestionGroup = (form, values) => {
  // Extract all questions for recursive dependency checking
  const allQuestions = form.question_group.flatMap((qg) => qg.question).filter((q) => q);

  return form.question_group.map((questionGroup) => {
    const filteredQuestions = questionGroup.question.filter((q) => q.required);
    return (
      filteredQuestions
        .map((question) => {
          if (question?.dependency) {
            // Use onFilterDependency with allQuestions for recursive ancestor checking
            if (!onFilterDependency(questionGroup, values, question, 0, allQuestions)) {
              return true; // Skip this question for completion check
            }
          }
          if (values?.[question.id] || values?.[question.id] === 0) {
            return true;
          }
          return false;
        })
        .filter((x) => x).length === filteredQuestions.length
    );
  });
};

/**
 * Schema-based counter that mirrors the Submit gate (validateAllGroups in
 * FormNavigation). A required question counts as "filled" only if it passes the
 * same Yup field-level schema used at submit time, so reaching totalFilled ===
 * totalRequired guarantees the form is actually submittable.
 */
export const countValidRequiredQuestions = async (form, values) => {
  // Extract all questions for recursive dependency checking
  const allQuestions = form.question_group.flatMap((qg) => qg.question).filter((q) => q);

  let totalRequired = 0;
  const validations = [];
  form.question_group.forEach((questionGroup) => {
    const requiredQuestions = questionGroup.question.filter((q) => q.required);
    requiredQuestions.forEach((question) => {
      // Skip dependent questions whose dependency is not currently satisfied
      if (
        question?.dependency &&
        !onFilterDependency(questionGroup, values, question, 0, allQuestions)
      ) {
        return;
      }
      // Mirror validateAllGroups: entity questions without a value are skipped
      // (their options depend on prevAdmAnswer and are not gated at submit).
      if (question?.extra?.type === 'entity' && values?.[question.id] === undefined) {
        return;
      }
      totalRequired += 1;
      const defaultVal = ['cascade', 'multiple_option', 'option', 'geo'].includes(question?.type)
        ? null
        : '';
      const fieldValue = values?.[question.id] === undefined ? defaultVal : values[question.id];
      validations.push(generateValidationSchemaFieldLevel(fieldValue, question));
    });
  });

  const results = await Promise.allSettled(validations);
  const totalFilled = results.filter(
    ({ status, value }) => status === 'fulfilled' && Object.values(value || {})[0] === true,
  ).length;

  return { totalFilled, totalRequired };
};

export const checkGroupHasErrors = (form, values) => {
  // Extract all questions for recursive dependency checking
  const allQuestions = form.question_group.flatMap((qg) => qg.question).filter((q) => q);

  return form.question_group.map((questionGroup) => {
    const requiredQuestions = questionGroup.question.filter((q) => q.required);
    const hasUnanswered = requiredQuestions.some((question) => {
      if (question?.dependency) {
        // Use onFilterDependency with allQuestions for recursive ancestor checking
        if (!onFilterDependency(questionGroup, values, question, 0, allQuestions)) {
          return false; // Skip dependent questions that don't match
        }
      }
      // Check if the question is unanswered
      const value = values?.[question.id];
      return !value && value !== 0;
    });
    return hasUnanswered;
  });
};

const QuestionGroupList = ({
  form,
  activeQuestionGroup,
  setActiveQuestionGroup,
  setShowQuestionGroupList,
}) => {
  const selectedForm = FormState.useState((s) => s.form);
  const currentValues = FormState.useState((s) => s.currentValues);
  const visitedQuestionGroup = FormState.useState((s) => s.visitedQuestionGroup);
  const cascades = FormState.useState((s) => s.cascades);
  const forms = selectedForm?.json ? JSON.parse(selectedForm.json) : {};

  const completedQuestionGroup = useMemo(
    () => checkCompleteQuestionGroup(form, currentValues),
    [form, currentValues],
  );

  const groupHasErrors = useMemo(
    () => checkGroupHasErrors(form, currentValues),
    [form, currentValues],
  );

  const handleOnPress = (questionGroupIndex) => {
    setActiveQuestionGroup(questionGroupIndex);
    setShowQuestionGroupList(false);
  };

  const dataPointNameText = generateDataPointName(forms, currentValues, cascades)?.dpName;
  const [requiredCount, setRequiredCount] = useState({ totalFilled: 0, totalRequired: 0 });
  useEffect(() => {
    let ignore = false;
    /**
     * Validating every required field (Yup schema) is expensive and currentValues
     * changes on each keystroke, so debounce the run. The `ignore` flag ensures
     * only the latest run commits its result and prevents setState after unmount;
     * clearTimeout drops the pending timer so it cannot leak past unmount.
     */
    const timer = setTimeout(() => {
      countValidRequiredQuestions(form, currentValues).then((res) => {
        if (!ignore) {
          setRequiredCount(res);
        }
      });
    }, 300);
    return () => {
      ignore = true;
      clearTimeout(timer);
    };
  }, [form, currentValues]);
  const { totalFilled, totalRequired } = requiredCount;

  return (
    <View style={styles.questionGroupListContainer}>
      <Text style={styles.questionGroupListFormTitle} testID="form-name">
        {form.name}
        {totalRequired ? ` (${totalFilled}/${totalRequired})` : ''}
      </Text>
      <Divider style={styles.divider} />
      {dataPointNameText && (
        <>
          <Text style={styles.questionGroupListDataPointName} testID="datapoint-name">
            {dataPointNameText}
          </Text>
          <Divider style={styles.divider} />
        </>
      )}
      <ScrollView>
        {form.question_group.map((questionGroup, qx) => (
          <QuestionGroupListItem
            key={questionGroup.id}
            label={questionGroup.label}
            active={activeQuestionGroup === qx}
            completedQuestionGroup={
              completedQuestionGroup[qx] && visitedQuestionGroup.includes(questionGroup.id)
            }
            hasErrors={groupHasErrors[qx]}
            visited={visitedQuestionGroup.includes(questionGroup.id)}
            onPress={() => handleOnPress(qx)}
          />
        ))}
      </ScrollView>
    </View>
  );
};

export default QuestionGroupList;
