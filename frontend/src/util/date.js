import moment from "moment";

/**
 * How the API renders datetimes: `REST_FRAMEWORK.DATETIME_FORMAT` is `"%d-%m-%Y %H:%M:%S"`
 * project-wide (backend/mis/settings.py) — day first, and with no timezone offset.
 */
export const API_DATETIME_FORMAT = "DD-MM-YYYY HH:mm:ss";

/**
 * Parse an API datetime and render it in the viewer's locale.
 *
 * **Never hand one of these to `new Date()`.** It does not read day-first, so it falls back to
 * a month-first guess: `"11-09-2026"` silently becomes 9 November instead of 11 September, and
 * `"15-09-2026"` becomes `Invalid Date` as soon as the day passes 12. The visible failure is the
 * lucky half — the quiet one is a wrong date that looks entirely plausible.
 *
 * Both parses are **strict**, and an unrecognised value returns the fallback rather than a
 * guess. ISO is tried second so that dropping `DATETIME_FORMAT` from the backend settings one
 * day improves this function instead of breaking it.
 */
export const formatApiDateTime = (value, fallback = "—") => {
  if (!value) {
    return fallback;
  }
  const asApiFormat = moment(value, API_DATETIME_FORMAT, true);
  if (asApiFormat.isValid()) {
    return asApiFormat.toDate().toLocaleString();
  }
  const asIso = moment(value, moment.ISO_8601, true);
  return asIso.isValid() ? asIso.toDate().toLocaleString() : fallback;
};

export const getDateRange = ({
  startDate,
  endDate,
  type = "months",
  dateFormat = "MMMM DD, YYYY",
}) => {
  const fromDate = moment(startDate);
  const toDate = moment(endDate);
  const diff = toDate.diff(fromDate, type);
  const range = [];
  for (let i = 0; i < diff; i++) {
    range.push(moment(startDate).add(i, type));
  }
  return range.map((r) => r.format(dateFormat));
};

export const timeDiffHours = (last_activity) => {
  const last = moment.unix(last_activity);
  const now = moment.utc();
  const duration = moment.duration(now.diff(last));
  return duration.asHours();
};

export const eraseCookieFromAllPaths = (name) => {
  var pathBits = location.pathname.split("/");
  var pathCurrent = " path=";
  document.cookie = name + "=; expires=Thu, 01-Jan-1970 00:00:01 GMT;";

  for (var i = 0; i < pathBits.length; i++) {
    pathCurrent += (pathCurrent.substr(-1) !== "/" ? "/" : "") + pathBits[i];
    document.cookie =
      name + "=; expires=Thu, 01-Jan-1970 00:00:01 GMT;" + pathCurrent + ";";
  }
};

export const getTimeDifferenceText = (targetDate, format) => {
  const targetDateTime = moment(targetDate, format);
  const currentDateTime = moment();
  const timeDifference = currentDateTime.diff(targetDateTime, "seconds");
  const secondsInADay = 86400; // 24 hours * 60 minutes * 60 seconds

  if (timeDifference < secondsInADay) {
    const hoursAgo = Math.floor(timeDifference / 3600);
    return hoursAgo <= 1 ? "an hour ago" : `${hoursAgo} hours ago`;
  }
  const daysAgo = Math.floor(timeDifference / secondsInADay);
  return daysAgo === 1 ? "a day ago" : `${daysAgo} days ago`;
};
