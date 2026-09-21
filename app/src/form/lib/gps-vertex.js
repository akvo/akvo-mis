/**
 * Vertex helpers for GPS boundary walking (GEO-004).
 *
 * Kept pure and out of the screen for the reason GEO-013 D-1 keeps rule logic out of
 * components: none of this needs a GPS, a store or a WebView to be tested, and the parts most
 * likely to be wrong - what counts as "measured", what counts as "poor" - are exactly the
 * parts a device test cannot exercise on demand.
 */

/**
 * ARF's default, pinned for phase 2 by GEO-004 D-3. In this phase the threshold decides which
 * vertices are drawn red and nothing more; the gate that blocks submission arrives in phase 3
 * (GEO-014 D-6), deliberately, so that four hours of field walking under canopy cannot
 * deadlock on a number nobody can yet change.
 */
export const DEFAULT_ACCURACY_THRESHOLD = 15;

/**
 * Recording interval, in seconds, offered in the capture dialog. ODK Collect's list, so an
 * enumerator moving between the two apps finds the same choices in the same order (GEO-004 D-6).
 *
 * The long end is not padding: at 30 min a boundary walk records a handful of corners, which is
 * how a large concession gets mapped on foot without producing the ~180-vertex captures RISK-5
 * warns about.
 */
export const INTERVAL_OPTIONS = [1, 5, 10, 20, 30, 60, 300, 600, 1200, 1800];

/** Ours, not ODK's 20 s. A default carries no transition cost - the control's position does. */
export const DEFAULT_INTERVAL_SECONDS = 10;

/**
 * Accuracy values offered in the capture dialog - ODK's list. `null` is ODK's "None".
 *
 * ODK's control of the same name *filters* fixes; ours *flags* them (GEO-014 D-3), which is why
 * the label beside it must not be copied even though the options are.
 */
export const ACCURACY_OPTIONS = [null, 3, 5, 10, 15, 20];

/**
 * Older than this and a fix is not a lock.
 *
 * It must stay **above** `buildParams.gpsInterval` (60 s), which is how often `Home.js` refreshes
 * the fix this screen falls back to before opening a watch of its own. An earlier 30 s window was
 * half that cadence, so the last shared fix was stale more often than not and the Start button
 * read as permanently dead with nothing on screen explaining why.
 *
 * 90 s is loose for "where am I", and that is fine: this only answers "is there a GPS at all"
 * before recording starts. Once it does, the screen's own watch reports every second.
 */
export const LOCK_MAX_AGE_MS = 90000;

const positiveNumber = (value) => {
  const metres = Number(value);
  return Number.isFinite(metres) && metres > 0 ? metres : null;
};

/**
 * `[lat, lng]` or `[lat, lng, accuracy]`. The third element is optional and its **absence**
 * means "not measured" (GEO-014 D-2).
 *
 * A non-positive or non-finite reading is written as absent rather than as `0`: the backend
 * refuses a literal 0 outright, because ODK spells "not measured" that way and GEO-007's
 * adaptive threshold would read it as *perfect* precision. Some Android devices do report 0,
 * so without this the submission would 400 and revert to a draft on the handset.
 *
 * Returns null when there is no usable position at all, so callers can skip rather than
 * append `[undefined, undefined]`.
 */
export const toVertex = (coords) => {
  const lat = Number(coords?.latitude);
  const lng = Number(coords?.longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return null;
  }
  const metres = positiveNumber(coords?.accuracy);
  return metres === null ? [lat, lng] : [lat, lng, metres];
};

/** Metres, or null when this vertex was tapped rather than measured. */
export const vertexAccuracy = (vertex) =>
  Array.isArray(vertex) ? positiveNumber(vertex[2]) : null;

/**
 * Worse than the threshold.
 *
 * A tapped vertex is never poor. It makes no claim about accuracy, so there is nothing for it
 * to fail - marking it red would tell the enumerator to re-walk a point that was never walked.
 */
export const isPoorVertex = (vertex, threshold = DEFAULT_ACCURACY_THRESHOLD) => {
  // `null` is ODK's "None": no marking at all. Without this branch `metres > null` coerces to
  // `metres > 0` and every measured vertex would turn red - the loosest setting producing the
  // loudest screen.
  const limit = positiveNumber(threshold);
  if (limit === null) {
    return false;
  }
  const metres = vertexAccuracy(vertex);
  return metres !== null && metres > limit;
};

