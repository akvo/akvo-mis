import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  View,
  SectionList,
  StyleSheet,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  Platform,
  ToastAndroid,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { CheckBox, ListItem } from '@rneui/themed';
import * as FileSystem from 'expo-file-system';
import * as SQLite from 'expo-sqlite';
import * as Sentry from '@sentry/react-native';
import moment from 'moment';
import { FormState, UIState, UserState } from '../store';
import { api, i18n } from '../lib';
import {
  ActionBar,
  BaseLayout,
  ConfirmDialog,
  DatapointCard,
  DatapointLegend,
  EmptyState,
  SectionHeader,
} from '../components';
import useTheme from '../lib/theme';
import { getCurrentTimestamp } from '../form/lib';
import { crudDataPoints, crudForms } from '../database/crud';
import { refreshStorageWarning } from '../lib/submission-fallback';

const Submission = ({ navigation, route }) => {
  const [search, setSearch] = useState('');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [draftsOnly, setDraftsOnly] = useState(false);
  // Per-section collapse, held for the screen's lifetime only (A14).
  const [collapsed, setCollapsed] = useState({});
  const [confirmAction, setConfirmAction] = useState(null);
  // Armed only by openFamilyDraft, which is the one place that swaps the active form.
  // A bare 'focus' listener would also fire on this screen's FIRST focus — and
  // FormOptions sets previousForm before pushing here, so the monitoring list would
  // restore the registration form onto itself the moment it opened.
  const restoreFormOnFocusRef = useRef(false);

  const previousForm = FormState.useState((s) => s.previousForm);
  const activeForm = FormState.useState((s) => s.form);
  const activeLang = UIState.useState((s) => s.lang);
  const { id: activeUserId } = UserState.useState((s) => s);
  const trans = i18n.text(activeLang);
  const theme = useTheme();
  const styles = getStyles(theme);
  const db = SQLite.useSQLiteContext();
  const refreshPage = UIState.useState((s) => s.refreshPage);
  const isOnline = UIState.useState((s) => s.online);

  // The registration list is the only place monitoring rollups make sense: a
  // monitoring list is already scoped to one uuid and has no children of its own.
  const isRegistrationList = !activeForm?.parentId && !route?.params?.uuid;
  // Checked on the registration list, the query widens to the whole form family.
  const isFamilyDraftView = draftsOnly && isRegistrationList;

  // Replaces the red dot the removed header icon carried: the same signal, with the
  // number the dot could never show. Counted by its own query rather than derived
  // from `data` — until the box is checked the list holds registration rows only, so
  // deriving it would undercount by every monitoring draft and then jump on check.
  const [draftCount, setDraftCount] = useState(0);

  const datapoints = useMemo(
    () =>
      data.filter((d) => {
        const matchSearch = !search || d?.name?.toLowerCase().includes(search.toLowerCase());
        // Checked shows drafts ALONE — the same view the removed header icon gave, and
        // the only way to find a handful of unfinished drafts among hundreds of rows.
        const matchDraft = draftsOnly ? d.submitted === 0 : d.submitted === 1;
        return matchSearch && matchDraft;
      }),
    [data, search, draftsOnly],
  );

  const sections = useMemo(() => {
    let groups;
    if (isFamilyDraftView) {
      // Grouped by BACKEND formId so multiple versions of one form collapse into a
      // single section instead of repeating the name. The SQL already orders
      // registration first then monitoring forms, and Map preserves insertion order.
      const byForm = datapoints.reduce((acc, d) => {
        const key = `${d.groupFormId}`;
        if (!acc.has(key)) {
          acc.set(key, { key, title: d.groupName, testID: `section-${d.groupName}`, rows: [] });
        }
        acc.get(key).rows.push(d);
        return acc;
      }, new Map());
      groups = [...byForm.values()];
    } else {
      // Split as on Home, each row once (A19, A20). sortAt is the newest activity
      // created in this app — the row itself or its monitoring data (A18); 0 is none.
      groups = [
        {
          key: 'latest',
          title: trans.latestSubmissionsTitle,
          rows: datapoints.filter((d) => d.sortAt > 0).sort((a, b) => b.sortAt - a.sortAt),
        },
        {
          key: 'earlier',
          title: trans.earlierSubmissionsTitle,
          rows: datapoints.filter((d) => !(d.sortAt > 0)),
        },
      ];
    }
    // Empty sections are hidden. A collapsed one keeps its header and count (A21) but
    // drops its rows, so a long list stays virtualized.
    return groups
      .filter((g) => g.rows.length)
      .map((g, gx) => ({
        ...g,
        testID: g.testID || `section-header-${g.key}`,
        spaced: gx > 0,
        data: collapsed[g.key] ? [] : g.rows,
      }));
  }, [
    datapoints,
    isFamilyDraftView,
    collapsed,
    trans.earlierSubmissionsTitle,
    trans.latestSubmissionsTitle,
  ]);

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

  const openFamilyDraft = async (item) => {
    // A row from another form in the family: load that form first, exactly as
    // FormOptions does, and remember the registration form so the existing
    // beforeRemove listener restores it on the way back.
    if (item.form === activeForm?.id) {
      onClickItem(item);
      return;
    }
    const targetForm = await crudForms.selectFormById(db, { id: item.form });
    if (!targetForm) {
      Sentry.captureMessage(`[Submission] draft ${item.id} points at a missing form ${item.form}`);
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.formMissingText, ToastAndroid.LONG);
      }
      return;
    }
    FormState.update((s) => {
      s.previousForm = activeForm;
      s.form = targetForm;
      s.surveyStart = getCurrentTimestamp();
      s.surveyDuration = item?.duration;
      s.repeats = item?.repeats ? JSON.parse(item.repeats) : {};
    });
    restoreFormOnFocusRef.current = true;
    navigation.push('FormPage', {
      id: targetForm.id,
      name: targetForm.name,
      uuid: item.uuid,
      dataPointId: item.id,
      newSubmission: false,
    });
  };

  const fetchData = useCallback(async () => {
    if (!activeForm?.id) {
      setLoading(false);
      return;
    }
    try {
      const registrationList = !activeForm?.parentId && !route?.params?.uuid;
      const familyView = draftsOnly && registrationList;

      // The label total, counted independently of the list query above: on the
      // registration list it spans the whole family, on a monitoring list just that
      // form and datapoint.
      setDraftCount(
        registrationList
          ? await crudDataPoints.countFamilyDrafts(db, {
              formDbId: activeForm.id,
              backendFormId: activeForm.formId,
              user: activeUserId,
            })
          : await crudDataPoints.totalSavedData(db, activeForm.id, route?.params?.uuid || null),
      );

      const stats = registrationList
        ? await crudDataPoints.getMonitoringStats(db, activeForm.formId, activeUserId)
        : [];
      const statsByUuid = new Map(stats.map((st) => [st.uuid, st]));

      let rows = familyView
        ? await crudDataPoints.getFamilyDrafts(db, {
            formDbId: activeForm.id,
            backendFormId: activeForm.formId,
            user: activeUserId,
          })
        : await crudDataPoints.selectDataPointsByFormAndSubmitted(db, {
            form: activeForm.id,
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
              // A row whose answers will not parse cannot be checked for missing
              // files. Reported rather than swallowed: it also means the detail
              // screen and the delete cleanup will not see those files either.
              Sentry.captureMessage(`[Submission] unreadable answers on datapoint ${res.id}`);
              Sentry.captureException(error);
              needsRetake = false;
            }
          }

          const monitoring = statsByUuid.get(res.uuid);
          // Computed from the RAW columns: createdAt above is already a display string.
          // A downloaded row's own dates are the download time, so only its monitoring
          // activity counts (APP-481 A18).
          const ownTimes = res.locallyCreated ? [res.submittedAt, res.createdAt] : [];
          const timestamps = [...ownTimes, monitoring?.lastSubmissionAt]
            .filter(Boolean)
            .map((d) => moment(d).valueOf())
            .filter((ms) => !Number.isNaN(ms));

          return {
            ...res,
            createdAt,
            syncedAt,
            isSynced: !!res.syncedAt,
            needsRetake,
            monitoringDrafts: monitoring?.draftCount || 0,
            monitoringSubmissions: monitoring?.submissionCount || 0,
            lastMonitoringAt: monitoring?.lastSubmissionAt || null,
            sortAt: timestamps.length ? Math.max(...timestamps) : 0,
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
  }, [
    activeForm?.id,
    activeForm?.formId,
    activeForm?.parentId,
    activeUserId,
    db,
    draftsOnly,
    route?.params?.uuid,
  ]);

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
      // Restore the form the user came from, then let the navigation proceed on its
      // own. Nothing calls e.preventDefault() here, so re-dispatching e.data.action
      // would fire the same action a second time — and once this screen is gone the
      // duplicate has no navigator left to handle it ("GO_BACK was not handled").
      navigation.addListener('beforeRemove', () => {
        if (previousForm) {
          FormState.update((s) => {
            s.form = previousForm;
            s.previousForm = null;
          });
        }
      }),
    [navigation, previousForm],
  );

  useEffect(
    () =>
      // Returning from a form opened by openFamilyDraft focuses this screen without
      // unmounting it, so the swapped form has to be undone here or the registration
      // list reloads itself as a monitoring list. Gated on the ref: this also fires on
      // first focus, when previousForm belongs to the screen that pushed us — and
      // restoring then would swap the monitoring list onto the registration form.
      navigation.addListener('focus', () => {
        if (!restoreFormOnFocusRef.current) {
          return;
        }
        restoreFormOnFocusRef.current = false;
        if (previousForm) {
          FormState.update((s) => {
            s.form = previousForm;
            s.previousForm = null;
          });
        }
      }),
    [navigation, previousForm],
  );

  // A URI is only safe to delete when no other row references it, or the surviving
  // row is left showing a broken preview.
  const removeLocalFiles = async (item) => {
    if (!item?.json) {
      return;
    }
    try {
      const values = JSON.parse(item.json.replace(/''/g, "'"));
      const uris = Object.values(values).filter(
        (v) => typeof v === 'string' && v.startsWith('file://'),
      );
      await Promise.all(
        uris.map(async (uri) => {
          const referenced = await crudDataPoints.countJsonReferences(db, uri, item.id);
          if (referenced > 0) {
            return;
          }
          try {
            await FileSystem.deleteAsync(uri, { idempotent: true });
          } catch (error) {
            // Best effort, but reported: a failed delete leaves an orphan file,
            // which is a storage leak worth knowing about.
            Sentry.captureMessage(`[Submission] orphaned file after draft delete: ${uri}`);
            Sentry.captureException(error);
          }
        }),
      );
    } catch (error) {
      Sentry.captureMessage('[Submission] could not read answers while deleting a draft');
      Sentry.captureException(error);
    }
  };

  const handleConfirmAction = async () => {
    const { type, item } = confirmAction || {};
    setConfirmAction(null);
    if (!item) {
      return;
    }
    try {
      if (type === 'delete') {
        // Atomic: the server copy goes first, and the local row only follows if that
        // succeeded. Either both disappear or neither does — a half-deleted draft
        // that comes back on the next sync is harder to explain than a failure.
        // The device route, not the web one: /draft-submission requires
        // IsAuthenticated, which a MobileAssignmentToken can never satisfy.
        if (item.draftId) {
          await api.delete(`/draft-list/${item.draftId}`);
        }
        await removeLocalFiles(item);
        await crudDataPoints.deleteDataPoint(db, item.id);
        await refreshStorageWarning();
        // Home stays mounted underneath and computes its Submitted/Draft/Synced
        // counts once, so without this its card still counts the deleted draft
        // until something else happens to refresh it.
        UIState.update((s) => {
          s.refreshPage = true;
        });
      } else {
        await crudDataPoints.setSendToWeb(db, item.id);
        if (Platform.OS === 'android') {
          ToastAndroid.show(trans.sendToWebToast, ToastAndroid.LONG);
        }
      }
      await fetchData();
    } catch (error) {
      Sentry.captureMessage('[Submission] Unable to apply draft action');
      Sentry.captureException(error);
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.deleteDraftFailedText, ToastAndroid.LONG);
      }
    }
  };

  // A web-known draft cannot be deleted offline, and finding that out after
  // confirming is worse than not being offered it: say so on the tap instead.
  const askDelete = (item) => {
    if (item.draftId && !isOnline) {
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.deleteNeedsConnectionText, ToastAndroid.LONG);
      }
      return;
    }
    setConfirmAction({ type: 'delete', item });
  };

  // One line under the name (Figma): the date, plus the monitoring count on the
  // registration list. The card truncates it rather than wrapping.
  const getMeta = (item) => {
    // Downloaded rows: syncedAt is the server's last_updated; createdAt is the download time.
    const date = (item.locallyCreated ? item.createdAt : item.syncedAt).split(' ')[0];
    const created = (item.submitted === 0 ? trans.createdOn : trans.registeredOn).replace(
      '{date}',
      date,
    );
    if (item.submitted !== 1 || activeForm?.parentId) {
      return created;
    }
    return `${created} · ${trans.monitoringCount.replace('{count}', item.monitoringSubmissions)}`;
  };

  const renderItem = ({ item }) => {
    // Submitted rows have nothing to swipe to — keep them plain so the gesture only
    // exists where it does something.
    if (item.submitted !== 0) {
      return (
        <TouchableOpacity
          onPress={() => onClickItem(item)}
          testID={`submission-item-${item.id}`}
          style={styles.item}
          activeOpacity={0.6}
        >
          <DatapointCard item={item} meta={getMeta(item)} trans={trans} />
        </TouchableOpacity>
      );
    }
    return (
      <ListItem.Swipeable
        onPress={() => openFamilyDraft(item)}
        containerStyle={styles.swipeItem}
        testID={`submission-item-${item.id}`}
        leftWidth={112}
        minSlideWidth={40}
        leftContent={
          <View style={styles.swipeActions}>
            <TouchableOpacity
              onPress={() => askDelete(item)}
              testID={`delete-draft-${item.id}`}
              style={styles.swipeAction}
            >
              <Icon name="trash-outline" size={22} color={theme.status.error} />
            </TouchableOpacity>
            {!item.draftId && !item.sendToWeb && (
              <TouchableOpacity
                onPress={() => setConfirmAction({ type: 'sendToWeb', item })}
                testID={`send-to-web-${item.id}`}
                style={styles.swipeAction}
              >
                <Icon name="cloud-upload-outline" size={22} color={theme.icon.accent} />
              </TouchableOpacity>
            )}
          </View>
        }
      >
        {/*
          One child only: RNEUI's PadView inserts an unkeyed spacer View between
          siblings, which triggers a "unique key" warning from inside the library.
        */}
        <DatapointCard item={item} meta={getMeta(item)} trans={trans} />
      </ListItem.Swipeable>
    );
  };

  const toggleSection = (key) => setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));

  const renderSectionHeader = ({ section }) => (
    <SectionHeader
      title={section.title}
      count={section.rows.length}
      collapsed={!!collapsed[section.key]}
      onToggle={() => toggleSection(section.key)}
      testID={section.testID}
      style={section.spaced ? styles.spacedHeader : null}
    />
  );

  const renderEmptyState = () =>
    loading ? (
      <View style={styles.emptyStateContainer}>
        <View style={styles.emptyIconContainer}>
          <ActivityIndicator size="large" color={theme.text.highlight} />
        </View>
        <View style={styles.emptyStateTextContainer}>
          <Text style={styles.emptyStateTitle}>{trans.fetchingData}</Text>
        </View>
      </View>
    ) : (
      // Figma's arrow position: its tip lands on the full-width action bar (A25).
      <EmptyState
        title={trans.emptySubmissionMessageInfo}
        body={trans.emptySubmissionMessageAction}
        testID="submission-empty-state"
      />
    );

  return (
    <BaseLayout
      title={route?.params?.name}
      subTitle={route?.params?.subTitle}
      search={{
        show: true,
        placeholder: trans.formDataSearch,
        value: search,
        action: setSearch,
      }}
    >
      <BaseLayout.Content>
        <View style={styles.container}>
          <View style={styles.filterBar}>
            <CheckBox
              checked={draftsOnly}
              onPress={() => setDraftsOnly((prev) => !prev)}
              title={`${trans.showDraftsOnlyLabel}${draftCount ? ` (${draftCount})` : ''}`}
              testID="show-drafts-checkbox"
              containerStyle={styles.filterCheckbox}
              textStyle={styles.filterCheckboxText}
              checkedColor={theme.icon.accent}
              uncheckedColor={theme.text.tertiary}
            />
          </View>
          {draftsOnly && datapoints.length > 0 && (
            <Text style={styles.swipeHint} testID="swipe-hint">
              {trans.swipeHintText}
            </Text>
          )}
          <View style={styles.listSection}>
            <SectionList
              sections={sections}
              renderItem={renderItem}
              renderSectionHeader={renderSectionHeader}
              keyExtractor={(item) => `${item.id}`}
              testID="submission-list"
              stickySectionHeadersEnabled={false}
              contentContainerStyle={[
                styles.flatListContent,
                datapoints.length === 0 && styles.emptyListContent,
              ]}
              ListEmptyComponent={renderEmptyState}
              ListFooterComponent={
                datapoints.length > 0 ? <DatapointLegend trans={trans} items={datapoints} /> : null
              }
            />
          </View>
        </View>
      </BaseLayout.Content>
      <ActionBar
        label={trans.newSubmissionText}
        onPress={goToNewForm}
        testID="new-submission-button"
      />
      <ConfirmDialog
        visible={!!confirmAction}
        danger={confirmAction?.type === 'delete'}
        title={confirmAction?.type === 'delete' ? trans.deleteDraftTitle : trans.sendToWebTitle}
        message={
          confirmAction?.type === 'delete'
            ? `${trans.deleteDraftMessage}${
                confirmAction?.item?.draftId ? ` ${trans.deleteDraftWebToo}` : ''
              }`
            : trans.sendToWebMessage
        }
        onClose={() => setConfirmAction(null)}
        actions={[
          {
            label: trans.buttonCancel,
            type: 'secondary',
            onPress: () => setConfirmAction(null),
            testID: 'cancel-action-button',
          },
          {
            label: trans.buttonYes,
            type: confirmAction?.type === 'delete' ? 'danger' : 'primary',
            onPress: handleConfirmAction,
            testID: 'confirm-action-button',
          },
        ]}
      />
    </BaseLayout>
  );
};

