import React, { useCallback, useEffect, useState } from 'react';
import { View, SectionList, StyleSheet, TouchableOpacity } from 'react-native';
import * as SQLite from 'expo-sqlite';
import { FormState, UIState } from '../store';
import { i18n } from '../lib';
import { BaseLayout, FormCard, SectionLabel, SettingRow } from '../components';
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

  const renderItem = ({ item }) =>
    item?.isData ? (
      <SettingRow
        icon="document-text-outline"
        label={item.name}
        description={trans.viewDetailsDesc}
        onPress={goToDetails}
        testID={`form-item-${item.id}`}
      />
    ) : (
      <TouchableOpacity
        onPress={() => goToSubmission(item)}
        testID={`form-item-${item.id}`}
        style={styles.card}
        activeOpacity={0.6}
      >
        <FormCard
          variant="monitoring"
          title={item.name}
          version={item.version}
          submitted={item.submitted}
          draft={item.draft}
          synced={item.synced}
        />
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
              <SectionLabel style={isData ? styles.sectionHeader : styles.sectionHeaderForm}>
                {title}
              </SectionLabel>
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
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  card: {
    marginBottom: 8,
  },
  sectionHeader: {
    paddingTop: 16,
    paddingBottom: 8,
  },
  sectionHeaderForm: {
    paddingTop: 32,
    paddingBottom: 8,
  },
});

export default FormOptions;