export const poorVertexCount = (points = [], threshold = DEFAULT_ACCURACY_THRESHOLD) =>
  Array.isArray(points) ? points.filter((p) => isPoorVertex(p, threshold)).length : 0;

/**
 * May this boundary be traced on the map rather than walked?
 *
 * Its own key since GEO-014 D-4 (2026-09-21). It was briefly tied to `detectOverlaps`, which made
 * one checkbox do two unrelated jobs - "check this against its neighbours" and "this must be
 * walked" are decisions a programme can reasonably take apart.
 *
 * Default `true`, so every form authored before the key existed behaves exactly as it did, and
 * `allowTapping: false` is the only value anyone ever writes. Anything that is not the literal
 * `false` allows tapping: a truthy `"false"` string reaching here would otherwise disable capture
 * on the strength of a value the backend already refuses.
 */
export const tappingAllowed = (extra) => extra?.geoConfig?.allowTapping !== false;

/**
 * The threshold this question marks against.
 *
 * GEO-004 D-3 chose a hardcoded 15 m because making it editable would have cost an upstream
 * `akvo-react-form-editor` release. That release has since shipped (GEO-009 is delivered as
 * 2.0.5), so the key is already authorable and reading it costs one line - and it gives field
 * testing the knob that D-3's own reaffirmation worried about not having.
 */
export const configuredAccuracyThreshold = (extra) =>
  positiveNumber(extra?.geoConfig?.accuracyThreshold);

export const accuracyThreshold = (extra) => {
  const configured = configuredAccuracyThreshold(extra);
  return configured === null ? DEFAULT_ACCURACY_THRESHOLD : configured;
};

/**
 * Which accuracy values the enumerator may pick, given what the form asked for.
 *
 * The form's value is a **ceiling, not merely a default** (GEO-004 D-7): looser options are not
 * offered and `None` is withdrawn entirely. Tightening what the form asked for is fine;
 * loosening it is not.
 *
 * That costs little in phase 2, where the threshold only colours vertices. It matters in phase 3,
 * where the same number blocks submission (GEO-014 D-9) - an unrestricted dropdown would let the
 * gate be switched off from inside the screen it is supposed to gate.
 *
 * A ceiling that is not itself on ODK's list (a form asking for 7 m) is added to the list rather
 * than rounded away, so the enumerator can always choose exactly what the form asked for.
 */
export const selectableAccuracyOptions = (cap = null) => {
  if (cap === null) {
    return ACCURACY_OPTIONS;
  }
  const allowed = ACCURACY_OPTIONS.filter((option) => option !== null && option <= cap);
  return allowed.includes(cap) ? allowed : [...allowed, cap].sort((a, b) => a - b);
};

/**
 * "20 seconds", "5 mins". Formatted at render rather than stored, so a language switch
 * mid-capture retranslates - the same reason `formatRuleFailure` takes `trans` (GEO-002).
 */
export const formatInterval = (seconds, trans) =>
  seconds < 60
    ? trans?.gpsIntervalSeconds?.replace('{count}', seconds)
    : trans?.gpsIntervalMinutes?.replace('{count}', seconds / 60);

/**
 * Can recording start?
 *
 * A fix must exist and be recent. It must **not** be a good one: requiring accuracy under the
 * threshold to begin would refuse to start under canopy, which is where boundaries are walked,
 * and it would contradict GEO-004 D-1 - poor fixes are recorded and marked, not prevented.
 *
 * A fix with no timestamp is accepted; staleness cannot be judged, and refusing on that basis
 * would be a dead button for a reason the enumerator cannot act on.
 */
export const hasSatelliteLock = (location, now = Date.now()) => {
  const coords = location?.coords;
  if (!coords || toVertex(coords) === null) {
    return false;
  }
  if (positiveNumber(coords.accuracy) === null) {
    return false;
  }
  const timestamp = Number(location?.timestamp);
  return !Number.isFinite(timestamp) || now - timestamp <= LOCK_MAX_AGE_MS;
};
