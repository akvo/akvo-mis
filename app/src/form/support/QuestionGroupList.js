import React, { useEffect, useRef, useState } from 'react';
import {
  Animated,
  Dimensions,
  Modal,
  ScrollView,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { onFilterDependency, generateValidationSchemaFieldLevel } from '../lib';
import { i18n } from '../../lib';
import { FormState, UIState } from '../../store';
import useTheme from '../../lib/theme';

/**
 * Schema-based counter that mirrors the Submit gate (findFirstInvalidGroup in
 * FormNavigation). A required question counts as "filled" only if it passes the
 * same Yup field-level schema used at submit time, so reaching totalFilled ===
 * totalRequired guarantees the form is actually submittable.
 *
 * groupsValid drives the per-group check marks from the same results, so a group
 * holding a present-but-invalid answer (e.g. a decimal in an integer field, or a
 * non-numeric phone number) is never ticked while the header still reports it as
 * missing. `groups` gives the per-group filled/required tally shown on each sheet row.
 */
export const countValidRequiredQuestions = async (form, values) => {
  // Extract all questions for recursive dependency checking
  const allQuestions = form.question_group.flatMap((qg) => qg.question).filter((q) => q);

  let totalRequired = 0;
  const validations = [];
  const groupIndexes = [];
  const groups = form.question_group.map(() => ({ filled: 0, required: 0 }));
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
      // Mirror validateGroup: entity questions without a value are skipped
      // (their options depend on prevAdmAnswer and are not gated at submit).
      if (question?.extra?.type === 'entity' && values?.[question.id] === undefined) {
        return;
      }
      totalRequired += 1;
      groups[groupIndex].required += 1;
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
      groups[groupIndexes[i]].filled += 1;
    } else {
      groupsValid[groupIndexes[i]] = false;
    }
  });

  return { totalFilled, totalRequired, groupsValid, groups };
};

/**
 * Groups bottom-sheet (APP-598, screen 17). Lists the form's question groups by name so the
 * user can jump straight to any of them, with a filled/required tally in the header (all groups)
 * and on each row (that group). The active group is highlighted and badged "Current". The tally
 * is computed only while the sheet is open and mirrors the submit gate; submit is unchanged.
 */
