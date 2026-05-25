# Implementation Plan: Akvo MIS SaaS Platform Cleanup

**Issue**: #226
**Branch**: `feature/226-clean-up-akvo-mis-for-new-development`
**Estimated effort**: ~1 hour (all config/data, no logic changes)

---

## Prerequisites

- [ ] Branch `feature/226-clean-up-akvo-mis-for-new-development` checked out
- [ ] No uncommitted local changes that conflict with the target files
- [ ] After merge: delete `COVERALLS_IWSIMS_TOKEN` GitHub Actions secret from repo settings (infrastructure task, not in this PR)

---

## Task Breakdown

Tasks are ordered to group related files. All tasks in a group can be done in a single commit if preferred.

---

### Group A: Delete IWSIMS Form Definitions

**Requirement**: FR-1

```bash
cd backend/source/forms/

# Delete all 15 IWSIMS-specific numbered forms
rm \
  1_1749634736797.prod.json \
  1_1749640508297.monitoring.prod.json \
  1_1749652214711.monitoring.prod.json \
  2_1749623934933.prod.json \
  2_1749624452908.monitoring.prod.json \
  2_1749632545233.monitoring.prod.json \
  3_1749621221728.prod.json \
  3_1749621962296.monitoring.prod.json \
  3_1749631041125.monitoring.prod.json \
  4_1749611049520.prod.json \
  4_1749611905372.monitoring.prod.json \
  4_1749627302948.monitoring.prod.json \
  5_1748903240763.prod.json \
  5_1748905550055.monitoring.prod.json \
  5_1748918946591.monitoring.prod.json
```

**Verify**:
```bash
ls backend/source/forms/ | grep -E "^[0-9]_"
# Expected: no output
```

**Files remaining after deletion**:
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

---

### Group B: Platform Identity — `env.example` and Frontend

**Requirement**: FR-2

#### B-1: `env.example`

```
APP_NAME="IWSIMS"        →  APP_NAME="Akvo MIS"
APP_SHORT_NAME=iwsims    →  APP_SHORT_NAME=akvo-mis
APK_NAME="DWS DataPro"  →  APK_NAME="Akvo MIS"
APK_SHORT_NAME="dws-datapro"  →  APK_SHORT_NAME="akvo-mis"
```

#### B-2: `frontend/package.json`

```json
"name": "iwsims"  →  "name": "akvo-mis"
```

#### B-3: `frontend/public/manifest.json`

```json
"name": "IWSIMS"      →  "name": "Akvo MIS"
"short_name": "iwsims"  →  "short_name": "akvo-mis"
```

**Verify**:
```bash
grep -n "IWSIMS\|iwsims\|DWS DataPro\|dws-datapro" \
  env.example frontend/package.json frontend/public/manifest.json
# Expected: no output
```

---

### Group C: Mobile Build Config URLs

**Requirement**: FR-3

**Files**: `app/src/build.prod.js`, `app/src/build.staging.js`, `app/src/build.testing.js`

For each file, replace the `serverURL` and `apkURL` values:

**`build.prod.js`** and **`build.staging.js`** (both reference `iwsims.akvo.org`):
```js
// Before
serverURL: 'https://iwsims.akvo.org/api/v1/device',
apkURL: 'https://iwsims.akvo.org/app',

// After
serverURL: '', // Configure: https://<your-domain>/api/v1/device
apkURL: '',    // Configure: https://<your-domain>/app
```

**`build.testing.js`** (references `iwsims.akvotest.org` — used for local dev):
```js
// Before
serverURL: 'https://iwsims.akvotest.org/api/v1/device',
apkURL: 'https://iwsims.akvotest.org/app',

// After
serverURL: 'http://localhost:3000/api/v1/device', // Mobile device: replace localhost with IP_ADDRESS from .env
apkURL: '',
```

Note: `serverURL` uses port **3000** — the mobile app always connects via nginx, which proxies `/api/` to the Django backend on port 8000. Physical devices on the same WiFi cannot resolve `localhost` — replace with the machine's LAN IP from `IP_ADDRESS` in `.env`.

**Verify**:
```bash
grep -r "iwsims\.akvo" app/src/
# Expected: no output
```

---

### Group D: K8s Deployment Template

**Requirement**: FR-4

**File**: `ci/k8s/deployment.template.yml`

Find all 3 occurrences of `subPath: iwsims-service-account.json` and replace:
```yaml
# Before
subPath: iwsims-service-account.json

# After
subPath: ${APP_SHORT_NAME}-service-account.json
```

Note: There are 3 occurrences — one for each container that mounts the service account (frontend/backend, worker, and possibly the Cloud SQL proxy). Replace all of them.

**Verify**:
```bash
grep "iwsims" ci/k8s/deployment.template.yml
# Expected: no output

grep "APP_SHORT_NAME.*service-account" ci/k8s/deployment.template.yml
# Expected: 3 matches
```

