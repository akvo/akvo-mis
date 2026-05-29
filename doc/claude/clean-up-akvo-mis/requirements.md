# Requirements: Akvo MIS SaaS Platform Cleanup

**Issue**: #226
**Branch**: `feature/226-clean-up-akvo-mis-for-new-development`

## User Acceptance Criteria

- `akvo/akvo-mis` is clearly identified as the SaaS platform repo (not IWSIMS)
- Project-specific data and configurations are removed or generalized
- Pipeline continues to work for SaaS development
- IWSIMS-specific form definitions removed from `backend/source/forms/`
- `APP_SHORT_NAME` and related configs updated to `akvo-mis`
- K8s namespace templates consistent for SaaS
- Sentry project references reviewed (found to be already generic)
- Legacy `COVERALLS_IWSIMS_TOKEN` reference removed from pipeline

---

## Functional Requirements

### FR-1: Remove IWSIMS Form Definitions

**Files deleted** — 15 numbered production/monitoring form JSON files from `backend/source/forms/`:

```
1_1749634736797.prod.json
1_1749640508297.monitoring.prod.json
1_1749652214711.monitoring.prod.json
2_1749623934933.prod.json
2_1749624452908.monitoring.prod.json
2_1749632545233.monitoring.prod.json
3_1749621221728.prod.json
3_1749621962296.monitoring.prod.json
3_1749631041125.monitoring.prod.json
4_1749611049520.prod.json
4_1749611905372.monitoring.prod.json
4_1749627302948.monitoring.prod.json
5_1748903240763.prod.json
5_1748905550055.monitoring.prod.json
5_1748918946591.monitoring.prod.json
```

**Files kept** — 13 generic example and test forms:

```
example-1.json
example-1.1.monitoring.json
example-1.2.monitoring.json
example-2.json
example-3.json
example-4.json
example-4.test.json
example-5.json
example-vis-6.json
example-vis-6.monitoring.json
short-test-form.test.json
short-test-form.monitoring.test.json
short-test-form.monitoring-2.test.json
```

**Acceptance**: No files matching `[0-9]_*.json` remain in `backend/source/forms/`.

---

### FR-2: Update Platform Identity to `akvo-mis`

| File | Key | Old Value | New Value |
|---|---|---|---|
| `env.example` | `APP_NAME` | `"IWSIMS"` | `"Akvo MIS"` |
| `env.example` | `APP_SHORT_NAME` | `iwsims` | `akvo-mis` |
| `env.example` | `APK_NAME` | `"DWS DataPro"` | `"Akvo MIS"` |
| `env.example` | `APK_SHORT_NAME` | `"dws-datapro"` | `"akvo-mis"` |
| `frontend/package.json` | `name` | `"iwsims"` | `"akvo-mis"` |
| `frontend/public/manifest.json` | `name` | `"IWSIMS"` | `"Akvo MIS"` |
| `frontend/public/manifest.json` | `short_name` | `"iwsims"` | `"akvo-mis"` |

**Acceptance**: `grep -r "IWSIMS\|iwsims" env.example frontend/package.json frontend/public/manifest.json` returns no matches.

---

### FR-3: Generalize Mobile Build Configs

**Files affected**:
- `app/src/build.prod.js`
- `app/src/build.staging.js`
- `app/src/build.testing.js`

**Current state** (all three files contain hardcoded domains):
```js
serverURL: 'https://iwsims.akvo.org/api/v1/device',
apkURL: 'https://iwsims.akvo.org/app',
```

**Target state**:

`build.prod.js` and `build.staging.js` — empty placeholder, no confirmed SaaS domain:
```js
serverURL: '', // Configure: https://<your-domain>/api/v1/device
apkURL: '',    // Configure: https://<your-domain>/app
```

`build.testing.js` — local dev default via nginx proxy (port 3000, not 8000):
```js
serverURL: 'http://localhost:3000/api/v1/device', // Mobile device: replace localhost with IP_ADDRESS from .env
apkURL: '',
```

