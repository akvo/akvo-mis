/* eslint-disable react/jsx-props-no-spreading */
import React, { useRef, useMemo, useEffect, useCallback } from 'react';
import { View } from 'react-native';
import { KeyboardAwareScrollView } from 'react-native-keyboard-aware-scroll-view';

import QuestionField from './QuestionField';
import { RepeatSection } from '../support';
import { generateValidationSchemaFieldLevel } from '../lib';
import { FormState } from '../../store';
import getStyles from '../styles';
import useTheme from '../../lib/theme';

const QuestionGroup = ({ group, activeQuestions }) => {
  const theme = useTheme();
  const styles = getStyles(theme);
  const values = FormState.useState((s) => s.currentValues);
  const scrollToQuestionId = FormState.useState((s) => s.scrollToQuestionId);
  const scrollRef = useRef(null);
  const itemPositions = useRef({});

  // Prepare items for rendering
  const items = useMemo(() => {
    if (group?.repeatable && group.sections) {
      return group.sections.flatMap((section, sectionIndex) => {
        const sectionItems = [];
        if (section.repeatIndex > 0) {
          sectionItems.push({
            type: 'header',
            repeatIndex: section.repeatIndex,
            id: `header-${section.repeatIndex}`,
          });
        }
        return [
          ...sectionItems,
          ...section.data.map((item) => ({
            ...item,
            sectionIndex,
            sectionData: section.data,
          })),
        ];
      });
    }
    return (
      activeQuestions?.filter(
        (q) => q && (q.group_id === group?.id || q.group_name === group?.name),
      ) || []
    );
  }, [group, activeQuestions]);

  // Scroll to question when scrollToQuestionId changes
  useEffect(() => {
    if (!scrollToQuestionId) {
      return;
    }
    const tryScroll = (retries = 0) => {
      if (retries > 15) {
        FormState.update((s) => {
          s.scrollToQuestionId = null;
        });
        return;
      }
      const y = itemPositions.current[scrollToQuestionId];
      const scroll = scrollRef.current;
      if (y === undefined || !scroll) {
        setTimeout(() => tryScroll(retries + 1), 200);
        return;
      }
      scroll.scrollToPosition(0, y, true);
      FormState.update((s) => {
        s.scrollToQuestionId = null;
      });
    };
    setTimeout(() => tryScroll(0), 500);
  }, [scrollToQuestionId]);

  // Handle onChange for all questions
  const handleOnChange = useCallback((id, value, question) => {
    FormState.update((s) => {
      s.currentValues = { ...s.currentValues, [id]: value };
    });
    const currentFeedback = FormState.getRawState().feedback?.[id];
    if (question?.id && currentFeedback && currentFeedback !== true) {
      generateValidationSchemaFieldLevel(value, question).then((result) => {
        const nextFeedback = result?.[question.id];
        FormState.update((s) => {
          if (s.feedback?.[id] !== nextFeedback) {
            s.feedback = { ...s.feedback, [id]: nextFeedback };
          }
        });
      });
    }
  }, []);

  return (
    <View style={{ flex: 1 }}>
      <KeyboardAwareScrollView
        ref={scrollRef}
        contentContainerStyle={{ paddingBottom: group?.repeatable ? 124 : 48 }}
        enableOnAndroid
        enableAutomaticScroll={false}
        keyboardShouldPersistTaps="handled"
        keyboardOpeningTime={0}
        extraHeight={124}
        extraScrollHeight={180}
      >
        {items.map((item) => {
          if (item.type === 'header') {
            return (
              <RepeatSection
                key={`header-${item.repeatIndex}`}
                group={group}
                repeatIndex={item.repeatIndex}
              />
            );
          }
          const fieldValue = values?.[item.id];
          const groupQuestions = group?.repeatable ? item.sectionData : activeQuestions;
          return (
            <View
              key={`question-${item.id}`}
              style={styles.questionContainer}
              onLayout={(e) => {
                itemPositions.current[item.id] = e.nativeEvent.layout.y;
              }}
            >
              <QuestionField
                keyform={item.id}
                field={item}
                onChange={handleOnChange}
                value={fieldValue}
                questions={groupQuestions}
              />
            </View>
          );
        })}
      </KeyboardAwareScrollView>
    </View>
  );
};

export default QuestionGroup;
