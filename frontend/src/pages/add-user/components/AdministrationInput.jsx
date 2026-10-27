import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Select, Space } from "antd";
import PropTypes from "prop-types";
import { store, api } from "../../../lib";

const AdministrationInput = ({
  width = "100%",
  maxLevel = null,
  onChange,
  value = [],
  disabled = false,
  ...props
}) => {
  const { user } = store.useState((state) => state);
  const [administration, setAdministration] = useState([]);
  const maxLevelValue = useMemo(() => {
    return maxLevel || user?.administration?.level || null;
  }, [maxLevel, user]);

  const fetchUserAdmin = useCallback(async () => {
    if (user) {
      try {
        const { data: apiData } = await api.get(
          `administration/${user.administration.id}`
        );
        setAdministration([apiData]);
      } catch (error) {
        console.error(error);
      }
    }
  }, [user]);

  useEffect(() => {
    fetchUserAdmin();
  }, [fetchUserAdmin]);

  // Initialize administration based on value prop
  useEffect(() => {
    if (value && value.length > 0 && administration.length === 0) {
      const initializeAdministration = async () => {
        try {
          // Get the last administration ID from value
          const lastAdminId = Array.isArray(value)
            ? value[value.length - 1]
            : value;
          const { data: adminData } = await api.get(
            `administration/${lastAdminId}`
          );

          // Build administration hierarchy
          const buildHierarchy = async (admin, acc = []) => {
            acc.unshift(admin);
            if (admin.level > 0 && admin.parent) {
              const { data: parentData } = await api.get(
                `administration/${admin.parent}`
              );
              return buildHierarchy(parentData, acc);
            }
            return acc;
          };

          const hierarchy = await buildHierarchy(adminData);
          setAdministration(hierarchy);
        } catch (error) {
          console.error("Error initializing administration:", error);
        }
      };

      initializeAdministration();
    }
  }, [value, administration.length]);

  // When a seeded/pre-filled administration is deeper than the role allows,
  // the render below trims the visible cascade to maxLevel but the form value
  // keeps the deeper id. That let the UI show e.g. the Province ancestor while
  // the stored value stayed a District, which the backend rejects as "Role and
  // administration level mismatch". Reconcile the form value to the deepest
  // node the current maxLevel actually exposes.
  useEffect(() => {
    if (!maxLevelValue || administration.length === 0 || !onChange) {
      return;
    }
    const effective = administration[maxLevelValue - 1]?.id;
    const current = Array.isArray(value) ? value[value.length - 1] : value;
    if (effective && effective !== current) {
      onChange([effective]);
    }
  }, [administration, maxLevelValue, value, onChange]);

  const handleChange = async (e, index) => {
    if (!e) {
      return;
    }

    const { data: selectedAdm } = await api.get(`administration/${e}`);
    const admItems = [selectedAdm];

    // Update local administration state
    const newAdministration = [...administration];
    newAdministration.length = index + 1;
    newAdministration.push(...admItems);
    setAdministration(newAdministration);

    if (onChange) {
      onChange([e]);
    }
  };

  const handleClear = (index) => {
    const newAdministration = [...administration];
    newAdministration.length = index + 1;
    setAdministration(newAdministration);

    if (onChange) {
      onChange([]);
    }
  };

  if (administration) {
    return (
      <Space {...props} style={{ width: "100%" }}>
        {administration
          .filter(
            (x) =>
              (x?.children?.length && !maxLevelValue) ||
              (maxLevelValue &&
                x?.level < maxLevelValue - 1 &&
                x?.children?.length) // show children based on maxLevel
          )
          .map((region, regionIdx) => {
            if (maxLevelValue === null || regionIdx + 1 < maxLevelValue) {
              const selectValues = administration[regionIdx + 1]?.id || null;
              return (
                <div key={regionIdx}>
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
                    disabled={disabled}
                    allowClear
                    showSearch
                    filterOption={true}
                    optionFilterProp="children"
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
      </Space>
    );
  }
  return "";
};

AdministrationInput.propTypes = {
  maxLevel: PropTypes.number,
  onChange: PropTypes.func,
  value: PropTypes.array,
  disabled: PropTypes.bool,
  width: PropTypes.string,
};

export default React.memo(AdministrationInput);
