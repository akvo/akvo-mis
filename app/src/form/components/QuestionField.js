/* eslint-disable react/jsx-props-no-spreading */
import React, { useCallback, useMemo, useRef } from 'react';

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
  TypeAttachment,
  TypeSignature,
  TypeGeoDrawing,
} from '../fields';
import getStyles from '../styles';
import { FormState } from '../../store';
import { QUESTION_TYPES } from '../../lib/constants';
import useTheme from '../../lib/theme';

const QuestionField = ({
  keyform,
  field: questionField,
  onChange,
  value = null,
  questions = [],
  onFieldFocus,
}) => {
  const theme = useTheme();
  const styles = getStyles(theme);
  const questionType = questionField?.type;
  const defaultValQuestion = questionField?.default_value || {};
  const displayValue =
    questionField?.hidden || Object.keys(defaultValQuestion).length ? 'none' : 'flex';
  const formFeedback = FormState.useState((s) => s.feedback);
  const viewRef = useRef(null);
  const hasError = useMemo(
    () => formFeedback?.[questionField?.id] && formFeedback?.[questionField?.id] !== true,
    [formFeedback, questionField?.id],
  );

  const handleOnChangeField = useCallback(
    (id, val) => {
      if (questionField?.displayOnly) {
        return;
      }
      onChange(id, val, questionField);
    },
    [onChange, questionField],
  );

  const handleInputFocus = useCallback(() => {
    if (onFieldFocus && viewRef.current) {
      // Measure the position of this component on the screen
      viewRef.current.measureInWindow((x, y, width, height) => {
        onFieldFocus(y, height);
      });
    }
  }, [onFieldFocus]);

  const renderField = useCallback(() => {
    switch (questionType) {
      case QUESTION_TYPES.date:
        return (
          <TypeDate
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            onFocus={handleInputFocus}
            hasError={hasError}
            {...questionField}
          />
        );
      case QUESTION_TYPES.image:
        return (
          <TypeImage
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
            useGallery
          />
        );
      case QUESTION_TYPES.multiple_option:
        return (
          <TypeMultipleOption
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            hasError={hasError}
            {...questionField}
          />
        );
      case QUESTION_TYPES.option:
        return (
          <TypeOption
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            hasError={hasError}
            {...questionField}
          />
        );
      case QUESTION_TYPES.text:
        return (
          <TypeText
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            onFocus={handleInputFocus}
            hasError={hasError}
            {...questionField}
          />
        );
      case QUESTION_TYPES.number:
        return (
          <TypeNumber
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            questions={questions}
            onFocus={handleInputFocus}
            hasError={hasError}
            {...questionField}
          />
        );
      case QUESTION_TYPES.geo:
        return <TypeGeo keyform={keyform} value={value} {...questionField} />;
      case QUESTION_TYPES.cascade:
        return (
          <TypeCascade
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            hasError={hasError}
            {...questionField}
          />
        );
      case QUESTION_TYPES.autofield:
        return (
          <TypeAutofield
            keyform={keyform}
            onChange={handleOnChangeField}
            questions={questions}
            value={value}
            {...questionField}
          />
        );
      case QUESTION_TYPES.attachment:
        return (
          <TypeAttachment
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
          />
        );
      case QUESTION_TYPES.geoshape:
      case QUESTION_TYPES.geotrace:
        return (
          <TypeGeoDrawing
            keyform={keyform}
            onChange={handleOnChangeField}
            value={value}
            {...questionField}
          />
        );
      case QUESTION_TYPES.signature:
        return (
          <TypeSignature
            keyform={keyform}
            onChange={handleOnChangeField}
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
            onFocus={handleInputFocus}
            hasError={hasError}
            {...questionField}
          />
        );
    }
  }, [
    questionType,
    keyform,
    handleOnChangeField,
    handleInputFocus,
    value,
    questionField,
    questions,
    hasError,
  ]);

  return (
    <View ref={viewRef} testID="question-view" style={{ display: displayValue }}>
      {renderField()}
      {hasError && (
        <Text style={styles.validationErrorText} testID="err-validation-text">
          {formFeedback[questionField.id]}
        </Text>
      )}
    </View>
  );
};

export default QuestionField;
