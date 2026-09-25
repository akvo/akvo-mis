import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { View, Text } from 'react-native';
import { Dropdown } from 'react-native-element-dropdown';

import { FieldLabel } from '../support';
import getStyles from '../styles';
import { FormState } from '../../store';
import { i18n, cascades } from '../../lib';
import useTheme from '../../lib/theme';

const TypeCascade = ({
  onChange,
  value,
  keyform,
  id,
  label,
  required,
  source,
  api,
  requiredSign = '*',
  disabled = false,
  tooltip = null,
  hasError = false,
}) => {
  const theme = useTheme();
  const styles = getStyles(theme);
  const [dataSource, setDataSource] = useState([]);
  const [dropdownItems, setDropdownItems] = useState([]);
  const [isLoaded, setIsLoaded] = useState(false);
  const prevAdmAnswer = FormState.useState((s) => s.prevAdmAnswer);
  const cascadesValue = FormState.useState((s) => s.cascades?.[id]);
  const activeLang = FormState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const requiredValue = required ? requiredSign : null;
  const {
    cascade_parent: cascadeParent,
    cascade_type: cascadeType,
    parent_id: parentId,
  } = source || {};
  const queryParams = api?.query_params || '';
  // extract max_level from queryParams if present
  const maxLevelMatch = queryParams.match(/max_level=(\d+)/);
  const maxLevel = maxLevelMatch ? parseInt(maxLevelMatch[1], 10) : null;

  const groupBy = (array, property) => {
    const gd = array
      .sort((a, b) => a?.name?.localeCompare(b?.name))
      .reduce((groups, item) => {
        const key = item[property];
        if (!groups[key]) {
          groups[key] = [];
        }
        groups[key].push(item);
        return groups;
      }, {});
    const groupedData = {};
    Object.entries(gd).forEach(([key, val]) => {
      groupedData[key] = val;
    });
    return groupedData;
  };

  const handleOnChange = (index, val, admLevel) => {
    const nextIndex = index + 1;
    const updatedItems = dropdownItems
      .slice(0, nextIndex)
      .map((d, dx) => (dx === index ? { ...d, value: val } : d));

    const options = dataSource?.filter((d) => d?.parent === val);

    if (options.length && (maxLevel ? admLevel - 1 < maxLevel : true)) {
      updatedItems.push({
        options,
        value: null,
      });
    }
    const dropdownValues = updatedItems.filter((dd) => dd.value);
    const finalValues = dropdownValues.slice(-1).map((dd) => dd.value);
    onChange(id, finalValues);
    if (finalValues) {
      const { options: selectedOptions, value: selectedValue } = dropdownValues.pop();
      const findSelected = selectedOptions?.find((o) => o.id === selectedValue);
      const cascadeName = findSelected?.full_path_name;
      FormState.update((s) => {
        s.cascades = { ...s.cascades, [id]: cascadeName };
        s.prevAdmAnswer = source?.file === 'administrator.sqlite' ? finalValues : s.prevAdmAnswer;
      });
    }
    setDropdownItems(updatedItems);
  };

  const initialDropdowns = useMemo(() => {
    const parentIDs =
      cascadeParent === 'administrator.sqlite' ? prevAdmAnswer || [] : parentId || [0];
    const nationalAdm = dataSource?.find((ds) => !ds?.parent);
    const defaultAdm = value?.[0] ? dataSource?.find((ds) => ds?.id === value[0]) : null;

    // Helper function to resolve value (string name to ID or keep ID)
    const resolveValue = (options, defaultValue) => {
      if (!defaultValue) {
        return null;
      }

      if (typeof defaultValue === 'string') {
        const found = options.find((o) => o?.name === defaultValue);
        return found ? found.id : null;
      }

      if (Array.isArray(value) && value.length) {
        const found = options.find((o) => value.includes(o?.id));
        return found?.id || options?.[options.length - 1]?.id || null;
      }

      return defaultValue;
    };

    // Handle case where defaultAdm exists (reconstruct path)
    if (defaultAdm?.path) {
      const pathParts = [
        ...defaultAdm.path
          .split('.')
          .filter(Boolean)
          .map((part) => part.trim())
          .map((part) => parseInt(part, 10)),
        defaultAdm?.id,
      ];

      const matchIndex = pathParts.findIndex((part) => parentIDs.includes(part));
      const modifiedPathParts = matchIndex !== -1 ? pathParts.slice(matchIndex) : pathParts;

      return modifiedPathParts.map((part, px) => {
        const options = dataSource?.filter((d) =>
          px === 0 ? parentIDs.includes(d?.id) : d?.parent === modifiedPathParts?.[px - 1],
        );
        return {
          options,
          value: part,
        };
      });
    }

    // Filter data source based on cascadeType and parentIDs
    const filterDs = dataSource
      ?.filter((ds) => {
        if (cascadeType && ds?.entity) {
          return ds.entity === cascadeType;
        }
        return true;
      })
      ?.filter((ds) => {
        if (cascadeParent) {
          return parentIDs.includes(ds?.parent);
        }
        return (
          parentIDs.includes(ds?.parent) ||
          parentIDs.includes(ds?.id) ||
          value?.includes(ds?.id) ||
          value?.includes(ds?.parent)
        );
      });

    // Handle administrator.sqlite case
    if (cascadeParent === 'administrator.sqlite') {
      if (!filterDs?.length) return [];

      const defaultValue = filterDs.find((d) => d?.name === value?.[0] || d?.id === value?.[0])?.id;

      return [
        {
          options: filterDs,
          value: defaultValue || value?.[0] || null,
        },
      ];
    }

    // Group by parent and handle national group special case
    const groupedDs = groupBy(filterDs, 'parent');
    const groupValues = Object.values(groupedDs);
    if (!groupValues.length) {
      return [];
    }

    const hasMultipleGroups = parentIDs.length > 1 && Object.keys(groupedDs).length > 1;

    if (hasMultipleGroups) {
      const nationalGroup = Object.entries(groupedDs).find(
        ([key]) => parseInt(key, 10) === nationalAdm?.id,
      );

      if (nationalGroup) {
        return [
          {
            options: nationalGroup[1],
            value: value?.[0] || null,
          },
        ];
      }
    }

    // Always render a single dropdown on first load; handleOnChange pushes
    // the next level when the user selects a value.
    const firstGroupOptions = groupValues[0];
    return [
      {
        options: firstGroupOptions,
        value: resolveValue(firstGroupOptions, value?.[0]),
      },
    ];
  }, [dataSource, cascadeParent, cascadeType, parentId, prevAdmAnswer, value]);

  const loadCascadeData = useCallback(async () => {
    if (!isLoaded && source?.file) {
      setIsLoaded(true);

      const rows = await cascades.loadDataSource(source);
      setDataSource(rows);

      // Update entity options if cascadeType is defined
      if (cascadeType) {
        FormState.update((s) => {
          s.entityOptions[id] = rows?.filter((a) => a?.entity === cascadeType);
        });
      }
      // Set initial cascade
      if (!cascadesValue && value?.length) {
        const cascadeID = value.slice(-1)?.[0];
        // Filter rows with cascadeID instead of making another loadDataSource call
        const csValue = rows?.find((row) => row.id === cascadeID);
        FormState.update((s) => {
          s.cascades = { ...s.cascades, [id]: csValue?.full_path_name };
        });
      }
    }
  }, [source, id, value, cascadesValue, cascadeType, isLoaded]);

  useEffect(() => {
    loadCascadeData();
  }, [loadCascadeData]);

  useEffect(() => {
    if (
      (dropdownItems.length === 0 && initialDropdowns.length) ||
      (source?.cascade_parent && prevAdmAnswer)
    ) {
      /**
       * Reset entity cascade options when the prevAdmAnswer changes.
       */
      setDropdownItems(initialDropdowns);
    }
  }, [dropdownItems, initialDropdowns, dataSource, prevAdmAnswer, id, source]);

  const handleDefaultValue = useCallback(() => {
    if (typeof value?.[0] === 'string' && dropdownItems.length) {
      const lastItem = dropdownItems.slice(-1)?.[0] || { value: null, options: [] };
      if (lastItem?.value) {
        onChange(id, [lastItem.value]);
      }
    }
  }, [value, id, dropdownItems, onChange]);

  useEffect(() => {
    handleDefaultValue();
  }, [handleDefaultValue]);

  if (!dropdownItems.length) {
    return null;
  }

  return (
    <View testID="view-type-cascade">
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <Text testID="text-values" style={styles.cascadeValues}>
        {value}
      </Text>
      <View style={styles.cascadeContainer}>
        {dropdownItems.map((item, index) => {
          const hasSearch = item?.options.length > 3;
          const style = {
            ...styles.dropdownField,
            ...(disabled ? styles.dropdownFieldDisabled : {}),
            ...(hasError ? styles.inputFieldError : {}),
          };
          return (
            <Dropdown
              // eslint-disable-next-line react/no-array-index-key
              key={index}
              labelField="name"
              valueField="id"
              testID={`dropdown-cascade-${index}`}
              containerStyle={{
                backgroundColor: theme.bg.surfaceElevated1,
                borderRadius: 12,
              }}
              data={item?.options}
              search={hasSearch}
              searchPlaceholder={trans.searchPlaceholder}
              onChange={({ id: selectedID, level }) => handleOnChange(index, selectedID, level)}
              value={item.value}
              style={style}
              placeholder={trans.selectItem}
              placeholderStyle={{ color: theme.input.text }}
              selectedTextStyle={{ color: theme.input.textInput }}
              inputSearchStyle={{
                borderRadius: 12,
                backgroundColor: theme.bg.surfaceTertiary,
                borderColor: 'transparent',
                color: theme.text.primary,
                paddingHorizontal: 12,
              }}
              maxHeight={500}
              disable={disabled}
            />
          );
        })}
      </View>
    </View>
  );
};

export default TypeCascade;
