import { useEffect, useState } from "react";
import { api } from "../../../lib";
import getQuestionOptions from "./getQuestionOptions";

/**
 * Fetches and caches the per-parent_id bucket value for the active
 * select filter. Both question-id and formula filters route to
 * /visualization/values/formula (decision #22):
 *   - formula filters pass the config JSON directly
 *   - question-id filters build an equivalent option_equals formula
 *     from the published forms (getForms()) so the formula endpoint
 *     handles both modes
 *
 * @param {{
 *   activeFilter: Object | null,
 *   filterState: Object,
 * }} args
 * @returns {{ byParent: Object, loading: boolean, error: any }}
 */
const useMapByParent = ({ activeFilter, filterState }) => {
  const [byParent, setByParent] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!activeFilter) {
      setByParent({});
      setLoading(false);
      setError(null);
      return () => {};
    }
    let cancelled = false;
    setLoading(true);
    setError(null);

    const params = {};
    if (filterState?.from_date) {
      params.from_date = filterState.from_date;
    }
    if (filterState?.to_date) {
      params.to_date = filterState.to_date;
    }

    let formula;
    if (activeFilter.formula) {
      formula = activeFilter.formula;
    } else if (activeFilter.question_id) {
      const options = getQuestionOptions(
        activeFilter.form_id,
        activeFilter.question_id
      );
      formula = {
        buckets: options.map((opt) => ({
          value: opt.value,
          label: opt.label,
          all_of: [
            {
              question_id: activeFilter.question_id,
              op: "option_equals",
              value: opt.value,
            },
          ],
        })),
        default: { value: "_no_info", label: "No info" },
      };
    } else {
      setByParent({});
      setLoading(false);
      return () => {};
    }

    const request = api.get("visualization/values/formula", {
      params: {
        form_id: activeFilter.form_id,
        group_by: "parent_id",
        monitoring: "latest",
        formula: JSON.stringify(formula),
        ...params,
      },
    });

    request
      .then((res) => {
        if (cancelled) {
          return;
        }
        const map = {};
        (res?.data?.data || []).forEach((row) => {
          map[row.group] = row.label;
        });
        setByParent(map);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setError(err);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeFilter, filterState]);

  return { byParent, loading, error };
};

export default useMapByParent;