const QuestionGroupList = ({
  form,
  activeQuestionGroup,
  setActiveQuestionGroup,
  setShowQuestionGroupList,
  visible = false,
}) => {
  const theme = useTheme();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const currentValues = FormState.useState((s) => s.currentValues);
  const groups = form?.question_group || [];
  const groupCount = groups.length;
  const currentNumber = Math.min(activeQuestionGroup + 1, groupCount);

  const [counts, setCounts] = useState({ totalFilled: 0, totalRequired: 0, groups: [] });
  // Validating every required field is expensive and only matters while the sheet is open, so
  // run it debounced and only when visible; `ignore` drops a stale run and prevents setState
  // after unmount.
  useEffect(() => {
    if (!visible) {
      return () => {};
    }
    let ignore = false;
    const timer = setTimeout(() => {
      countValidRequiredQuestions(form, currentValues).then((res) => {
        if (!ignore) {
          setCounts({
            totalFilled: res.totalFilled,
            totalRequired: res.totalRequired,
            groups: res.groups,
          });
        }
      });
    }, 250);
    return () => {
      ignore = true;
      clearTimeout(timer);
    };
  }, [visible, form, currentValues]);

  const handleOnPress = (questionGroupIndex) => {
    setActiveQuestionGroup(questionGroupIndex);
    setShowQuestionGroupList(false);
  };

  const onClose = () => setShowQuestionGroupList(false);

  // Backdrop fades in to cover the screen behind while the sheet slides up, instead of the
  // whole Modal (backdrop included) sliding from the bottom and leaving the top undimmed.
  const progress = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (visible) {
      Animated.timing(progress, {
        toValue: 1,
        duration: 220,
        useNativeDriver: true,
      }).start();
    } else {
      progress.setValue(0);
    }
  }, [visible, progress]);
  const translateY = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [Dimensions.get('window').height, 0],
  });

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={onClose}>
      <Animated.View style={[styles.backdrop, { opacity: progress }]}>
        <TouchableOpacity
          style={StyleSheet.absoluteFill}
          activeOpacity={1}
          onPress={onClose}
          testID="question-group-backdrop"
        />
      </Animated.View>
      <Animated.View
        style={[
          styles.sheet,
          { backgroundColor: theme.bg.surfacePrimary, transform: [{ translateY }] },
        ]}
      >
        <View style={[styles.grabber, { backgroundColor: theme.border.listDivider }]} />
        <View style={styles.sheetHeader}>
          <View style={styles.sheetHeaderText}>
            <Text style={[styles.sheetTitle, { color: theme.text.primary }]} testID="form-name">
              {trans.questionGroups || 'Question groups'}
              {counts.totalRequired ? ` (${counts.totalFilled}/${counts.totalRequired})` : ''}
            </Text>
            <Text style={[styles.sheetSubtitle, { color: theme.text.secondary }]}>
              {`${form?.name || ''} · ${trans.groupLabel || 'Group'} ${currentNumber} ${
                trans.ofLabel || 'of'
              } ${groupCount}`}
            </Text>
          </View>
          <TouchableOpacity
            onPress={onClose}
            style={styles.closeButton}
            accessibilityLabel={trans.buttonClose || 'Close'}
            testID="question-group-close"
          >
            <Icon name="close" size={22} color={theme.text.primary} />
          </TouchableOpacity>
        </View>
        <ScrollView>
          {groups.map((questionGroup, qx) => {
            const active = activeQuestionGroup === qx;
            const stats = counts.groups[qx];
            const complete = stats && stats.required > 0 && stats.filled >= stats.required;
            return (
              <TouchableOpacity
                key={questionGroup.id}
                testID="question-group-list-item-wrapper"
                onPress={() => handleOnPress(qx)}
                style={[
                  styles.item,
                  { borderBottomColor: theme.border.listDivider },
                  active && { backgroundColor: theme.bg.surfaceChip },
                ]}
              >
                <View style={styles.itemText}>
                  <Text
                    style={[
                      styles.itemLabel,
                      { color: theme.text.primary },
                      active && styles.itemLabelActive,
                    ]}
                    numberOfLines={3}
                  >
                    {`${qx + 1} · ${questionGroup.label}`}
                  </Text>
                  {stats && stats.required > 0 ? (
                    <Text
                      style={[
                        styles.itemCount,
                        { color: complete ? theme.status.success : theme.text.secondary },
                      ]}
                    >
                      {`${stats.filled}/${stats.required}`}
                    </Text>
                  ) : null}
                </View>
                {active ? (
                  <Text
                    style={[
                      styles.currentBadge,
                      { backgroundColor: theme.buttonPrimary.bg, color: theme.buttonPrimary.text },
                    ]}
                  >
                    {trans.currentLabel || 'Current'}
                  </Text>
                ) : (
                  <Icon name="chevron-forward" size={18} color={theme.text.secondary} />
                )}
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </Animated.View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(26,29,38,0.55)',
  },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    maxHeight: '80%',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 32,
  },
  grabber: {
    width: 40,
    height: 4,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 8,
  },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 52,
  },
  sheetHeaderText: {
    flex: 1,
    minWidth: 0,
  },
  sheetTitle: {
    fontSize: 20,
    fontWeight: '700',
  },
  sheetSubtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  closeButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: -8,
  },
  item: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginHorizontal: -12,
    borderRadius: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  itemText: {
    flex: 1,
    minWidth: 0,
  },
  itemLabel: {
    fontSize: 16,
    fontWeight: '500',
    lineHeight: 21,
  },
  itemCount: {
    fontSize: 13,
    fontWeight: '500',
    marginTop: 2,
  },
  itemLabelActive: {
    fontWeight: '700',
  },
  currentBadge: {
    fontSize: 12,
    fontWeight: '700',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    overflow: 'hidden',
  },
});

export default QuestionGroupList;
