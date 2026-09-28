import React, { useMemo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { FormState } from '../../store';
import { onFilterDependency } from '../lib';
import useTheme from '../../lib/theme';

const formatValue = (value, question) => {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  if (Array.isArray(value)) {
    if (question?.option) {
      return value
        .map((v) => question.option.find((o) => o.value === v)?.label || v)
        .join(', ');
    }
    return value.filter((v) => v !== null && v !== undefined).join(', ');
  }
  if (question?.option) {
    return question.option.find((o) => o.value === value)?.label || value;
  }
  if (value instanceof Date) {
    return value.toLocaleDateString();
  }
  return String(value);
};

const FormOverview = ({ formDefinition, onEditGroup, onEditQuestion }) => {
  const theme = useTheme();
  const currentValues = FormState.useState((s) => s.currentValues);

  const allQuestions = useMemo(
    () =>
      formDefinition?.question_group?.flatMap((qg) => qg.question).filter((q) => q) || [],
    [formDefinition],
  );

  const groupSummaries = useMemo(() => {
    if (!formDefinition?.question_group) {
      return [];
    }
    return formDefinition.question_group.map((group, groupIndex) => {
      const visibleQuestions =
        group.question?.filter((q) =>
          onFilterDependency(group, currentValues, q, 0, allQuestions),
        ) || [];

      const questions = visibleQuestions.map((q) => {
        const value = currentValues?.[q.id];
        const displayValue = formatValue(value, q);
        const isEmpty = displayValue === null || displayValue === '';
        const isMissing = q.required && isEmpty;
        return {
          id: q.id,
          label: q.label || q.name,
          value: displayValue,
          required: q.required,
          isMissing,
        };
      });

      return {
        groupIndex,
        label: group.label || group.name,
        questions,
        hasMissing: questions.some((q) => q.isMissing),
      };
    });
  }, [formDefinition, currentValues, allQuestions]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer}>
      {groupSummaries.map((group) => (
        <View key={group.groupIndex} style={styles.groupSection}>
          <View style={styles.groupHeaderRow}>
            <Text style={[styles.groupLabel, { color: theme.text.primary }]}>
              {group.label}
            </Text>
            {group.hasMissing && (
              <TouchableOpacity
                style={[styles.editButton, { backgroundColor: theme.status.error }]}
                onPress={() => onEditGroup(group.groupIndex)}
                testID={`overview-edit-group-${group.groupIndex}`}
              >
                <Icon name="pencil" size={14} color="#FFFFFF" />
                <Text style={styles.editButtonText}>Edit</Text>
              </TouchableOpacity>
            )}
          </View>

          {group.questions.map((q) => (
            <TouchableOpacity
              key={q.id}
              style={[
                styles.questionRow,
                { borderBottomColor: theme.border.listDivider },
                q.isMissing && styles.missingRow,
              ]}
              onPress={() => onEditQuestion(group.groupIndex, q.id)}
              testID={`overview-edit-question-${q.id}`}
            >
              <View style={styles.questionInfo}>
                <Text
                  style={[
                    styles.questionLabel,
                    { color: q.isMissing ? theme.status.error : theme.text.secondary },
                  ]}
                  numberOfLines={2}
                >
                  {q.label}
                  {q.required && <Text style={{ color: theme.status.error }}> *</Text>}
                </Text>
                <Text
                  style={[
                    styles.questionValue,
                    {
                      color: q.value ? theme.text.primary : theme.text.tertiary,
                      fontStyle: q.value ? 'normal' : 'italic',
                    },
                  ]}
                  numberOfLines={2}
                >
                  {q.value || (q.isMissing ? 'Required' : 'Not answered')}
                </Text>
              </View>
              <Icon
                name="pencil"
                size={16}
                color={q.isMissing ? theme.status.error : theme.text.tertiary}
              />
            </TouchableOpacity>
          ))}
        </View>
      ))}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  contentContainer: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 48,
  },
  groupSection: {
    marginBottom: 20,
  },
  groupHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  groupLabel: {
    fontSize: 16,
    fontWeight: '600',
    flex: 1,
  },
  editButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    gap: 4,
  },
  editButtonText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  questionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderRadius: 8,
  },
  missingRow: {
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
    borderBottomWidth: 0,
    marginVertical: 2,
  },
  questionInfo: {
    flex: 1,
    gap: 2,
  },
  questionLabel: {
    fontSize: 13,
  },
  questionValue: {
    fontSize: 15,
    fontWeight: '500',
  },
});

export default FormOverview;
