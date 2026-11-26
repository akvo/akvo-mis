import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { ListItem } from '@rneui/themed';
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
  SortControl,
  StatusChips,
} from '../components';
import useTheme from '../lib/theme';
import { getCurrentTimestamp } from '../form/lib';
import { crudDataPoints, crudForms } from '../database/crud';
import { refreshStorageWarning } from '../lib/submission-fallback';
import { parseGeo, geoFromAnswers, haversineMeters, formatDistance } from '../lib/distance';
import { QUESTION_TYPES } from '../lib/constants';

// Direction a sort mode opens on; re-tapping the active mode flips it (APP-586 D-4).
const DEFAULT_DIR = { name: 'asc', date: 'desc', distance: 'asc' };

// Pending/Synced count THIS device's own submissions (locallyCreated = 1), matching Home's
// tile semantics (crud-forms.selectLatestFormVersion). Registrations downloaded from the
// server are master data, not the user's synced work, so they are excluded from both.
const matchesStatus = (d, filter) => {
  if (filter === 'draft') {
    return d.submitted === 0;
  }
  if (filter === 'pending') {
    return d.submitted === 1 && !d.isSynced && d.locallyCreated === 1;
  }
  if (filter === 'synced') {
    return d.submitted === 1 && d.isSynced && d.locallyCreated === 1;
  }
  return true; // 'all'
};