Note: The mobile app always connects via nginx on port 3000 (which proxies `/api/` to the Django backend). Physical mobile devices must replace `localhost` with the machine's LAN IP from `IP_ADDRESS` in `.env`.

**Acceptance**: No occurrence of `iwsims.akvo.org` or `iwsims.akvotest.org` in `app/src/`.

---

### FR-4: Fix K8s Deployment Template — Hardcoded `iwsims`

**File**: `ci/k8s/deployment.template.yml`

Three occurrences of `subPath: iwsims-service-account.json` — replace with `subPath: ${APP_SHORT_NAME}-service-account.json`.

This makes `deployment.template.yml` consistent with `cronjobs.template.yml` which already uses the template variable.

**Acceptance**: `grep "iwsims" ci/k8s/deployment.template.yml` returns no matches.

---

### FR-5: Fix K8s Wait Script — Hardcoded Pod Labels

**File**: `ci/k8s/wait-for-k8s-deployment-to-be-ready.sh`

**Current state**:
```bash
# Pod label selectors use hardcoded "iwsims"
"iwsims-version=$CI_COMMIT,run=iwsims"
"iwsims-version!=$CI_COMMIT,run=iwsims"
```

**Target state**:
```bash
"${APP_SHORT_NAME}-version=$CI_COMMIT,run=${APP_SHORT_NAME}"
"${APP_SHORT_NAME}-version!=$CI_COMMIT,run=${APP_SHORT_NAME}"
```

`APP_SHORT_NAME` must be sourced from the environment (already set in the CI pipeline via `${{ secrets.APP_SHORT_NAME }}`).

**Acceptance**: `grep "iwsims" ci/k8s/wait-for-k8s-deployment-to-be-ready.sh` returns no matches.

---

### FR-6: Fix Docker Compose Credential Paths

**Files affected**:
- `docker-compose.override.yml` — 2 occurrences of `/credentials/iwsims-service-account.json`
- `docker-compose.test.yml` — 1 occurrence of `/credentials/iwsims-service-account.json`

**Target state**: Replace with `/credentials/${APP_SHORT_NAME:-akvo-mis}-service-account.json`

The `${APP_SHORT_NAME:-akvo-mis}` default ensures local dev still works if `.env` is not yet configured.

**Acceptance**: `grep "iwsims-service-account" docker-compose.override.yml docker-compose.test.yml` returns no matches.

---

### FR-7: Clean Up Pipeline — Remove `COVERALLS_IWSIMS_TOKEN`

**File**: `.github/workflows/main.yml`

**Current state**: Two Coveralls tokens exist — one for build, one for deploy:
```yaml
# Build job (line ~70)
COVERALLS_REPO_TOKEN: ${{ secrets.COVERALLS_AKVO_MIS_TOKEN }}

# Deploy job (line ~87)
COVERALLS_REPO_TOKEN: ${{ secrets.COVERALLS_IWSIMS_TOKEN }}
```

**Target state**: Remove the deploy-job Coveralls reference. Coveralls reporting runs once during the build/test stage only.

**Acceptance**: `grep "COVERALLS_IWSIMS_TOKEN" .github/workflows/main.yml` returns no matches.

---

### FR-8: Fix Dev Proxy APK Path

**File**: `frontend/src/setupProxy.js`

The dev proxy (CRA, port 3000) rewrites `/app` to the APK filename:

```js
// Before
pathRewrite: { "^/app": "/apk/dws-datapro.apk" }

// After
pathRewrite: { "^/app": "/apk/akvo-mis.apk" }
```

Must match the nginx config and `APK_SHORT_NAME`.

**Acceptance**: `grep "dws-datapro" frontend/src/setupProxy.js` returns no matches.

---

### FR-9: Fix Nginx APK Filename

**File**: `frontend/nginx/conf.d/default.conf`

**Current state**: The `/app` location block hardcodes the IWSIMS APK name:
```nginx
try_files /storage/apk/dws-datapro.apk =404;
add_header Content-Disposition 'attachment; filename="dws-datapro.apk"';
```

