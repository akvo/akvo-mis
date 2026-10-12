import React from 'react';
import { ToastAndroid } from 'react-native';
import { Tab } from '@rneui/themed';
import styles from '../styles';
import { UIState, FormState } from '../../store';
import i18n from '../../lib/i18n';
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
        /**
         * Only ENTITY cascades are gated here. `extra.type` is a cascade sub-type, so
         * the old `|| !q?.extra?.type` clause also excluded administration cascades —
         * a required one was never validated, and the form submitted without it.
         */
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
    // Submit stays pressable while the group list is open; close it so the field
    // errors are actually on screen.
    setShowQuestionGroupList(false);
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

  const handleFormNavigation = async (index) => {
    // index 0 = prev group
    // index 1 = show question group list
    // index 2 = next group
    const feedbackValues = await validateGroup(currentGroup);
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
      const invalidGroup = await findFirstInvalidGroup();
      if (invalidGroup) {
        handleInvalidSubmit(invalidGroup);
        return;
      }
      onSubmit();
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
