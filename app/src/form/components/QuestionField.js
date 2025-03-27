/* eslint-disable react/jsx-props-no-spreading */
import React, { useCallback } from 'react';

import { View, Text } from 'react-native';
import {
  TypeDate,
  TypeImage,
  TypeInput,
  TypeMultipleOption,
  TypeOption,
  TypeText,
  TypeNumber,
  TypeGeo,
  TypeCascade,
  TypeAutofield,
} from '../fields';
import styles from '../styles';
import { FormState } from '../../store';

const QuestionField = ({ keyform, field: questionField, onChange, value = null }) => {
  const questionType = questionField?.type;
  const defaultValQuestion = questionField?.default_value || {};
  const displayValue =
    questionField?.hidden || Object.keys(defaultValQuestion).length ? 'none' : 'flex';
  const formFeedback = FormState.useState((s) => s.feedback);
  const selectedForm = FormState.useState((s) => s.form);

  const handleOnChangeField = useCallback(
    (id, val) => {
      if (questionField?.displayOnly) {
        return;
      }
      onChange(id, val, questionField);
    },
    [onChange, questionField],
  );

  const renderField = useCallback(() => {
    const questions =
      selectedForm && Object.keys(selectedForm).length > 0
        ? JSON.parse(selectedForm.json)?.question_group
        : {};
    switch (questionType) {
      case 'date':
        return (
          <TypeDate
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
          />
        );
      case 'photo':
        return (
          <TypeImage
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
          />
        );
      case 'multiple_option':
        return (
          <TypeMultipleOption
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
          />
        );
      case 'option':
        return (
          <TypeOption
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
          />
        );
      case 'text':
        return (
          <TypeText
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
          />
        );
      case 'number':
        return (
          <TypeNumber
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
          />
        );
      case 'geo':
        return <TypeGeo keyform={keyform} value={value} {...questionField} />;
      case 'cascade':
        return (
          <TypeCascade
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
          />
        );
      case 'autofield':
        return (
          <TypeAutofield
            keyform={keyform}
            onChange={handleOnChangeField}
            questions={questions}
            value={value}
            {...questionField}
          />
        );
      default:
        return (
          <TypeInput
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
          />
        );
    }
  }, [selectedForm, questionField, questionType, keyform, value, handleOnChangeField]);

  return (
    <View testID="question-view" style={{ display: displayValue }}>
      {renderField()}
      {formFeedback?.[questionField?.id] && formFeedback?.[questionField?.id] !== true && (
        <Text style={styles.validationErrorText} testID="err-validation-text">
          {formFeedback[questionField.id]}
        </Text>
      )}
    </View>
  );
};

export default QuestionField;
