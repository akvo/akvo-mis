import React, { useEffect, useState } from 'react';
import { View } from 'react-native';
import { Input } from '@rneui/themed';

import { FieldLabel } from '../support';
import getStyles from '../styles';
import { FormState } from '../../store';
import { strToFunction } from '../lib';
import useTheme from '../../lib/theme';

const TypeAutofield = ({
  keyform,
  id,
  label,
  fn,
  tooltip = null,
  displayOnly = false,
  questions = [],
  value: autofieldValue = null,
}) => {
  const theme = useTheme();
  const styles = getStyles(theme);
  const [value, setValue] = useState(null);
  const [fieldColor, setFieldColor] = useState(null);
  const { fnString: nameFnString, fnColor } = fn;

  useEffect(() => {
    const unsubsValues = FormState.subscribe(({ currentValues, surveyStart }) => {
      if (!surveyStart) {
        return;
      }
      try {
        const automateValue = strToFunction(nameFnString, currentValues, questions);
        if (typeof automateValue === 'function') {
          const answer = automateValue();
          if (answer !== value && (answer || answer === 0)) {
            setValue(answer);

            if (typeof fnColor === 'string') {
              const fnColorFunction = strToFunction(fnColor, currentValues, questions);
              if (typeof fnColorFunction === 'function') {
                const fnColorValue = fnColorFunction();
                if (fnColorValue && fnColorValue !== fieldColor) {
                  setFieldColor(fnColorValue);
                }
              }
            } else if (typeof fnColor === 'object' && fnColor?.[answer]) {
              setFieldColor(fnColor[answer]);
            } else {
              setFieldColor(null);
            }
          }
        }
      } catch {
        // Ignore errors in fnString evaluation to avoid breaking the form
      }
    });

    return () => {
      unsubsValues();
    };
  }, [fnColor, nameFnString, id, value, fieldColor, questions]);

  useEffect(() => {
    if (value !== null && value !== autofieldValue && !displayOnly) {
      FormState.update((s) => {
        s.currentValues[id] = value;
      });
    }
  }, [value, id, autofieldValue, displayOnly]);

  return (
    <View testID="type-autofield-wrapper">
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} />
      <Input
                inputContainerStyle={{
          ...styles.autoFieldContainer,
          backgroundColor: fieldColor || styles.autoFieldContainer.backgroundColor,
        }}
        value={value || value === 0 ? String(value) : null}
        testID="type-autofield"
        multiline
        numberOfLines={2}
        disabled
        renderErrorMessage={false}
        style={{
          fontWeight: 'bold',
          opacity: 1,
          color: fieldColor ? '#ffffff' : theme.text.primary,
        }}
      />
    </View>
  );
};

export default TypeAutofield;
