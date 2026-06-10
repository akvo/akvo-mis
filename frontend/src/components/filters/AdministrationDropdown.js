import React, { useEffect, useState, useMemo, useCallback } from "react";
import "./style.scss";
import { Select, Space, Checkbox, Row, Col } from "antd";
import PropTypes from "prop-types";
import uniq from "lodash/uniq";
import { store, api, uiText } from "../../lib";

const AdministrationDropdown = ({
  loading = false,
  withLabel = false,
  width = 160,
  hidden = false,
  maxLevel = null,
  allowMultiple = false,
  persist = false,
  onChange,
  limitLevel = false,
  showSelectAll = false,
  selectedAdministrations = [],
  ...props
}) => {
  const { user, administration, levels, language } = store.useState(
    (state) => state
  );
  const [checked, setChecked] = useState(false);
  const lowestLevel = levels
    .slice()
    .sort((a, b) => a.level - b.level)
    .slice(-1)?.[0];
  /**
   * Get lowest level administrator from maxLevel.
   * otherwise, sort asc by level and get the last item from levels global state
   */
  const currLevel = levels?.find((l) => l?.id === maxLevel) || lowestLevel;

  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const fetchUserAdmin = useCallback(async () => {
    if (user && !persist) {
      try {
        const { data: apiData } = await api.get(
          `administration/${user.administration.id}`
        );
        store.update((s) => {
          s.administration = [apiData];
        });
      } catch (error) {
        console.error(error);
      }
    }
  }, [user, persist]);

  useEffect(() => {
    fetchUserAdmin();
  }, [fetchUserAdmin]);

  useEffect(() => {
    const multiadministration = administration?.find(
      (admLevel) => admLevel?.level === currLevel?.level - 1
    )?.children;
    if (multiadministration?.length === selectedAdministrations?.length) {
      setChecked(true);
    }
  }, [administration, selectedAdministrations, currLevel?.level]);

  const handleChange = async (e, index) => {
    if (!e) {
      return;
    }
    let admItems = null;
    if (Array.isArray(e)) {
      const multiadministration = administration
        ?.find((admLevel) => admLevel?.level === currLevel?.level - 1)
        ?.children.filter((admItem) => e.includes(admItem.id));
      admItems = multiadministration;
    } else {
      const { data: selectedAdm } = await api.get(`administration/${e}`);
      admItems = [selectedAdm];
    }
    store.update((s) => {
      s.administration.length = index + 1;
      s.administration = s.administration.concat(admItems);
    });
    if (onChange) {
      const _values = allowMultiple && Array.isArray(e) ? e : [e];
      onChange(_values);
    }
  };

  const onSelectAll = (e) => {
    if (e.target.checked) {
      setChecked(true);
      const admItems =
        administration?.find(
          (admLevel) => admLevel?.level === currLevel?.level - 1
        )?.children || [];
      if (selectedAdministrations.length === admItems.length) {
        return;
      }
      store.update((s) => {
        s.administration = s.administration.concat(admItems);
      });
      if (onChange) {
        const _values = admItems
          .filter((item) => {
            if (!user?.is_superuser && user?.roles?.length) {
              return user.roles.some((role) => {
                if (role?.administration?.level_id === item.level) {
                  return role.administration.id === item.id;
                }
                return true;
              });
            }
            return item;
          })
          .map((item) => item.id);
        onChange(_values);
      }
    } else {
      setChecked(false);
      store.update((s) => {
        s.administration = s.administration.filter(
          (data) => data.level <= currLevel?.level - 1
        );
      });
      if (onChange) {
        onChange(
          administration.filter((data) => data.level <= currLevel?.level - 1)
        );
      }
    }
  };

  const handleClear = (index) => {
    store.update((s) => {
      s.administration.length = index + 1;
    });
  };

  if (administration && !hidden) {
    return (
      <Space {...props} style={{ width: "100%" }}>
        {administration
          .filter(
            (x) =>
              (x?.children?.length && !maxLevel) ||
              (maxLevel && x?.level < maxLevel - 1 && x?.children?.length) // show children based on maxLevel
          )
          .filter((l) => !limitLevel || l?.level !== limitLevel)
          .map((region, regionIdx) => {
            if (maxLevel === null || regionIdx + 1 < maxLevel) {
              /**
               * Find last item by checking:
               * - regionIdx + 1 = next index is equal with parent maxLevel
               * OR
               * - region.level = current level is equal with parent lowest level
               */
              const isLastItem =
                (maxLevel && maxLevel - 1 === regionIdx + 1) ||
                region.level === currLevel?.level - 1;
              const selectMode =
                allowMultiple && isLastItem ? "multiple" : null;
              const selectValues =
                selectMode === "multiple"
                  ? uniq(
                      administration
                        ?.slice(regionIdx + 1, administration.length)
                        ?.filter(
                          (a) =>
                            region.children?.some((c) => c?.id === a?.id) &&
                            (!user?.is_superuser && user?.roles?.length
                              ? user.roles.some((role) => {
                                  if (
                                    role?.administration?.level_id === a.level
                                  ) {
                                    return role.administration.id === a.id;
                                  }
                                  return true;
                                })
                              : true)
                        )
                        ?.map((a) => a?.id)
                    )
                  : administration[regionIdx + 1]?.id || null;
              return (
                <div key={regionIdx}>
                  {withLabel ? (
                    <label className="ant-form-item-label">
                      {region?.children_level_name || ""}
                    </label>
                  ) : (
                    ""
                  )}
                  <Select
                    placeholder={`Select ${region?.children_level_name || ""}`}
                    style={{ width: width }}
                    onChange={(e) => {
                      handleChange(e, regionIdx);
                    }}
                    onClear={() => {
                      handleClear(regionIdx);
                    }}
                    getPopupContainer={(trigger) => trigger.parentNode}
                    dropdownMatchSelectWidth={false}
                    value={selectValues}
                    disabled={loading}
                    allowClear
                    showSearch
                    filterOption={true}
                    optionFilterProp="children"
                    mode={selectMode}
                    className="custom-select"
                  >
                    {region.children
                      ?.filter((c) => {
                        if (!user?.is_superuser && user?.roles?.length) {
                          return user.roles.some((role) => {
                            if (role?.administration?.level_id === c.level) {
                              return role.administration.id === c.id;
                            }
                            return true;
                          });
                        }
                        return c;
                      })
                      .map((optionValue, optionIdx) => (
                        <Select.Option key={optionIdx} value={optionValue.id}>
                          {optionValue.name}
                        </Select.Option>
                      ))}
                  </Select>
                </div>
              );
            }
          })}
        {showSelectAll && maxLevel === lowestLevel.id && (
          <Row className="form-row">
            <Col span={24}>
              <Checkbox onChange={onSelectAll} checked={checked}>
                {text.checkboxSelectAll.replace("{{name}}", currLevel?.name)}
              </Checkbox>
            </Col>
          </Row>
        )}
      </Space>
    );
  }
  return "";
};

AdministrationDropdown.propTypes = {
  loading: PropTypes.bool,
  persist: PropTypes.bool,
  hidden: PropTypes.bool,
  maxLevel: PropTypes.number,
  allowMultiple: PropTypes.bool,
  onChange: PropTypes.func,
};

export default React.memo(AdministrationDropdown);
