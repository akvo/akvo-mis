/* eslint-disable react/jsx-props-no-spreading */
import React, { useRef, useMemo, useEffect, useCallback, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  Keyboard,
  TextInput,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';

import QuestionField from './QuestionField';
import { RepeatSection } from '../support';
import { generateValidationSchemaFieldLevel } from '../lib';
import { FormState } from '../../store';
import getStyles from '../styles';
import useTheme from '../../lib/theme';

// Space left between the focused input and the keyboard (or the Back/Next bar above it).
const KEYBOARD_GAP = 24;
// Room kept for the question label above the input, so a tall input never pushes its
// label under the form header.
const LABEL_ROOM = 48;

const QuestionGroup = ({ group, activeQuestions }) => {
  const theme = useTheme();
  const styles = getStyles(theme);
  const values = FormState.useState((s) => s.currentValues);
  const scrollToQuestionId = FormState.useState((s) => s.scrollToQuestionId);
  const listRef = useRef(null);
  const containerRef = useRef(null);
  const scrollOffset = useRef(0);
  const keyboardTop = useRef(0);
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', (e) => {
      keyboardTop.current = e.endCoordinates.screenY;
      setKeyboardHeight(e.endCoordinates.height);
    });
    const hide = Keyboard.addListener('keyboardDidHide', () => setKeyboardHeight(0));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  /**
   * Lift the focused input just clear of the keyboard, measured rather than guessed.
   *
   * react-native-keyboard-aware-scroll-view scrolled a fixed extraHeight + extraScrollHeight
   * on Android, assuming the system had already moved the input up. Edge-to-edge (Android
   * 15+) the system does not, so the input landed at an arbitrary height — tall inputs went
   * far enough to hide their label under the header.
   *
   * The visible bottom is the keyboard top or the list's own bottom, whichever is higher:
   * when Android resizes the window the list ends at the Back/Next bar above the keyboard;
   * edge-to-edge it runs on behind the keyboard. The label cap wins over the gap, so an input
   * taller than the space left shows its top, where typing starts.
   *
   * Runs after the keyboard-height padding below is laid out, so the last inputs can rise.
   * ponytail: fires on keyboard open only; moving focus to a covered input while the
   * keyboard stays up is not followed — hook QuestionField's onFocus if that is reported.
   */
  useEffect(() => {
    const input = TextInput.State.currentlyFocusedInput?.();
    if (!keyboardHeight || !input?.measureInWindow || !containerRef.current) {
      return;
    }
    containerRef.current.measureInWindow((lx, listTop, lw, listHeight) => {
      input.measureInWindow((x, y, width, height) => {
        const visibleBottom = Math.min(keyboardTop.current, listTop + listHeight);
        const lift = Math.min(y + height + KEYBOARD_GAP - visibleBottom, y - LABEL_ROOM - listTop);
        if (lift > 0) {
          listRef.current?.scrollToOffset({ offset: scrollOffset.current + lift, animated: true });
        }
      });
    });
  }, [keyboardHeight]);

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

  // Scroll to the question picked on the overview. By index, not measured offset:
  // the list is virtualized, so a far-down question has no layout until it is near.
  useEffect(() => {
    if (!scrollToQuestionId) {
      return () => {};
    }
    const index = items.findIndex(
      (item) => item.type !== 'header' && item.id === scrollToQuestionId,
    );
    const timer = setTimeout(() => {
      if (index >= 0) {
        listRef.current?.scrollToIndex({ index, animated: true });
      }
      FormState.update((s) => {
        s.scrollToQuestionId = null;
      });
    }, 300);
    return () => clearTimeout(timer);
  }, [scrollToQuestionId, items]);

  // Rows past the rendered window have no measured offset yet: jump near the
  // estimate, which renders them, then land on the row itself.
  const handleScrollToIndexFailed = useCallback(({ index, averageItemLength }) => {
    listRef.current?.scrollToOffset({ offset: averageItemLength * index, animated: false });
    setTimeout(() => listRef.current?.scrollToIndex({ index, animated: true }), 100);
  }, []);

  const handleAddRepeat = useCallback(() => {
    if (group?.repeatable && group?.id) {
      FormState.update((s) => {
        const currentRepeats = s.repeats || {};
        const groupRepeats = currentRepeats[group.id] || [0];
        const nextRepeatIndex = Math.max(...groupRepeats) + 1;
        s.repeats = {
          ...s.repeats,
          [group.id]: [...groupRepeats, nextRepeatIndex],
        };
      });
    }
  }, [group]);

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

  const renderItem = ({ item }) => {
    if (item.type === 'header') {
      return <RepeatSection group={group} repeatIndex={item.repeatIndex} />;
    }
    const groupQuestions = group?.repeatable ? item.sectionData : activeQuestions;
    return (
      <View style={styles.questionContainer}>
        <QuestionField
          keyform={item.id}
          field={item}
          onChange={handleOnChange}
          value={values?.[item.id]}
          questions={groupQuestions}
        />
      </View>
    );
  };

  // Virtualized so opening a long group mounts only the rows near the top, not
  // every field at once (which froze the step transition on long forms).
  return (
    <View ref={containerRef} collapsable={false} style={{ flex: 1 }}>
      <FlatList
        ref={listRef}
        data={items}
        keyExtractor={(item) => (item.type === 'header' ? item.id : `question-${item.id}`)}
        renderItem={renderItem}
        extraData={values}
        onScrollToIndexFailed={handleScrollToIndexFailed}
        onScroll={(e) => {
          scrollOffset.current = e.nativeEvent.contentOffset.y;
        }}
        scrollEventThrottle={16}
        removeClippedSubviews={false}
        // Keyboard height added while it is up, so the last inputs have room to rise above it.
        contentContainerStyle={{ paddingBottom: (group?.repeatable ? 24 : 16) + keyboardHeight }}
        keyboardShouldPersistTaps="handled"
        ListFooterComponent={
          group?.repeatable ? (
            <TouchableOpacity
              style={[repeatStyles.addButton, { backgroundColor: theme.buttonSecondary.bg }]}
              onPress={handleAddRepeat}
              testID={`add-repeat-${group.id}`}
            >
              <Icon name="add-circle-outline" size={20} color={theme.buttonSecondary.text} />
              <Text style={[repeatStyles.addButtonText, { color: theme.buttonSecondary.text }]}>
                {group.repeat_text || 'Add another'}
              </Text>
            </TouchableOpacity>
          ) : null
        }
      />
    </View>
  );
};

const repeatStyles = StyleSheet.create({
  addButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 24,
    marginHorizontal: 16,
    marginTop: 16,
    gap: 8,
  },
  addButtonText: {
    fontSize: 15,
    fontWeight: '600',
  },
});

export default QuestionGroup;