const Submission = ({ navigation, route }) => {
  const [search, setSearch] = useState('');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [confirmAction, setConfirmAction] = useState(null);
  // APP-586: status chip, sort mode + direction, family counts and lazily-loaded family rows
  // (registration + monitoring submissions) per status.
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortMode, setSortMode] = useState('date');
  const [sortDir, setSortDir] = useState('desc');
  const [familyRows, setFamilyRows] = useState({});
  const [familyCounts, setFamilyCounts] = useState({ draft: 0, pending: 0, synced: 0 });
  // Armed only by openFamilyDraft, which is the one place that swaps the active form.
  const restoreFormOnFocusRef = useRef(false);

  const previousForm = FormState.useState((s) => s.previousForm);
  const activeForm = FormState.useState((s) => s.form);
  const activeLang = UIState.useState((s) => s.lang);
  const { id: activeUserId } = UserState.useState((s) => s);
  const currentLocation = UserState.useState((s) => s.currentLocation);
  const trans = i18n.text(activeLang);
  const theme = useTheme();
  const styles = getStyles(theme);
  const db = SQLite.useSQLiteContext();
  const refreshPage = UIState.useState((s) => s.refreshPage);

  // The registration list is the only place family drafts and distance make sense: a
  // monitoring list is already scoped to one uuid, whose rows share the registration location.
  const isRegistrationList = !activeForm?.parentId && !route?.params?.uuid;
  const origin = useMemo(
    () =>
      currentLocation?.coords
        ? { lat: currentLocation.coords.latitude, lng: currentLocation.coords.longitude }
        : null,
    [currentLocation],
  );
  const canDistance = isRegistrationList && !!origin;
  // Guard: if Distance is selected but location is lost, fall back to Date (and hide the toggle).
  const effectiveSortMode = sortMode === 'distance' && !canDistance ? 'date' : sortMode;
  // On a registration list, any status chip (Draft/Pending/Synced) is a family view: it shows the
  // registration form's AND its monitoring forms' submissions of that status, grouped by form.
  const usingFamily = statusFilter !== 'all' && isRegistrationList;

  // Question ids of the form's geo (GPS point) questions, for the distance fallback when a
  // datapoint's `geo` column is empty (server-downloaded master data keeps GPS only in answers).
  const geoQuestionIds = useMemo(() => {
    try {
      const form = activeForm?.json ? JSON.parse(activeForm.json) : null;
      return (form?.question_group || [])
        .flatMap((g) => g?.question || [])
        .filter((q) => q?.type === QUESTION_TYPES.geo)
        .map((q) => `${q.id}`);
    } catch (e) {
      return [];
    }
  }, [activeForm?.json]);

  const annotateRow = useCallback(async (res, statsByUuid) => {
    const createdAt = moment(res.createdAt).format('DD/MM/YYYY hh:mm A');
    const syncedAt = res.syncedAt ? moment(res.syncedAt).format('DD/MM/YYYY hh:mm A') : '-';
    // Flag unsynced rows whose local photo files no longer exist — they will never upload
    // until the user retakes the photo.
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
        Sentry.captureMessage(`[Submission] unreadable answers on datapoint ${res.id}`);
        Sentry.captureException(error);
        needsRetake = false;
      }
    }
    const monitoring = statsByUuid?.get(res.uuid);
    const toMs = (x) => {
      const ms = x ? moment(x).valueOf() : 0;
      return Number.isNaN(ms) ? 0 : ms;
    };
    // "Latest first" uses the family's most recent activity: the registration's own date OR its
    // newest monitoring submission, so a plot with recent monitoring rises to the top (APP-586).
    const regMs = res.locallyCreated
      ? toMs(res.submittedAt) || toMs(res.createdAt)
      : toMs(res.syncedAt) || toMs(res.createdAt);
    const monMs = toMs(monitoring?.lastSubmissionAt);
    return {
      ...res,
      createdAt,
      syncedAt,
      createdTs: toMs(res.createdAt),
      activityTs: Math.max(regMs, monMs),
      isSynced: !!res.syncedAt,
      needsRetake,
      monitoringDrafts: monitoring?.draftCount || 0,
      monitoringSubmissions: monitoring?.submissionCount || 0,
      lastMonitoringAt: monitoring?.lastSubmissionAt || null,
    };
  }, []);

  const fetchData = useCallback(async () => {
    if (!activeForm?.id) {
      setLoading(false);
      return;
    }
    try {
      const registrationList = !activeForm?.parentId && !route?.params?.uuid;
      if (registrationList) {
        setFamilyCounts(
          await crudDataPoints.countFamilyByStatus(db, {
            formDbId: activeForm.id,
            backendFormId: activeForm.formId,
            user: activeUserId,
          }),
        );
      }
      const stats = registrationList
        ? await crudDataPoints.getMonitoringStats(db, activeForm.formId, activeUserId)
        : [];
      const statsByUuid = new Map(stats.map((st) => [st.uuid, st]));
      const baseRows = await crudDataPoints.selectDataPointsByFormAndSubmitted(db, {
        form: activeForm.id,
        user: activeUserId,
        uuid: route?.params?.uuid || null,
      });
      const rows = await Promise.all(baseRows.map((res) => annotateRow(res, statsByUuid)));
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
  }, [activeForm?.id, activeForm?.formId, activeForm?.parentId, activeUserId, db, route?.params?.uuid, annotateRow]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Lazily load the family rows for the active status chip on a registration list (APP-586):
  // Draft/Pending/Synced each fetch the family (registration + monitoring) submissions of that
  // status, grouped by form. Cached per status until invalidated (refresh / delete).
  useEffect(() => {
    if (!usingFamily || familyRows[statusFilter] || !activeForm?.id) {
      return undefined;
    }
    let cancelled = false;
    crudDataPoints
      .getFamilyByStatus(db, {
        formDbId: activeForm.id,
        backendFormId: activeForm.formId,
        user: activeUserId,
        status: statusFilter,
      })
      .then((rows) => {
        if (cancelled) {
          return;
        }
        const annotated = rows.map((r) => ({
          ...r,
          createdAt: moment(r.createdAt).format('DD/MM/YYYY hh:mm A'),
          createdTs: moment(r.createdAt).valueOf(),
          isSynced: !!r.syncedAt,
        }));
        setFamilyRows((prev) => ({ ...prev, [statusFilter]: annotated }));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [usingFamily, statusFilter, familyRows, db, activeForm?.id, activeForm?.formId, activeUserId]);

  useEffect(() => {
    if (refreshPage) {
      setFamilyRows({});
      fetchData();
      UIState.update((s) => {
        s.refreshPage = false;
      });
    }
  }, [refreshPage, activeForm?.id, fetchData]);

  useEffect(
    () =>
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

  // On a registration list the chip counts are family-wide (registration + monitoring), matching
  // Home; on a monitoring list they are derived from the loaded rows for that uuid.
  const counts = useMemo(() => {
    if (isRegistrationList) {
      return { all: data.length, ...familyCounts };
    }
    return {
      all: data.length,
      draft: data.filter((d) => d.submitted === 0).length,
      pending: data.filter((d) => d.submitted === 1 && !d.isSynced && d.locallyCreated === 1).length,
      synced: data.filter((d) => d.submitted === 1 && d.isSynced && d.locallyCreated === 1).length,
    };
  }, [data, familyCounts, isRegistrationList]);

  const filteredRows = useMemo(() => {
    // A status chip on a registration list reads the family rows for that status (already filtered
    // by the query); otherwise filter the loaded rows by the chip.
    const source = usingFamily ? familyRows[statusFilter] || [] : data;
    const q = search.trim().toLowerCase();
    return source.filter((d) => {
      const byStatus = usingFamily || statusFilter === 'all' || matchesStatus(d, statusFilter);
      const bySearch = !q || d?.name?.toLowerCase().includes(q);
      return byStatus && bySearch;
    });
  }, [data, familyRows, usingFamily, statusFilter, search]);

  // Rows → FlatList data, with labeled group-header sentinels for the two grouped cases
  // (family-draft per-form names, and the distance "No location recorded" group). (APP-586 D-1)
  const listData = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1;
    // Date sort uses the family activity timestamp when present (registration rows), so a plot
    // with recent monitoring sorts first; family submission rows fall back to their own createdTs.
    const dateKey = (d) => (d.activityTs ?? d.createdTs) || 0;
    const byNameOrDate = (a, b) =>
      effectiveSortMode === 'name'
        ? (a.name || '').localeCompare(b.name || '') * dir
        : (dateKey(a) - dateKey(b)) * dir;

    if (usingFamily) {
      const groups = new Map();
      filteredRows.forEach((d) => {
        const key = `${d.groupFormId}`;
        if (!groups.has(key)) {
          groups.set(key, { title: d.groupName, rows: [] });
        }
        groups.get(key).rows.push(d);
      });
      const out = [];
      [...groups.values()].forEach((g) => {
        out.push({ header: `fam-${g.title}`, title: g.title });
        [...g.rows].sort(byNameOrDate).forEach((r) => out.push(r));
      });
      return out;
    }

    if (effectiveSortMode === 'distance') {
      const annotated = filteredRows.map((d) => {
        const coord = parseGeo(d.geo) || geoFromAnswers(d.json, geoQuestionIds);
        return { ...d, distanceM: coord ? haversineMeters(origin, coord) : null };
      });
      const located = annotated
        .filter((d) => d.distanceM != null)
        .sort((a, b) => (a.distanceM - b.distanceM) * dir);
      const noLoc = annotated.filter((d) => d.distanceM == null);
      return noLoc.length
        ? [...located, { header: 'no-location', title: trans.noLocationGroup }, ...noLoc]
        : located;
    }

    return [...filteredRows].sort(byNameOrDate);
  }, [
    filteredRows,
    usingFamily,
    effectiveSortMode,
    sortDir,
    origin,
    geoQuestionIds,
    trans.noLocationGroup,
  ]);

  const goToNewForm = () => {
    FormState.update((s) => {
      s.surveyStart = getCurrentTimestamp();
      s.prevAdmAnswer = null;
    });
    navigation.push('FormPage', { ...route?.params, newSubmission: true });
  };

  const goToDetails = async (item) => {
    const { json: valuesJSON, name: dataPointName } = item;
    // A family row from another form (a monitoring submission opened from a registration-list
    // family view) must be read against ITS OWN form definition. Load it and remember the current
    // form so the focus/beforeRemove listeners restore it on the way back, like openFamilyDraft.
    if (item.form && item.form !== activeForm?.id) {
      const targetForm = await crudForms.selectFormById(db, { id: item.form });
      if (targetForm) {
        FormState.update((s) => {
          s.previousForm = activeForm;
          s.form = targetForm;
        });
        restoreFormOnFocusRef.current = true;
      }
    }
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
    navigation.push('FormOptions', { id, name, uuid, formId: activeForm.formId });
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
    // A monitoring submission shown in a family view (groupParentId set) opens its own detail,
    // not the registration's options.
    if (activeForm?.parentId || selectedData?.groupParentId) {
      goToDetails(selectedData);
    } else {
      goToFormOptions(selectedData);
    }
  };

  const openFamilyDraft = async (item) => {
    // A row from another form in the family: load that form first, exactly as FormOptions does,
    // and remember the registration form so the existing listeners restore it on the way back.
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

  // A URI is only safe to delete when no other row references it.
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
        // Atomic: the server copy goes first, and the local row only follows if that succeeded.
        if (item.draftId) {
          await api.delete(`/draft-list/${item.draftId}`);
        }
        await removeLocalFiles(item);
        await crudDataPoints.deleteDataPoint(db, item.id);
        await refreshStorageWarning();
        setFamilyRows({});
        UIState.update((s) => {
          s.refreshPage = true;
        });
      }
      setFamilyRows({});
      await fetchData();
    } catch (error) {
      Sentry.captureMessage('[Submission] Unable to apply draft action');
      Sentry.captureException(error);
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.deleteDraftFailedText, ToastAndroid.LONG);
      }
    }
  };

  const askDelete = (item) => {
    setConfirmAction({ type: 'delete', item });
  };

  // One line under the name: the date, plus the monitoring count on the registration list.
  const getMeta = (item) => {
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

  const onPickSort = (nextMode) => {
    if (nextMode === effectiveSortMode) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortMode(nextMode);
    setSortDir(DEFAULT_DIR[nextMode]);
  };

  const renderItem = ({ item }) => {
    if (item.header) {
      return (
        <Text style={styles.groupHeader} testID={`group-${item.header}`}>
          {item.title}
        </Text>
      );
    }
    const distanceLabel = item.distanceM != null ? formatDistance(item.distanceM, trans) : null;
    // Submitted rows have nothing to swipe to — keep them plain.
    if (item.submitted !== 0) {
      return (
        <TouchableOpacity
          onPress={() => onClickItem(item)}
          testID={`submission-item-${item.id}`}
          style={styles.item}
          activeOpacity={0.6}
        >
          <DatapointCard item={item} meta={getMeta(item)} distance={distanceLabel} trans={trans} />
        </TouchableOpacity>
      );
    }
    return (
      <ListItem.Swipeable
        onPress={() => openFamilyDraft(item)}
        containerStyle={styles.swipeItem}
        testID={`submission-item-${item.id}`}
        leftWidth={56}
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
          </View>
        }
      >
        <DatapointCard item={item} meta={getMeta(item)} distance={distanceLabel} trans={trans} />
      </ListItem.Swipeable>
    );
  };

  const keyExtractor = (item) => (item.header ? item.header : `${item.id}`);

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
          <StatusChips counts={counts} active={statusFilter} onSelect={setStatusFilter} trans={trans} />
          <SortControl
            mode={effectiveSortMode}
            dir={sortDir}
            onPick={onPickSort}
            showDistance={canDistance}
            trans={trans}
          />
          {statusFilter === 'draft' && filteredRows.length > 0 && (
            <Text style={styles.swipeHint} testID="swipe-hint">
              {trans.swipeHintText}
            </Text>
          )}
          <View style={styles.listSection}>
            <FlatList
              data={listData}
              renderItem={renderItem}
              keyExtractor={keyExtractor}
              testID="submission-list"
              contentContainerStyle={[
                styles.flatListContent,
                listData.length === 0 && styles.emptyListContent,
              ]}
              ListEmptyComponent={renderEmptyState}
              ListFooterComponent={
                filteredRows.length > 0 ? (
                  <DatapointLegend trans={trans} items={filteredRows} />
                ) : null
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
        title={trans.deleteDraftTitle}
        message={trans.deleteDraftMessage}
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
            type: 'danger',
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
    groupHeader: {
      fontSize: 12,
      fontWeight: '700',
      letterSpacing: 0.4,
      textTransform: 'uppercase',
      color: theme.text.tertiary,
      paddingTop: 12,
      paddingBottom: 4,
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
