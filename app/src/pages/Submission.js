import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, FlatList, StyleSheet, Text, TouchableOpacity } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import * as SQLite from 'expo-sqlite';
import moment from 'moment';
import { FormState, UIState, UserState } from '../store';
import { i18n } from '../lib';
import { BaseLayout, FAButton } from '../components';
import { getCurrentTimestamp } from '../form/lib';
import { crudDataPoints } from '../database/crud';

const Submission = ({ navigation, route }) => {
  const [search, setSearch] = useState('');
  const [data, setData] = useState([]);

  const previousForm = FormState.useState((s) => s.previousForm);
  const activeForm = FormState.useState((s) => s.form);
  const activeLang = UIState.useState((s) => s.lang);
  const { id: activeUserId } = UserState.useState((s) => s);
  const trans = i18n.text(activeLang);
  const db = SQLite.useSQLiteContext();
  const refreshPage = UIState.useState((s) => s.refreshPage);

  const datapoints = useMemo(
    () =>
      data.filter(
        (d) => (search && d?.name?.toLowerCase().includes(search.toLowerCase())) || !search,
      ),
    [data, search],
  );

  const goToNewForm = () => {
    FormState.update((s) => {
      s.surveyStart = getCurrentTimestamp();
      s.prevAdmAnswer = null;
    });
    navigation.push('FormPage', {
      ...route?.params,
      newSubmission: true,
    });
  };

  const goToDetails = (item) => {
    const { json: valuesJSON, name: dataPointName } = item;

    FormState.update((s) => {
      /**
       * Double parse to ensure that the JSON is correctly formatted
       * and to handle cases where the JSON string contains escaped quotes.
       */
      const jsonData = typeof valuesJSON === 'string' ? JSON.parse(valuesJSON) : valuesJSON;
      s.currentValues = typeof jsonData === 'string' ? JSON.parse(jsonData) : jsonData;
    });

    navigation.push('FormDataDetails', { name: dataPointName });
  };

  const goToFormOptions = (item) => {
    const { id, name, uuid } = item;
    navigation.push('FormOptions', {
      id,
      name,
      uuid,
      formId: activeForm.formId,
    });
  };

  const goToSavedData = () => {
    navigation.push('FormData', { ...route?.params, showSubmitted: false });
  };

  const fetchData = useCallback(async () => {
    if (!activeForm.id) {
      return;
    }
    /**
     * Fetch data points from the database based on the active form ID and user ID.
     * The data points are filtered by the submitted status (1 for submitted).
     * The results are then formatted to include
     * createdAt and syncedAt dates in a readable format.
     * The syncedAt date is set to '-' if it is null.
     * The isSynced property is set to true if syncedAt is not null.
     * The data points are then set to the state variable 'data'.
     */
    let rows = await crudDataPoints.selectDataPointsByFormAndSubmitted(db, {
      form: activeForm.id,
      submitted: 1,
      user: activeUserId,
      uuid: route?.params?.uuid || null,
    });
    rows = rows.map((res) => {
      const createdAt = moment(res.createdAt).format('DD/MM/YYYY hh:mm A');
      const syncedAt = res.syncedAt ? moment(res.syncedAt).format('DD/MM/YYYY hh:mm A') : '-';
      return {
        ...res,
        createdAt,
        syncedAt,
        isSynced: !!res.syncedAt,
      };
    });
    setData(rows);
  }, [activeForm.id, activeUserId, db, route?.params?.uuid]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (refreshPage) {
      fetchData();
      UIState.update((s) => {
        s.refreshPage = false;
      });
    }
  }, [refreshPage, activeForm?.id, fetchData]);

  useEffect(
    () =>
      navigation.addListener('beforeRemove', (e) => {
        if (previousForm) {
          FormState.update((s) => {
            s.form = previousForm;
            s.previousForm = null;
          });
        }
        navigation.dispatch(e.data.action);
      }),
    [navigation, previousForm],
  );

  const renderItem = ({ item }) => (
    <TouchableOpacity
      key={item.id}
      onPress={() => (activeForm?.parentId ? goToDetails(item) : goToFormOptions(item))}
      testID={`submission-item-${item.id}`}
      style={styles.itemContainer}
      activeOpacity={0.6}
    >
      <View style={styles.iconContainer}>
        <Icon
          name={item.isSynced ? 'checkmark' : 'time'}
          size={24}
          color={item.isSynced ? '#4CAF50' : '#FFA000'}
        />
      </View>
      <View style={styles.itemContent}>
        <Text style={styles.itemTitle}>{item.name}</Text>
        <Text style={styles.itemDate}>
          {trans.createdLabel} {item.createdAt}
        </Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <BaseLayout
      title={route?.params?.name}
      subTitle={route?.params?.subTitle}
      search={{
        show: true,
        value: search,
        action: setSearch,
      }}
      rightComponent={
        <TouchableOpacity
          onPress={goToSavedData}
          testID="draft-submission-button"
          style={{ padding: 8 }}
          activeOpacity={0.6}
        >
          <View style={route?.params?.draft ? styles.redDot : styles.redDotHide} />
          <Icon name="folder-open-outline" size={24} color="#677483" />
        </TouchableOpacity>
      }
    >
      <BaseLayout.Content>
        <View style={styles.container}>
          <FlatList
            data={datapoints}
            renderItem={renderItem}
            keyExtractor={(item) => item.id}
            testID="submission-list"
            contentContainerStyle={styles.flatListContent}
          />
        </View>
      </BaseLayout.Content>
      <FAButton
        label={trans.newSubmissionText}
        onPress={goToNewForm}
        testID="new-submission-button"
        icon={{ name: 'add-circle', size: 20, color: 'white' }}
      />
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    width: '100%',
  },
  flatListContent: {
    padding: 8,
  },
  itemContainer: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: 'white',
    marginBottom: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 2,
    elevation: 2,
  },
  iconContainer: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 20,
    backgroundColor: '#f5f5f5',
    marginRight: 12,
  },
  itemContent: {
    flex: 1,
  },
  itemTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#212121',
    marginBottom: 4,
  },
  itemDate: {
    fontSize: 12,
    color: '#9e9e9e',
  },
  redDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#FF0000',
    position: 'absolute',
    top: 10,
    right: 10,
    zIndex: 1,
  },
  redDotHide: {
    display: 'none',
  },
});

export default Submission;
