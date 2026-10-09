import React, { useState, useEffect } from 'react';
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

/**
 * Schema-based counter that mirrors the Submit gate (validateAllGroups in
 * FormNavigation). A required question counts as "filled" only if it passes the
 * same Yup field-level schema used at submit time, so reaching totalFilled ===
 * totalRequired guarantees the form is actually submittable.
 *
 * groupsValid drives the per-group check marks from the same results, so a group
 * holding a present-but-invalid answer (e.g. a decimal in an integer field, or a
 * non-numeric phone number) is never ticked while the header still reports it as
 * missing.
 */
export const countValidRequiredQuestions = async (form, values) => {
  // Extract all questions for recursive dependency checking
  const allQuestions = form.question_group.flatMap((qg) => qg.question).filter((q) => q);

  let totalRequired = 0;
  const validations = [];
  const groupIndexes = [];
  form.question_group.forEach((questionGroup, groupIndex) => {
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
      groupIndexes.push(groupIndex);
    });
  });

  const results = await Promise.allSettled(validations);
  const groupsValid = form.question_group.map(() => true);
  let totalFilled = 0;
  results.forEach(({ status, value }, i) => {
    if (status === 'fulfilled' && Object.values(value || {})[0] === true) {
      totalFilled += 1;
    } else {
      groupsValid[groupIndexes[i]] = false;
    }
  });

  return { totalFilled, totalRequired, groupsValid };
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

  const handleOnPress = (questionGroupIndex) => {
    setActiveQuestionGroup(questionGroupIndex);
    setShowQuestionGroupList(false);
  };

  const dataPointNameText = generateDataPointName(forms, currentValues, cascades)?.dpName;
  // groupsValid stays null until the first validation run, so no group is marked
  // complete or erroneous before its answers have actually been checked.
  const [requiredCount, setRequiredCount] = useState({
    totalFilled: 0,
    totalRequired: 0,
    groupsValid: null,
  });
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
  const { totalFilled, totalRequired, groupsValid } = requiredCount;

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
              !!groupsValid?.[qx] && visitedQuestionGroup.includes(questionGroup.id)
            }
            hasErrors={!!groupsValid && !groupsValid[qx]}
            visited={visitedQuestionGroup.includes(questionGroup.id)}
            onPress={() => handleOnPress(qx)}
          />
        ))}
      </ScrollView>
    </View>
  );
};

export default QuestionGroupList;