---

### Group E: K8s Wait Script

**Requirement**: FR-5

**File**: `ci/k8s/wait-for-k8s-deployment-to-be-ready.sh`

Locate the pod label selector strings and replace:

```bash
# Before (exact strings may vary — check line content)
"iwsims-version=$CI_COMMIT,run=iwsims"
"iwsims-version!=$CI_COMMIT,run=iwsims"

# After
"${APP_SHORT_NAME}-version=$CI_COMMIT,run=${APP_SHORT_NAME}"
"${APP_SHORT_NAME}-version!=$CI_COMMIT,run=${APP_SHORT_NAME}"
```

Also check if `APP_SHORT_NAME` needs to be exported at the top of the script or if it's already available in the calling environment. The CI pipeline sets it via `${{ secrets.APP_SHORT_NAME }}` — no script-level change needed.

**Verify**:
```bash
grep "iwsims" ci/k8s/wait-for-k8s-deployment-to-be-ready.sh
# Expected: no output
```

---

### Group F: Docker Compose Credential Paths

**Requirement**: FR-6

**File**: `docker-compose.override.yml` (2 occurrences)

```yaml
# Before
GOOGLE_APPLICATION_CREDENTIALS=/credentials/iwsims-service-account.json

# After
GOOGLE_APPLICATION_CREDENTIALS=/credentials/${APP_SHORT_NAME:-akvo-mis}-service-account.json
```

**File**: `docker-compose.test.yml` (1 occurrence)

```yaml
# Before
GOOGLE_APPLICATION_CREDENTIALS=/credentials/iwsims-service-account.json

# After
GOOGLE_APPLICATION_CREDENTIALS=/credentials/${APP_SHORT_NAME:-akvo-mis}-service-account.json
```

**Verify**:
```bash
grep "iwsims-service-account" docker-compose.override.yml docker-compose.test.yml
# Expected: no output
```

---

### Group G: CI Pipeline — Remove `COVERALLS_IWSIMS_TOKEN`

**Requirement**: FR-7

**File**: `.github/workflows/main.yml`

Locate the deploy job section (around line 87) that sets `COVERALLS_REPO_TOKEN` using `COVERALLS_IWSIMS_TOKEN` and remove that environment variable entry.

```yaml
# Before (deploy job env section)
env:
  COVERALLS_REPO_TOKEN: ${{ secrets.COVERALLS_IWSIMS_TOKEN }}
  # ... other vars

# After
# Remove the COVERALLS_REPO_TOKEN line entirely from the deploy job
```

The build job reference to `COVERALLS_AKVO_MIS_TOKEN` must be left untouched.

**Verify**:
```bash
grep "COVERALLS_IWSIMS_TOKEN" .github/workflows/main.yml
# Expected: no output

grep "COVERALLS_AKVO_MIS_TOKEN" .github/workflows/main.yml
# Expected: 1 match (build job only)
```

---

### Group H: Nginx APK Filename

**File**: `frontend/nginx/conf.d/default.conf`

The `/app` location block hardcodes the old IWSIMS APK name `dws-datapro.apk`:

```nginx
# Before
location /app {
    try_files               /storage/apk/dws-datapro.apk =404;
    add_header              Content-Disposition 'attachment; filename="dws-datapro.apk"';
}

# After
location /app {
    try_files               /storage/apk/akvo-mis.apk =404;
    add_header              Content-Disposition 'attachment; filename="akvo-mis.apk"';
}
```

Note: Nginx does not support env vars natively — the APK name is baked in. This must match `APK_SHORT_NAME=akvo-mis`.

**Verify**:
```bash
grep "dws-datapro" frontend/nginx/conf.d/default.conf
# Expected: no output
```

---

### Group I: CI Deploy Script — Credentials Path

**Requirement**: FR-11

**File**: `ci/deploy.sh`

```bash
# Before
gcloud auth activate-service-account --key-file=/home/runner/work/iwsims/credentials/gcp.json

# After
gcloud auth activate-service-account --key-file=/home/runner/work/${APP_SHORT_NAME}/credentials/gcp.json
```

**Verify**:
```bash
grep "iwsims" ci/deploy.sh
# Expected: no output
```

---

### Group J: Mobile App Identity

**Requirement**: FR-10

**Files**: `app/app.json`, `app/package.json`, `app/src/build.json`

| File → Field | Before | After |
|---|---|---|
| `app/package.json` → `name` | `dws-datapro-mobile` | `akvo-mis-mobile` |
| `app/app.json` → `expo.name` | `DWS DataPro` | `Akvo MIS` |
| `app/app.json` → `expo.slug` | `dws-datapro-mobile` | `akvo-mis-mobile` |
| `app/app.json` → `android.package` | `com.akvo.dws_datapro` | `com.akvo.akvo_mis` |
| `app/app.json` → Sentry `project` | `dws-datapro-mobile` | `akvo-mis-mobile` |
| `app/src/build.json` → `apkName` | `DWS DataPro` | `Akvo MIS` |

