import React, { useCallback, useEffect, useState } from 'react';
import { View, SectionList, StyleSheet, Text, TouchableOpacity } from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import * as SQLite from 'expo-sqlite';
import { FormState, UIState } from '../store';
import { i18n } from '../lib';
import { BaseLayout } from '../components';
import { crudDataPoints, crudForms } from '../database/crud';

const FormOptions = ({ navigation, route }) => {
  const [forms, setForms] = useState([]);
  const activeForm = FormState.useState((s) => s.form);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const db = SQLite.useSQLiteContext();

  const goToSubmission = (selectedForm) => {
    FormState.update((s) => {
      s.form = selectedForm;
      s.previousForm = activeForm;
    });
    navigation.push('Submission', {
      id: selectedForm?.id,
      name: selectedForm.name,
      subTitle: route?.params?.name,
      uuid: route?.params?.uuid,
      formId: selectedForm.formId,
      draft: selectedForm?.draft || 0,
    });
  };

  const goToDetails = async () => {
    const item = await crudDataPoints.selectDataPointById(db, {
      id: route?.params?.id,
    });
    const { json: valuesJSON, name: dataPointName } = item || {};
    if (!valuesJSON) {
      return;
    }
    const dataValues = typeof valuesJSON === 'string' ? JSON.parse(valuesJSON) : valuesJSON;
    FormState.update((s) => {
      s.currentValues = dataValues;
    });
    navigation.push('FormDataDetails', {
      name: dataPointName,
      id: item?.id,
      isSynced: !!item?.syncedAt,
    });
  };

  const renderItem = ({ item }) => (
    <TouchableOpacity
      key={item.id}
      onPress={() => (item?.isData ? goToDetails() : goToSubmission(item))}
      testID={`form-item-${item.id}`}
      style={styles.itemContainer}
      activeOpacity={0.6}
    >
      <View style={styles.itemContent}>
        {item?.isData ? (
          <Text style={styles.itemLabel}>{item.name}</Text>
        ) : (
          <View>
            <Text style={styles.itemTitle}>
              {item.name} {item?.submitted ? `(${item.submitted})` : ''}
            </Text>

            <Text style={styles.itemVersion}>{`${trans.versionLabel}${item.version}`}</Text>
          </View>
        )}
      </View>
      <Icon name="chevron-right" size={18} color="#ccc" />
    </TouchableOpacity>
  );

  const fetchForms = useCallback(async () => {
    let rows = await crudForms.getFormOptions(db, {
      parentId: activeForm?.formId,
      uuid: route?.params?.uuid,
    });
    rows = rows.map((r) => ({ ...r, parentName: activeForm.name, parentDBId: activeForm.id }));
    setForms(rows);
  }, [db, activeForm, route?.params?.uuid]);

  useEffect(() => {
    fetchForms();
  }, [fetchForms]);

  useEffect(
    () =>
      // Same as Submission: nothing is prevented here, so re-dispatching the action
      // would run it twice and the duplicate goes unhandled once the screen is gone.
      navigation.addListener('beforeRemove', () => {
        UIState.update((s) => {
          s.refreshPage = true;
        });
      }),
    [navigation, activeForm?.id],
  );

  return (
    <BaseLayout title={route?.params?.name} rightComponent={false}>
      <BaseLayout.Content>
        <View style={styles.container}>
          <SectionList
            sections={[
              {
                isData: true,
                title: trans.datapointLabel,
                data: [{ id: route?.params?.id, name: trans.viewDetails, isData: true }],
              },
              { title: trans.monitoringForms, data: forms },
            ]}
            renderItem={renderItem}
            keyExtractor={(item) => item.id}
            testID="form-list"
            contentContainerStyle={styles.flatListContent}
            stickySectionHeadersEnabled={false}
            renderSectionHeader={({ section: { title, isData } }) => (
              <Text style={isData ? styles.sectionHeader : styles.sectionHeaderForm}>{title}</Text>
            )}
          />
        </View>
      </BaseLayout.Content>
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    width: '100%',
  },
  flatListContent: {
    paddingHorizontal: 8,
  },
  itemContainer: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    backgroundColor: 'white',
    marginBottom: 0,
    borderBottomColor: '#E0E0E0',
    borderBottomWidth: 1,
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
  itemLabel: {
    fontSize: 14,
    color: '#757575',
  },
  itemVersion: {
    fontSize: 12,
    color: '#9e9e9e',
  },
  sectionHeader: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#212121',
    backgroundColor: '#f5f5f5',
    paddingVertical: 12,
    paddingLeft: 16,
  },
  sectionHeaderForm: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#212121',
    backgroundColor: '#f5f5f5',
    paddingVertical: 12,
    paddingLeft: 16,
    marginTop: 24,
  },
});

export default FormOptions;
