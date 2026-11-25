import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ToastAndroid,
  ActivityIndicator,
} from 'react-native';
import { UIState, FormState } from '../../store';
import i18n from '../../lib/i18n';
import { generateValidationSchemaFieldLevel, onFilterDependency } from '../lib';
import useTheme from '../../lib/theme';

const FormNavigation = ({
  currentGroup,
  formDefinition,
  onSubmit,
  activeGroup,
  setActiveGroup,
  totalGroup,
  showQuestionGroupList,
  setShowDialogMenu,
}) => {
  const theme = useTheme();
  const [submitting, setSubmitting] = useState(false);
  const visitedQuestionGroup = FormState.useState((s) => s.visitedQuestionGroup);
  const currentValues = FormState.useState((s) => s.currentValues);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  const handleOnUpdateState = (activeValue) => {
    const updateVisitedQuestionGroup = [...visitedQuestionGroup, ...[activeValue]];
    FormState.update((s) => {
      s.visitedQuestionGroup = [...new Set(updateVisitedQuestionGroup)];
    });
  };

  // Extract all questions for recursive dependency checking
  const allQuestions =
    formDefinition?.question_group?.flatMap((qg) => qg.question).filter((q) => q) || [];

  const getFirstErrorMessage = (feedback, group = currentGroup) => {
    const [questionID, errorMessage] = Object.entries(feedback).find(([, value]) => value !== true);
    const question = group?.question?.find((q) => `${q?.id}` === `${questionID}`);
    return errorMessage.replace('this', question?.label);
  };

  /**
   * Field-level feedback for one group's visible questions:
   * { [questionId]: true | errorMessage }.
   */
  const validateGroup = async (group) => {
    const validateSync =
      group?.question
        ?.filter((q) => onFilterDependency(group, currentValues, q, 0, allQuestions))
        ?.filter((q) => q?.extra?.type !== 'entity' || currentValues?.[q?.id] !== undefined)
        ?.map((q) => {
          const defaultVal = [
            'cascade',
            'multiple_option',
            'option',
            'geo',
            'geoshape',
            'geotrace',
          ].includes(q?.type)
            ? null
            : '';
          const fieldValue =
            currentValues?.[q?.id] === undefined ? defaultVal : currentValues[q.id];
          return generateValidationSchemaFieldLevel(fieldValue, q);
        }) || [];
    const validations = await Promise.allSettled(validateSync);
    return validations
      .filter(({ status }) => status === 'fulfilled')
      .reduce((acc, { value }) => ({ ...acc, ...value }), {});
  };

  /**
   * The first group (in form order) holding an unanswered or invalid answer, with
   * its feedback, or null when the whole form is submittable.
   */
  const findFirstInvalidGroup = async () => {
    const groups = formDefinition?.question_group || [];
    const feedbacks = await Promise.all(groups.map((group) => validateGroup(group)));
    const groupIndex = feedbacks.findIndex((feedback) =>
      Object.values(feedback).some((val) => val !== true),
    );
    return groupIndex === -1 ? null : { groupIndex, feedback: feedbacks[groupIndex] };
  };

  /**
   * Blocks submission and takes the user to the problem: opens the first failing
   * group with its field errors shown. "Complete all required fields" is only true
   * when an answer is missing — a filled-in but invalid answer (e.g. 2.5 in a
   * whole-number field) gets its own message instead.
   */
  const handleInvalidSubmit = ({ groupIndex, feedback }) => {
    const group = formDefinition.question_group[groupIndex];
    const isRequired = Object.values(feedback).some(
      (val) => val !== true && val.includes('required'),
    );
    FormState.update((s) => {
      s.feedback = feedback;
    });
    if (groupIndex !== activeGroup) {
      setActiveGroup(groupIndex);
    }
    ToastAndroid.show(
      isRequired
        ? trans.completeAllRequiredFields ||
            'Please complete all required fields in all sections before submitting'
        : `${group?.label}: ${getFirstErrorMessage(feedback, group)}`,
      ToastAndroid.LONG,
    );
  };

  const handleBack = async () => {
    if (showQuestionGroupList) {
      return;
    }
    if (!activeGroup) {
      setShowDialogMenu(true);
      return;
    }
    const activeValue = activeGroup - 1;
    setActiveGroup(activeValue);
    handleOnUpdateState(activeValue);
  };

  const handleNext = async () => {
    if (showQuestionGroupList) {
      return;
    }

    const feedbackValues = await validateGroup(currentGroup);
    const errors = Object.values(feedbackValues).filter((val) => val !== true);

    if (errors.length > 0 && activeGroup < totalGroup - 1) {
      const isRequired = errors.find((e) => e.includes('required'));
      const errorMessage = isRequired
        ? trans.mandatoryQuestionsWarning || trans.mandatoryQuestions
        : getFirstErrorMessage(feedbackValues);
      ToastAndroid.show(errorMessage, ToastAndroid.SHORT);
    }
    FormState.update((s) => {
      s.feedback = feedbackValues;
    });

    if (currentGroup?.id && !visitedQuestionGroup.includes(currentGroup.id)) {
      FormState.update((s) => {
        s.visitedQuestionGroup = [...visitedQuestionGroup, currentGroup.id];
      });
    }

    if (activeGroup < totalGroup - 1) {
      setActiveGroup(activeGroup + 1);
    }
  };

  const handleSubmit = async () => {
    if (submitting) {
      return;
    }
    setSubmitting(true);
    try {
      const invalidGroup = await findFirstInvalidGroup();
      if (invalidGroup) {
        handleInvalidSubmit(invalidGroup);
        return;
      }
      await onSubmit();
    } finally {
      setSubmitting(false);
    }
  };

  const isOverviewStep = activeGroup === totalGroup - 1;

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: theme.bg.surfaceElevated3, borderTopColor: theme.border.listDivider },
      ]}
    >
      <TouchableOpacity
        style={styles.backButton}
        onPress={handleBack}
        disabled={showQuestionGroupList || submitting}
        testID="form-nav-btn-back"
      >
        <Text style={[styles.backText, { color: theme.buttonGhost.color }]}>
          {trans.buttonBack}
        </Text>
      </TouchableOpacity>

      {isOverviewStep ? (
        <TouchableOpacity
          style={[styles.nextButton, { backgroundColor: theme.buttonPrimary.bg }]}
          onPress={handleSubmit}
          disabled={submitting}
          testID="form-btn-submit"
        >
          {submitting ? (
            <ActivityIndicator color={theme.buttonPrimary.text} testID="form-btn-submit-loading" />
          ) : (
            <Text style={[styles.nextText, { color: theme.buttonPrimary.text }]}>
              {trans.buttonSubmit}
            </Text>
          )}
        </TouchableOpacity>
      ) : (
        <TouchableOpacity
          style={[styles.nextButton, { backgroundColor: theme.buttonPrimary.bg }]}
          onPress={handleNext}
          disabled={showQuestionGroupList}
          testID="form-nav-btn-next"
        >
          <Text style={[styles.nextText, { color: theme.buttonPrimary.text }]}>
            {trans.buttonNext}
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  backButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
  },
  backText: {
    fontSize: 18,
    fontWeight: '600',
  },
  nextButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 16,
  },
  nextText: {
    fontSize: 18,
    fontWeight: '600',
  },
});

export default FormNavigation;