**Verify**:
```bash
grep -r "dws-datapro\|dws_datapro\|DWS DataPro" app/
# Expected: no output
```

---

### Group K: Stress Test Scripts

**Requirement**: FR-12

**Files**:
- `doc/script/stress_tests/push_submissions.sh` — 2 URL occurrences
- `doc/script/stress_tests/jmeter_stress_test.sh` — 1 URL occurrence
- `doc/script/stress_tests/household_submission.json` — 3 image URL occurrences

```bash
# Before
https://iwsims.akvotest.org/...

# After
https://your-domain.org/...
```

**Verify**:
```bash
grep -r "iwsims" doc/script/stress_tests/
# Expected: no output
```

---

## Final Verification Checklist

Run all verification commands as a batch after completing all groups:

```bash
# FR-1: No numbered forms remain
ls backend/source/forms/ | grep -E "^[0-9]_"

# FR-2: No IWSIMS branding in identity files
grep -rn "IWSIMS\|iwsims\|DWS DataPro\|dws-datapro" \
  env.example frontend/package.json frontend/public/manifest.json

# FR-3: No hardcoded mobile domain URLs
grep -r "iwsims\.akvo" app/src/

# FR-4: No hardcoded iwsims in K8s deployment
grep "iwsims" ci/k8s/deployment.template.yml

# FR-5: No hardcoded iwsims in wait script
grep "iwsims" ci/k8s/wait-for-k8s-deployment-to-be-ready.sh

# FR-6: No hardcoded credential paths
grep "iwsims-service-account" docker-compose.override.yml docker-compose.test.yml

# FR-7: No legacy Coveralls token
grep "COVERALLS_IWSIMS_TOKEN" .github/workflows/main.yml

# FR-8: Dev proxy APK path updated
grep "dws-datapro" frontend/src/setupProxy.js

# FR-9: Nginx APK filename updated
grep "dws-datapro" frontend/nginx/conf.d/default.conf

# FR-10: Mobile app identity updated
grep -r "dws-datapro\|dws_datapro\|DWS DataPro" app/

# FR-11: CI deploy script updated
grep "iwsims" ci/deploy.sh

# FR-12: Stress test scripts updated
grep -r "iwsims" doc/script/stress_tests/

# Broad sweep — catch anything missed (excludes historical debug logs)
grep -rn "iwsims\|dws-datapro\|dws_datapro\|DWS DataPro" \
  --include="*.json" \
  --include="*.yml" \
  --include="*.yaml" \
  --include="*.js" \
  --include="*.sh" \
  --include="*.env*" \
  --include="*.conf" \
  . \
  --exclude-dir=node_modules \
  --exclude-dir=.git \
  --exclude-dir=unused \
  --exclude-dir=mobile-sqlite-issues
```

All commands should return no output.

---

## Commit Strategy

**Single commit** — this is one logical cleanup with no partial states to preserve:

```bash
git commit -m "[#226] Remove IWSIMS-specific configs and prepare repo as Open Core SaaS platform

- Delete 15 IWSIMS-specific form definitions from backend/source/forms/
- Update APP_SHORT_NAME, APP_NAME, APK_NAME in env.example to akvo-mis / Akvo MIS
- Update frontend/package.json and frontend/public/manifest.json from IWSIMS to Akvo MIS
- Replace hardcoded iwsims.akvo.org URLs in mobile build configs with placeholders
- Set build.testing.js serverURL to localhost:3000 (via nginx proxy) for local dev
- Fix ci/k8s/deployment.template.yml: use \${APP_SHORT_NAME} for service account subPath (3 places)
- Fix ci/k8s/wait-for-k8s-deployment-to-be-ready.sh: replace hardcoded iwsims pod labels
- Fix ci/deploy.sh: use \${APP_SHORT_NAME} in credentials path
- Fix docker-compose.override.yml and docker-compose.test.yml: use \${APP_SHORT_NAME:-akvo-mis} for credential path
- Remove COVERALLS_IWSIMS_TOKEN from deploy stage in GitHub Actions pipeline
- Update nginx APK filename and dev proxy path from dws-datapro to akvo-mis
- Rename mobile app identity: slug, Android package, Sentry project, apkName → akvo-mis
- Replace hardcoded iwsims URLs in doc/script/stress_tests/ with placeholder domain"
```

---

## Post-Merge Infrastructure Tasks (Out of Scope for PR)

- [ ] Delete `COVERALLS_IWSIMS_TOKEN` GitHub Actions secret from repository settings
- [ ] Update the K8s secret in the SaaS cluster to use `akvo-mis` as the secret name (if deploying fresh)
- [ ] Rename the GCS service account JSON file from `iwsims-service-account.json` to `akvo-mis-service-account.json` in the credentials store