**Target state**: Update to match `APK_SHORT_NAME=akvo-mis`:
```nginx
try_files /storage/apk/akvo-mis.apk =404;
add_header Content-Disposition 'attachment; filename="akvo-mis.apk"';
```

Nginx does not support env vars natively — the value is baked in. Deployers using a custom APK name must update this file to match their `APK_SHORT_NAME`.

**Acceptance**: `grep "dws-datapro" frontend/nginx/conf.d/default.conf` returns no matches.

---

### FR-10: Mobile App Identity (`app/app.json`, `app/package.json`, `app/src/build.json`)

**Implemented.**

| File → Field | Old | New |
|---|---|---|
| `app/package.json` → `name` | `dws-datapro-mobile` | `akvo-mis-mobile` |
| `app/app.json` → `expo.name` | `DWS DataPro` | `Akvo MIS` |
| `app/app.json` → `expo.slug` | `dws-datapro-mobile` | `akvo-mis-mobile` |
| `app/app.json` → `android.package` | `com.akvo.dws_datapro` | `com.akvo.akvo_mis` |
| `app/app.json` → Sentry `project` | `dws-datapro-mobile` | `akvo-mis-mobile` |
| `app/src/build.json` → `apkName` | `DWS DataPro` | `Akvo MIS` |

**Note on Android package rename**: This repo is a clean SaaS base for new deployments. The Android package ID change means existing app installations require uninstall/reinstall — acceptable since IWSIMS production users are on a separate deployment.

**Acceptance**: `grep -r "dws-datapro\|dws_datapro\|DWS DataPro" app/` returns no matches.

---

### FR-11: Generalize CI Deploy Script

**File**: `ci/deploy.sh`

The GCloud auth step hardcoded the credentials path:
```bash
# Before
gcloud auth activate-service-account --key-file=/home/runner/work/iwsims/credentials/gcp.json

# After
gcloud auth activate-service-account --key-file=/home/runner/work/${APP_SHORT_NAME}/credentials/gcp.json
```

`APP_SHORT_NAME` is already set in the CI environment via `${{ secrets.APP_SHORT_NAME }}`.

**Acceptance**: `grep "iwsims" ci/deploy.sh` returns no matches.

---

### FR-12: Generalize Stress Test Scripts

**Files affected**:
- `doc/script/stress_tests/push_submissions.sh`
- `doc/script/stress_tests/jmeter_stress_test.sh`
- `doc/script/stress_tests/household_submission.json`

All three hardcoded `https://iwsims.akvotest.org` — replaced with `https://your-domain.org` placeholder.

**Acceptance**: `grep -r "iwsims" doc/script/stress_tests/` returns no matches.

---

### FR-13: Sentry — No Changes Required

Sentry is already fully driven by environment variables (`SENTRY_DSN`, `SENTRY_MOBILE_DSN`, etc.) across all integration points:
- `backend/mis/settings.py`
- `ci/k8s/deployment.template.yml` (references `sentry-dsn` K8s secret key — generic)
- `deploy/app.env.template` (placeholder values)

No hardcoded IWSIMS Sentry project names found. **This requirement is satisfied by the current state.**

---

## Non-Functional Requirements

### NFR-1: Pipeline Continuity
The GitHub Actions build and deploy pipeline must continue to function after all changes. No broken secret references, no missing substitution variables, no failed deployments.

### NFR-2: No Silent Breakage in Local Dev
Changes to `docker-compose.override.yml` and `env.example` must not break existing local developer setups. Use shell variable defaults (`${VAR:-fallback}`) where needed.

### NFR-3: Consistent Template Variable Usage
All K8s templates must use `${APP_SHORT_NAME}` uniformly — no file should still hardcode `iwsims` after this cleanup.

### NFR-4: Minimal Diff
Changes are configuration and data only. No logic changes, no refactoring, no new features.

---

## Out of Scope

- GCP project or GKE cluster infrastructure changes
- K8s namespace renaming (handled at deploy time via `APP_SHORT_NAME`)
- Sentry project configuration changes
- Any application logic modifications
- Documentation updates beyond this `doc/claude/` directory
