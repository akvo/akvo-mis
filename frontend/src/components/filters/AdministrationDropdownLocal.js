import React, { useCallback, useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { Select, Space } from "antd";
import { api, store } from "../../lib";

/**
 * Component-local cascading admin dropdown.
 *
 * Mirrors the visual cascade of `AdministrationDropdown` but owns its
 * selection state in React `useState` instead of the global Pullstate
 * `store.administration`. Designed for embedded use inside a single
 * `custom_component` (e.g. IndividualEPSOverview) so picking an admin
 * here does NOT trigger the dashboard-wide refetch ripple that the
 * global dropdown causes via `DashboardFilters`.
 *
 * Lifecycle:
 *   - On mount, fetches the user's root admin via `/administration/<id>`
 *     and seeds `levels[0]`. Same payload shape as `store.administration`
 *     entries: `{ id, name, level, children: [...] }`.
 *   - Picking a child select fetches its full detail (so the next-level
 *     children are available) and appends to `levels`.
 *   - Clearing a select truncates `levels` to that index.
 *   - After every change, `onChange(deepest)` fires with the deepest
 *     non-root level (or `null` when only root remains, matching the
 *     contract used by `useIndividualOverviewData`).
 *
 * Forbidden by design:
 *   - No `store.update(...)` call. The component never writes to the
 *     global store, so it cannot leak its selection to other widgets
 *     on the page or to other pages reached via navigation.
 *
 * @param {object}   props
 * @param {Function} props.onChange  (deepest: AdminLevel | null) => void
 * @param {number}   [props.width]   px width applied to each select
 * @param {boolean}  [props.loading] disables every select while true
 */
const AdministrationDropdownLocal = ({
  onChange,
  width = 160,
  loading = false,
  rootAdministrationId = null,
}) => {
  const user = store.useState((s) => s.user);

  const [levels, setLevels] = useState([]);
  const mountedRef = useRef(true);

  const seedId = user?.administration?.id || rootAdministrationId;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!seedId) {
      return () => {};
    }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(`administration/${seedId}`);
        if (cancelled || !mountedRef.current) {
          return;
        }
        setLevels([data]);
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("AdministrationDropdownLocal: root fetch failed", error);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [seedId]);

  // Replicates the role-based child filter from AdministrationDropdown.js
  // so non-superusers only see admin units inside their assigned roles.
  const filterChildren = useCallback(
    (children) => {
      if (!Array.isArray(children)) {
        return [];
      }
      if (user?.is_superuser || !user?.roles?.length) {
        return children;
      }
      return children.filter((c) =>
        user.roles.some((role) => {
          if (role?.administration?.level_id === c.level) {
            return role.administration.id === c.id;
          }
          return true;
        })
      );
    },
    [user]
  );

  const emitDeepest = (next) => {
    if (!onChange) {
      return;
    }
    // Root (`levels.length === 1`) is the user's own scope — treat as
    // "no embedded selection" so callers see `null`, matching the
    // deepestSelectedAdmin contract in useIndividualOverviewData.
    const deepest = next.length > 1 ? next[next.length - 1] : null;
    onChange(deepest);
  };

  const handlePick = async (idx, childId) => {
    if (!childId) {
      return;
    }
    try {
      const { data: child } = await api.get(`administration/${childId}`);
      if (!mountedRef.current) {
        return;
      }
      setLevels((prev) => {
        const next = prev.slice(0, idx + 1).concat([child]);
        emitDeepest(next);
        return next;
      });
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("AdministrationDropdownLocal: child fetch failed", error);
    }
  };

  const handleClear = (idx) => {
    setLevels((prev) => {
      const next = prev.slice(0, idx + 1);
      emitDeepest(next);
      return next;
    });
  };

  return (
    <Space style={{ width: "100%" }}>
      {levels
        .filter((lvl) => lvl?.children?.length)
        .map((lvl, idx) => (
          <div key={`adm-local-${idx}`}>
            <Select
              placeholder={`Select ${lvl?.children_level_name || ""}`}
              style={{ width }}
              value={levels[idx + 1]?.id || null}
              onChange={(e) => handlePick(idx, e)}
              onClear={() => handleClear(idx)}
              getPopupContainer={(trigger) => trigger.parentNode}
              dropdownMatchSelectWidth={false}
              disabled={loading}
              allowClear
              showSearch
              filterOption={true}
              optionFilterProp="children"
              className="custom-select"
            >
              {filterChildren(lvl.children).map((opt, optIdx) => (
                <Select.Option key={`opt-${idx}-${optIdx}`} value={opt.id}>
                  {opt.name}
                </Select.Option>
              ))}
            </Select>
          </div>
        ))}
    </Space>
  );
};

AdministrationDropdownLocal.propTypes = {
  onChange: PropTypes.func.isRequired,
  width: PropTypes.number,
  loading: PropTypes.bool,
  rootAdministrationId: PropTypes.number,
};

export default AdministrationDropdownLocal;
