import React from 'react';
import { ToastAndroid } from 'react-native';
import { Tab } from '@rneui/themed';
import styles from '../styles';
import { UIState, FormState } from '../../store';
import { i18n } from '../../lib';
import { generateValidationSchemaFieldLevel, onFilterDependency } from '../lib';

const FormNavigation = ({
  currentGroup,
  formDefinition,
  onSubmit,
  activeGroup,
  setActiveGroup,
  totalGroup,
  showQuestionGroupList,
  setShowQuestionGroupList,
  setShowDialogMenu,
}) => {
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
    // Extract all questions for recursive dependency checking
    const allQuestions = allGroups.flatMap((qg) => qg.question).filter((q) => q);

    const validationPromises = allGroups.map(async (group) => {
      const validateSync = group.question
        ?.filter((q) => onFilterDependency(group, currentValues, q, 0, allQuestions))
        /**
         * Only ENTITY cascades are gated here. `extra.type` is a cascade sub-type, so
         * the old `|| !q?.extra?.type` clause also excluded administration cascades —
         * a required one was never validated, and the form submitted without it.
         */
        ?.filter((q) => q?.extra?.type !== 'entity' || currentValues?.[q?.id] !== undefined)
        ?.map((q) => {
          const defaultVal = ['cascade', 'multiple_option', 'option', 'geo'].includes(q?.type)
            ? null
            : '';
          const fieldValue =
            currentValues?.[q?.id] === undefined ? defaultVal : currentValues[q.id];
          return generateValidationSchemaFieldLevel(fieldValue, q);
        });

      if (!validateSync || validateSync.length === 0) {
        return true;
      }

      const validations = await Promise.allSettled(validateSync);
      const errors = validations
        ?.filter(({ status }) => status === 'fulfilled')
        .map(({ value }) => Object.values(value))
        .flat()
        .filter((val) => val !== true);

      return errors.length === 0;
    });

    const results = await Promise.all(validationPromises);
    return results.every((valid) => valid);
  };

  const handleFormNavigation = async (index) => {
    // index 0 = prev group
    // index 1 = show question group list
    // index 2 = next group
    // Extract all questions for recursive dependency checking
    const allQuestions =
      formDefinition?.question_group?.flatMap((qg) => qg.question).filter((q) => q) || [];

    const validateSync =
      currentGroup?.question
        ?.filter((q) => onFilterDependency(currentGroup, currentValues, q, 0, allQuestions))
        /**
         * Only ENTITY cascades are gated, because they depend on options and
         * prevAdmAnswer. `extra.type` is a cascade sub-type, so the old
         * `|| !q?.extra?.type` clause also excluded administration cascades — a required
         * one was never validated here, and the group passed without it.
         */
        ?.filter((q) => q?.extra?.type !== 'entity' || currentValues?.[q?.id] !== undefined)
        ?.map((q) => {
          const defaultVal = ['cascade', 'multiple_option', 'option', 'geo'].includes(q?.type)
            ? null
            : '';
          /**
           * Set default value when the answer is undefined
           */
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
    // Show warning but allow navigation to next group
    if (errors.length > 0 && index === 2 && activeGroup < totalGroup - 1) {
      const isRequired = errors.find((e) => e.includes('required'));
      const errorMessage = isRequired
        ? trans.mandatoryQuestionsWarning || trans.mandatoryQuestions
        : getFirstErrorMessage(feedbackValues);
      ToastAndroid.show(errorMessage, ToastAndroid.SHORT);
    }
    FormState.update((s) => {
      s.feedback = feedbackValues;
    });

    // No longer block navigation - allow moving to next group even with errors
    if (currentGroup?.id && !visitedQuestionGroup.includes(currentGroup.id)) {
      FormState.update((s) => {
        s.visitedQuestionGroup = [...visitedQuestionGroup, currentGroup.id];
      });
    }

    if (index === 0) {
      if (activeGroup > 0) {
        setActiveGroup(activeGroup - 1);
      }
      if (!activeGroup) {
        setShowDialogMenu(true);
      } else {
        const activeValue = activeGroup - 1;
        setActiveGroup(activeValue);
        handleOnUpdateState(activeValue);
      }
      return;
    }
    if (index === 1) {
      setShowQuestionGroupList(!showQuestionGroupList);
      return;
    }
    if (index === 2 && activeGroup < totalGroup - 1) {
      setActiveGroup(activeGroup + 1);
    }
    if (index === 2 && activeGroup === totalGroup - 1) {
      // Validate all groups before submitting
      const allGroupsValid = await validateAllGroups();
      if (allGroupsValid) {
        onSubmit();
      } else {
        ToastAndroid.show(
          trans.completeAllRequiredFields ||
            'Please complete all required fields in all sections before submitting',
          ToastAndroid.LONG,
        );
      }
    }
  };

  return (
    <Tab
      buttonStyle={styles.formNavigationButton}
      onChange={handleFormNavigation}
      disableIndicator
      value={activeGroup}
    >
      <Tab.Item
        title={trans.buttonBack}
        icon={{ name: 'chevron-back-outline', type: 'ionicon', color: 'grey', size: 20 }}
        iconPosition="left"
        iconContainerStyle={styles.formNavigationIcon}
        titleStyle={styles.formNavigationTitle}
        testID="form-nav-btn-back"
        disabled={showQuestionGroupList}
        disabledStyle={{ backgroundColor: 'transparent' }}
        containerStyle={styles.formNavigationBgLight}
      />
      <Tab.Item
        title={`${activeGroup + 1}/${totalGroup}`}
        titleStyle={styles.formNavigationGroupCount}
        testID="form-nav-group-count"
        containerStyle={styles.formNavigationBgLight}
      />
      {activeGroup < totalGroup - 1 ? (
        <Tab.Item
          title={trans.buttonNext}
          icon={{ name: 'chevron-forward-outline', type: 'ionicon', color: 'grey', size: 20 }}
          iconPosition="right"
          iconContainerStyle={styles.formNavigationIcon}
          titleStyle={styles.formNavigationTitle}
          testID="form-nav-btn-next"
          disabled={showQuestionGroupList}
          disabledStyle={{ backgroundColor: 'transparent' }}
          containerStyle={styles.formNavigationBgLight}
        />
      ) : (
        <Tab.Item
          title={trans.buttonSubmit}
          icon={{ name: 'paper-plane-outline', type: 'ionicon', color: 'white', size: 20 }}
          iconPosition="right"
          iconContainerStyle={styles.formNavigationIconSubmit}
          titleStyle={styles.formNavigationSubmit}
          containerStyle={styles.formNavigationBgPrimary}
          testID="form-btn-submit"
        />
      )}
    </Tab>
  );
};

export default FormNavigation;