const getStyles = (theme) =>
  StyleSheet.create({
    container: {
      flex: 1,
      width: '100%',
    },
    listSection: {
      flex: 1,
      paddingHorizontal: 16,
      paddingTop: 12,
    },
    flatListContent: {
      paddingBottom: 16,
    },
    emptyListContent: {
      flexGrow: 1,
    },
    filterBar: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: 8,
      paddingVertical: 4,
    },
    filterCheckbox: {
      backgroundColor: 'transparent',
      borderWidth: 0,
      padding: 0,
      margin: 0,
    },
    filterCheckboxText: {
      fontSize: 14,
      fontWeight: 'normal',
      color: theme.text.secondary,
    },
    spacedHeader: {
      marginTop: 16,
    },
    swipeHint: {
      fontSize: 14,
      color: theme.text.tertiary,
      fontStyle: 'italic',
      paddingHorizontal: 16,
      paddingTop: 4,
    },
    item: {
      marginBottom: 8,
    },
    // The card draws itself; the swipe container only has to get out of its way.
    swipeItem: {
      padding: 0,
      marginBottom: 8,
      backgroundColor: 'transparent',
    },
    swipeActions: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'flex-start',
      marginBottom: 8,
      borderRadius: 12,
      backgroundColor: theme.bg.surfaceChip,
    },
    swipeAction: {
      width: 56,
      height: '100%',
      alignItems: 'center',
      justifyContent: 'center',
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
      color: theme.text.primary,
      textAlign: 'center',
      marginBottom: 8,
    },
  });

export default Submission;
