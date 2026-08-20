import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, Alert } from 'react-native';
import { Button } from '@rneui/themed';
import moment from 'moment';
import * as Linking from 'expo-linking';
import { UIState } from '../../store';
import { cascades, i18n } from '../../lib';
import { QUESTION_TYPES } from '../../lib/constants';

const SubtitleContent = ({ index, answer, type, source = null, option = [] }) => {
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const [cascadeValue, setCascadeValue] = useState(null);

  const openFileManager = async (uri) => {
    const supported = await Linking.canOpenURL(uri);
    if (supported) {
      await Linking.openURL(uri);
    } else {
      Alert.alert("Don't know how to open this URL:", uri);
    }
  };

  const fetchCascade = useCallback(async () => {
    const cascadeID = parseInt(answer, 10);
    if (!cascadeID) {
      return;
    }
    if (source?.file) {
      const csValue = await cascades.loadDataSource(source, cascadeID);
      setCascadeValue(csValue);
    }
  }, [answer, source]);

  useEffect(() => {
    fetchCascade();
  }, [fetchCascade]);

  switch (type) {
    case QUESTION_TYPES.geo:
      return (
        <View testID={`text-type-geo-${index}`}>
          <Text>
            {trans.latitude}: {answer?.[0]}
          </Text>
          <Text>
            {trans.longitude}: {answer?.[1]}
          </Text>
        </View>
      );
    case QUESTION_TYPES.cascade:
      return <Text testID={`text-answer-${index}`}>{cascadeValue?.full_path_name || answer}</Text>;
    case QUESTION_TYPES.date:
      return (
        <Text testID={`text-answer-${index}`}>
          {answer ? moment(answer).format('YYYY-MM-DD') : '-'}
        </Text>
      );
    case QUESTION_TYPES.option:
    case QUESTION_TYPES.multiple_option:
      return (
        <Text testID={`text-answer-${index}`}>
          {answer
            ?.map((a) => {
              const findOption = option?.find((o) => o?.value === a);
              return findOption?.label;
            })
            ?.join(', ')}
        </Text>
      );
    case QUESTION_TYPES.attachment:
      if (!answer) {
        return <Text testID={`text-type-attachment-${index}`}>-</Text>;
      }
      return (
        <View testID={`text-type-attachment-${index}`} style={{ width: '100%' }}>
          <Text
            testID={`text-answer-${index}`}
            style={{ color: 'blue', textDecorationLine: 'underline' }}
          >
            {answer.split('/').pop()}
          </Text>
          <Button
            title={trans.openFileButton}
            onPress={() => openFileManager(answer)}
            testID={`open-file-button-${index}`}
            buttonStyle={{ width: '100%', backgroundColor: '#1E90FF', marginTop: 8 }}
          />
        </View>
      );
    default:
      return <Text testID={`text-answer-${index}`}>{answer || answer === 0 ? answer : '-'}</Text>;
  }
};

export default SubtitleContent;
