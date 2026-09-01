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
import { CheckBox, Dialog, ListItem } from '@rneui/themed';
import * as FileSystem from 'expo-file-system';
import * as SQLite from 'expo-sqlite';
import * as Sentry from '@sentry/react-native';
import moment from 'moment';
import { FormState, UIState, UserState } from '../store';
import { api, i18n } from '../lib';
import { BaseLayout, FAButton } from '../components';
import { getCurrentTimestamp } from '../form/lib';
import { crudDataPoints, crudForms } from '../database/crud';
import { refreshStorageWarning } from '../lib/submission-fallback';

const Submission = ({ navigation, route }) => {
  const [search, setSearch] = useState('');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [draftsOnly, setDraftsOnly] = useState(false);
  const [sortByLastSubmission, setSortByLastSubmission] = useState(false);
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

  const datapoints = useMemo(() => {
    const filtered = data.filter((d) => {
      const matchSearch = !search || d?.name?.toLowerCase().includes(search.toLowerCase());
      // Checked shows drafts ALONE — the same view the removed header icon gave, and
      // the only way to find a handful of unfinished drafts among hundreds of rows.
      const matchDraft = draftsOnly ? d.submitted === 0 : d.submitted === 1;
      return matchSearch && matchDraft;
    });
    if (!sortByLastSubmission) {
      return filtered;
    }
    // sortAt is the newest of this row's submission, its creation and its latest
    // monitoring submission, so "last submission" means the datapoint's last
    // activity rather than only the registration's. Sort a copy: data is state.
    return [...filtered].sort((a, b) => b.sortAt - a.sortAt);
  }, [data, search, draftsOnly, sortByLastSubmission]);

  const sections = useMemo(() => {
    if (!isFamilyDraftView) {
      // One untitled section: the ordinary list, unchanged.
      return datapoints.length ? [{ title: null, data: datapoints }] : [];
    }
    // Grouped by BACKEND formId so multiple versions of one form collapse into a
    // single section instead of repeating the name. The SQL already orders
    // registration first then monitoring forms, and Map preserves insertion order.
    const byForm = datapoints.reduce((acc, d) => {
      const key = d.groupFormId;
      if (!acc.has(key)) {
        acc.set(key, { title: d.groupName, data: [] });
      }
      acc.get(key).data.push(d);
      return acc;
    }, new Map());
    return [...byForm.values()];
  }, [datapoints, isFamilyDraftView]);

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
          const timestamps = [res.submittedAt, res.createdAt, monitoring?.lastSubmissionAt]
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

  const renderRowBody = (item) => (
    <View style={styles.itemContent}>
      <Text style={styles.itemTitle} numberOfLines={2} ellipsizeMode="tail">
        {item.name}
      </Text>
      <View style={styles.badgeRow}>
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
        {item.submitted === 0 &&
          (!!item.draftId || !!item.sendToWeb) &&
          // syncedAt is the only honest signal here. Bound for the web is not the
          // same as on the web: a freshly opted-in draft has not left the device
          // yet, and an edited one leaves a stale copy up there until it re-uploads.
          (item.isSynced ? (
            <Text style={styles.onWebLabel} testID={`on-web-${item.id}`}>
              {trans.onWebLabel}
            </Text>
          ) : (
            <Text style={styles.pendingWebLabel} testID={`pending-web-${item.id}`}>
              {trans.pendingWebLabel}
            </Text>
          ))}
        <Text style={styles.itemDate}>
          {trans.createdLabel} {item.createdAt}
        </Text>
      </View>
      {item.submitted === 1 && !activeForm?.parentId && (
        <Text style={styles.itemMeta} testID={`monitoring-meta-${item.id}`}>
          {`${trans.monitoringLabel}${item.monitoringSubmissions}`}
          {item.monitoringDrafts > 0 ? ` · ${trans.draftLabel}${item.monitoringDrafts}` : ''}
          {item.lastMonitoringAt
            ? ` · ${trans.lastMonitoringLabel}${moment(item.lastMonitoringAt).format('DD/MM/YYYY')}`
            : ''}
        </Text>
      )}
    </View>
  );

  const renderItem = ({ item }) => {
    // Submitted rows have nothing to swipe to — keep them plain so the gesture only
    // exists where it does something.
    if (item.submitted !== 0) {
      return (
        <TouchableOpacity
          key={item.id}
          onPress={() => onClickItem(item)}
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
          {renderRowBody(item)}
        </TouchableOpacity>
      );
    }
    return (
      <ListItem.Swipeable
        key={item.id}
        onPress={() => openFamilyDraft(item)}
        containerStyle={[styles.itemContainer, styles.itemDraftBorder]}
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
              <Icon name="trash-outline" size={22} color="#B91C1C" />
            </TouchableOpacity>
            {!item.draftId && !item.sendToWeb && (
              <TouchableOpacity
                onPress={() => setConfirmAction({ type: 'sendToWeb', item })}
                testID={`send-to-web-${item.id}`}
                style={styles.swipeAction}
              >
                <Icon name="cloud-upload-outline" size={22} color="#1651b6" />
              </TouchableOpacity>
            )}
          </View>
        }
      >
        {/*
          One child only. RNEUI's PadView inserts an unkeyed spacer View between
          siblings, so passing Content and Chevron separately triggers a "unique key"
          warning from inside the library. Wrapping them keeps the same layout.
        */}
        <View style={styles.swipeRowInner}>
          {renderRowBody(item)}
          <Icon name="chevron-forward" size={18} color="#cccccc" />
        </View>
      </ListItem.Swipeable>
    );
  };

  const renderSectionHeader = ({ section }) =>
    section.title ? (
      <View style={styles.sectionHeader} testID={`section-${section.title}`}>
        <Text style={styles.sectionHeaderText} numberOfLines={1}>
          {section.title}
        </Text>
        <Text style={styles.sectionHeaderCount}>{section.data.length}</Text>
      </View>
    ) : null;

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
            />
            <TouchableOpacity
              onPress={() => setSortByLastSubmission((prev) => !prev)}
              testID="sort-last-submission-button"
              style={[styles.sortChip, sortByLastSubmission && styles.sortChipActive]}
              activeOpacity={0.6}
            >
              <Icon
                name="swap-vertical"
                size={14}
                color={sortByLastSubmission ? '#ffffff' : '#424242'}
              />
              <Text
                style={[styles.sortChipText, sortByLastSubmission && styles.sortChipTextActive]}
              >
                {trans.sortLastSubmissionLabel}
              </Text>
            </TouchableOpacity>
          </View>
          {draftsOnly && datapoints.length > 0 && (
            <Text style={styles.swipeHint} testID="swipe-hint">
              {trans.swipeHintText}
            </Text>
          )}
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
          />
        </View>
      </BaseLayout.Content>
      <FAButton
        label={trans.newSubmissionText}
        onPress={goToNewForm}
        testID="new-submission-button"
        icon={{ name: 'add-circle', size: 20, color: 'white' }}
      />
      <Dialog isVisible={!!confirmAction} onBackdropPress={() => setConfirmAction(null)}>
        <Dialog.Title
          title={confirmAction?.type === 'delete' ? trans.deleteDraftTitle : trans.sendToWebTitle}
        />
        <Text>
          {confirmAction?.type === 'delete'
            ? `${trans.deleteDraftMessage}${
                confirmAction?.item?.draftId ? ` ${trans.deleteDraftWebToo}` : ''
              }`
            : trans.sendToWebMessage}
        </Text>
        <Dialog.Actions>
          <Dialog.Button testID="confirm-action-button" onPress={handleConfirmAction}>
            {trans.buttonYes}
          </Dialog.Button>
          <Dialog.Button testID="cancel-action-button" onPress={() => setConfirmAction(null)}>
            {trans.buttonCancel}
          </Dialog.Button>
        </Dialog.Actions>
      </Dialog>
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
    // Clears the floating action button, which overlays the list rather than
    // sitting below it.
    paddingBottom: 88,
  },
  emptyListContent: {
    flexGrow: 1,
  },
  filterBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
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
    color: '#424242',
  },
  sortChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: '#cfd8dc',
    paddingVertical: 8,
    paddingHorizontal: 10,
    backgroundColor: '#ffffff',
  },
  sortChipActive: {
    backgroundColor: '#1651b6',
    borderColor: '#1651b6',
  },
  sortChipText: {
    fontSize: 14,
    color: '#424242',
  },
  sortChipTextActive: {
    color: '#ffffff',
  },
  swipeHint: {
    fontSize: 14,
    color: '#78909c',
    fontStyle: 'italic',
    paddingHorizontal: 12,
    paddingTop: 4,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
    paddingHorizontal: 4,
    gap: 8,
  },
  sectionHeaderText: {
    flex: 1,
    fontSize: 14,
    fontWeight: 'bold',
    color: '#37474f',
  },
  sectionHeaderCount: {
    fontSize: 14,
    color: '#607d8b',
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
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  itemDate: {
    fontSize: 12,
    color: '#9e9e9e',
  },
  itemMeta: {
    fontSize: 12,
    color: '#546e7a',
    marginTop: 2,
  },
  swipeRowInner: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  swipeActions: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-start',
    backgroundColor: '#f1f5f9',
  },
  swipeAction: {
    width: 56,
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  onWebLabel: {
    fontSize: 11,
    color: '#1651b6',
    fontWeight: 'bold',
  },
  // Amber, matching the low-storage bar: bound for the web, not there yet.
  pendingWebLabel: {
    fontSize: 11,
    color: '#b45309',
    fontWeight: 'bold',
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
