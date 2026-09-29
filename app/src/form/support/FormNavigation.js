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

  const getFirstErrorMessage = (feedback) => {
    const [questionID, errorMessage] = Object.entries(feedback).find(([, value]) => value !== true);
    const question = currentGroup.question.find((q) => q?.id === parseInt(questionID, 10));
    return errorMessage.replace('this', question?.label);
  };

  const validateAllGroups = async () => {
    if (!formDefinition?.question_group) {
      return true;
    }

    const allGroups = formDefinition.question_group;
    const allQuestions = allGroups.flatMap((qg) => qg.question).filter((q) => q);

    const validationPromises = allGroups.map(async (group) => {
      const validateSync = group.question
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
        });

      if (!validateSync || validateSync.length === 0) {
        return { valid: true, feedback: {} };
      }

      const validations = await Promise.allSettled(validateSync);
      const feedbackValues = validations
        ?.filter(({ status }) => status === 'fulfilled')
        .map(({ value }) => value)
        .reduce((acc, obj) => ({ ...acc, ...obj }), {});
      const errors = Object.values(feedbackValues).filter((val) => val !== true);

      return { valid: errors.length === 0, feedback: feedbackValues };
    });

    const results = await Promise.all(validationPromises);
    const allFeedback = results.reduce((acc, r) => ({ ...acc, ...r.feedback }), {});
    FormState.update((s) => {
      s.feedback = { ...s.feedback, ...allFeedback };
    });
    return results.every((r) => r.valid);
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

    const allQuestions =
      formDefinition?.question_group?.flatMap((qg) => qg.question).filter((q) => q) || [];

    const validateSync =
      currentGroup?.question
        ?.filter((q) => onFilterDependency(currentGroup, currentValues, q, 0, allQuestions))
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
    const feedbackList = validations
      ?.filter(({ status }) => status === 'fulfilled')
      .map(({ value }) => value);
    const feedbackValues = feedbackList.reduce((acc, obj) => {
      const key = Object.keys(obj)[0];
      const value = obj[key];
      acc[key] = value;
      return acc;
    }, {});
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
      const allGroupsValid = await validateAllGroups();
      if (allGroupsValid) {
        await onSubmit();
      } else {
        ToastAndroid.show(
          trans.completeAllRequiredFields ||
            'Please complete all required fields in all sections before submitting',
          ToastAndroid.LONG,
        );
      }
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
