import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  Platform,
  ToastAndroid,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import LucideIcon from '@react-native-vector-icons/lucide';
import * as FileSystem from 'expo-file-system';
import * as SQLite from 'expo-sqlite';
import * as Sentry from '@sentry/react-native';
import moment from 'moment';
import { FormState, UIState, UserState } from '../store';
import { i18n } from '../lib';
import { BaseLayout, FAButton } from '../components';
import { getCurrentTimestamp } from '../form/lib';
import { crudDataPoints } from '../database/crud';

const Submission = ({ navigation, route }) => {
  const [search, setSearch] = useState('');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isSubmitted, setIsSubmitted] = useState(1);
  const [totalSavedData, setTotalSavedData] = useState(0);

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
      s.currentValues = typeof valuesJSON === 'string' ? JSON.parse(valuesJSON) : valuesJSON;
    });

    navigation.push('FormDataDetails', {
      name: dataPointName,
      id: item.id,
      isSynced: item.isSynced,
    });
  };

  const goToFormOptions = (item) => {
    const { id, name, uuid, repeats } = item;
    if (repeats) {
      FormState.update((s) => {
        s.repeats = JSON.parse(repeats);
      });
    }
    navigation.push('FormOptions', {
      id,
      name,
      uuid,
      formId: activeForm.formId,
    });
  };

  const toggleIsSubmitted = () => {
    setIsSubmitted((prev) => (prev === 1 ? 0 : 1));
    setSearch('');
    setLoading(true);
    UIState.update((s) => {
      s.refreshPage = true;
    });
  };

  const onClickItem = (selectedData) => {
    if (selectedData?.submitted === 0) {
      FormState.update((s) => {
        s.surveyStart = getCurrentTimestamp();
        s.surveyDuration = selectedData?.duration;
        s.repeats = selectedData?.repeats ? JSON.parse(selectedData?.repeats) : {};
      });
      navigation.navigate('FormPage', {
        ...route?.params,
        dataPointId: selectedData.id,
        newSubmission: false,
      });
      return;
    }
    if (activeForm?.parentId) {
      goToDetails(selectedData);
    } else {
      goToFormOptions(selectedData);
    }
  };

  const fetchData = useCallback(async () => {
    if (!activeForm?.id) {
      setLoading(false);
      return;
    }
    try {
      const draftCount = await crudDataPoints.totalSavedData(
        db,
        activeForm.id,
        route?.params?.uuid || null,
      );
      setTotalSavedData(draftCount);
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
        submitted: isSubmitted,
        user: activeUserId,
        uuid: route?.params?.uuid || null,
      });
      rows = await Promise.all(
        rows.map(async (res) => {
          const createdAt = moment(res.createdAt).format('DD/MM/YYYY hh:mm A');
          const syncedAt = res.syncedAt ? moment(res.syncedAt).format('DD/MM/YYYY hh:mm A') : '-';
          // Flag unsynced rows whose local photo files no longer exist —
          // they will never upload until the user retakes the photo
          let needsRetake = false;
          if (!res.syncedAt && res.json) {
            try {
              const values = JSON.parse(res.json.replace(/''/g, "'"));
              const fileUris = Object.values(values).filter(
                (v) => typeof v === 'string' && v.startsWith('file://'),
              );
              const filesExist = await Promise.all(
                fileUris.map((uri) =>
                  FileSystem.getInfoAsync(uri)
                    .then((info) => info.exists)
                    .catch(() => false),
                ),
              );
              needsRetake = filesExist.some((exists) => !exists);
            } catch (error) {
              needsRetake = false;
            }
          }
          return {
            ...res,
            createdAt,
            syncedAt,
            isSynced: !!res.syncedAt,
            needsRetake,
          };
        }),
      );
      setData(rows);
    } catch (error) {
      Sentry.captureMessage('[Submission] Unable to fetch data points');
      Sentry.captureException(error);
      if (Platform.OS === 'android') {
        ToastAndroid.show(`SQL: ${error}`, ToastAndroid.LONG);
      }
    } finally {
      setLoading(false);
    }
  }, [activeForm?.id, activeUserId, db, isSubmitted, route?.params?.uuid]);

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
      onPress={() => onClickItem(item)}
      testID={`submission-item-${item.id}`}
      style={[styles.itemContainer, item.submitted === 0 && styles.itemDraftBorder]}
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
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          {item.submitted === 0 && (
            <View style={styles.draftBadge}>
              <Text style={styles.draftText}>{trans.draftText}</Text>
            </View>
          )}
          {item.needsRetake && (
            <View style={styles.retakeBadge} testID={`retake-badge-${item.id}`}>
              <Text style={styles.retakeText}>{trans.photoMissingText}</Text>
            </View>
          )}
          <Text style={styles.itemDate}>
            {trans.createdLabel} {item.createdAt}
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  );

  const renderEmptyState = () =>
    loading ? (
      <View style={styles.emptyStateContainer}>
        <View style={styles.emptyIconContainer}>
          <ActivityIndicator size="large" />
        </View>
        <View style={styles.emptyStateTextContainer}>
          <Text style={styles.emptyStateTitle}>{trans.fetchingData}</Text>
        </View>
      </View>
    ) : (
      <View style={styles.emptyStateContainer}>
        <View style={styles.emptyIconContainer}>
          <Icon name="document-outline" size={64} color="#C5CAE9" />
        </View>
        <View style={styles.emptyStateTextContainer}>
          <Text style={styles.emptyStateTitle}>{trans.emptySubmissionMessageInfo}</Text>
          <Text style={styles.emptyStateDescription}>{trans.emptySubmissionMessageAction}</Text>
        </View>
      </View>
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
          onPress={toggleIsSubmitted}
          testID="draft-submission-button"
          style={{ padding: 8 }}
          activeOpacity={0.6}
        >
          <View style={totalSavedData && isSubmitted === 1 ? styles.redDot : styles.redDotHide} />
          {isSubmitted ? (
            <LucideIcon name="file-clock" size={24} color="#677483" />
          ) : (
            <Icon name="close-outline" size={24} color="#677483" />
          )}
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
            contentContainerStyle={[
              styles.flatListContent,
              datapoints.length === 0 && styles.emptyListContent,
            ]}
            ListEmptyComponent={renderEmptyState}
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
  emptyListContent: {
    flexGrow: 1,
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
    borderLeftWidth: 4,
    borderLeftColor: 'transparent',
  },
  itemDraftBorder: {
    borderLeftColor: '#FFEB3B',
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
  emptyStateContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
    paddingVertical: 60,
  },
  emptyIconContainer: {
    marginBottom: 20,
  },
  emptyStateTextContainer: {
    alignItems: 'center',
  },
  emptyStateTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#424242',
    textAlign: 'center',
    marginBottom: 8,
  },
  emptyStateDescription: {
    fontSize: 14,
    color: '#757575',
    textAlign: 'center',
    lineHeight: 20,
  },
  draftBadge: {
    backgroundColor: '#FFEB3B',
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderTopLeftRadius: 4,
    borderBottomLeftRadius: 4,
  },
  draftText: {
    fontSize: 12,
    color: '#212121',
    fontWeight: 'bold',
  },
  retakeBadge: {
    backgroundColor: '#FEE2E2',
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: 4,
  },
  retakeText: {
    fontSize: 12,
    color: '#B91C1C',
    fontWeight: 'bold',
  },
});

export default Submission;
