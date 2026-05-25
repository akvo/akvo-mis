# Design: Akvo MIS SaaS Platform Cleanup

**Issue**: #226

## Design Philosophy

This is a **subtraction task**, not a construction task. The goal is to remove and neutralize project-specific content without introducing new abstractions or changing application behavior. Every decision should minimize code churn while maximizing generality.

---

## Decision Log

### D-1: Form File Strategy — Delete, Not Archive

**Options considered**:
1. Delete numbered forms permanently
2. Move to a separate IWSIMS branch/archive
3. Keep in a `legacy/` subdirectory

**Decision**: Delete permanently (option 1).

**Rationale**:
- Git history already preserves the files — `git log -- backend/source/forms/1_*.json` will always work
- An archive branch or `legacy/` directory still pollutes the repo with project-specific data
- New tenants cloning the repo should not encounter another organization's survey forms
- The example forms (`example-*.json`) provide sufficient demo content for onboarding

---

### D-2: SaaS Identity — `akvo-mis` Not a New Brand Name

**Options considered**:
1. Use `akvo-mis` (matches repo name)
2. Define a new SaaS product name
3. Use pure placeholders with no defaults

**Decision**: `APP_SHORT_NAME=akvo-mis`, `APP_NAME="Akvo MIS"` (option 1).

**Rationale**:
- The repo is already named `akvo-mis` — consistency across naming layers reduces confusion
- Pure placeholders (`<your-app-name>`) would break CI and local dev that don't set the env var before testing
- A new brand name requires a separate brand/product decision outside this scope

---

### D-3: Mobile Build URLs — Placeholder Pattern Over New Domain

**Options considered**:
1. Replace with empty string + comment
2. Replace with a new SaaS domain (e.g., `mis.akvo.org`)
3. Use `process.env.SERVER_URL` runtime variable

**Decision**: Empty string with explanatory comment (option 1).

**Rationale**:
- There is no confirmed SaaS domain yet — hardcoding one would recreate the same problem
- `process.env.SERVER_URL` would require changes to the Expo build pipeline — out of scope
- An empty string with a comment makes the configuration requirement explicit to any new deployer
- The mobile build files (`build.prod.js`, `build.staging.js`) are already understood to be deployment-specific configuration

**Pattern** (prod/staging — no confirmed SaaS domain yet):
```js
serverURL: '', // Configure: https://<your-domain>/api/v1/device
apkURL: '',    // Configure: https://<your-domain>/app
```

**Pattern** (testing — `build.testing.js` for local dev):
```js
serverURL: 'http://localhost:3000/api/v1/device', // Mobile device: replace localhost with IP_ADDRESS from .env
apkURL: '',
```

`serverURL` uses port **3000**, not 8000. Nginx (running on port 3000) proxies `/api/` to the Django backend — the mobile app never talks to the backend directly. Physical mobile devices on the same WiFi cannot resolve `localhost` — developers replace it with the machine's LAN IP from `IP_ADDRESS` in `.env`.

---

### D-4: K8s Template Consistency — `${APP_SHORT_NAME}` Variable

**Finding**: `cronjobs.template.yml` already uses `${APP_SHORT_NAME}-service-account.json` correctly. `deployment.template.yml` does not — it hardcodes `iwsims-service-account.json`.

**Decision**: Align `deployment.template.yml` with the pattern already established in `cronjobs.template.yml`.

**Rationale**:
- The `${APP_SHORT_NAME}` variable is already resolved at deploy time by `ci/deploy.sh` using `envsubst`
- No new mechanism needed — just apply the existing pattern consistently
- The wait script (`wait-for-k8s-deployment-to-be-ready.sh`) needs the same treatment since it references pod labels that are set using `APP_SHORT_NAME` in the deployment

---

### D-5: Docker Compose Credential Path — Shell Default Syntax

**Decision**: Use `${APP_SHORT_NAME:-akvo-mis}-service-account.json` in compose files.

**Rationale**:
- Developers who haven't set `APP_SHORT_NAME` in their `.env` still get a working path
- The default `akvo-mis` aligns with the new `env.example` default
- This is standard shell variable substitution supported by Docker Compose

---

### D-6: Coveralls Token — Single Token, Build Stage Only

**Finding**: Two tokens exist — `COVERALLS_AKVO_MIS_TOKEN` (build stage) and `COVERALLS_IWSIMS_TOKEN` (deploy stage). Coverage is already reported in the build stage; the deploy-stage reference is redundant.

**Decision**: Remove the `COVERALLS_IWSIMS_TOKEN` reference from the deploy job.

**Rationale**:
- Coverage reporting belongs in the test/build stage, not in the deploy stage
- Removing the reference also removes the need to maintain a separate GitHub secret
- The `COVERALLS_IWSIMS_TOKEN` GitHub Actions secret can be deleted from the repository settings after this change (out of scope for this PR — infrastructure task)

---

## File Change Map

```
backend/source/forms/
  DELETE: 1_*.json, 2_*.json, 3_*.json, 4_*.json, 5_*.json   (22 files)
  KEEP:   example-*.json, short-test-form-*.json              (13 files)

env.example
  EDIT: APP_NAME, APP_SHORT_NAME, APK_NAME, APK_SHORT_NAME

frontend/package.json
  EDIT: "name" field

frontend/public/manifest.json
  EDIT: "name", "short_name" fields

app/src/build.prod.js
app/src/build.staging.js
app/src/build.testing.js
  EDIT: serverURL, apkURL values → empty string + comment

ci/k8s/deployment.template.yml
  EDIT: 3x iwsims-service-account.json → ${APP_SHORT_NAME}-service-account.json

ci/k8s/wait-for-k8s-deployment-to-be-ready.sh
  EDIT: hardcoded run=iwsims labels → ${APP_SHORT_NAME}

docker-compose.override.yml
  EDIT: 2x iwsims-service-account.json → ${APP_SHORT_NAME:-akvo-mis}-service-account.json

docker-compose.test.yml
  EDIT: 1x iwsims-service-account.json → ${APP_SHORT_NAME:-akvo-mis}-service-account.json

.github/workflows/main.yml
  EDIT: Remove COVERALLS_IWSIMS_TOKEN reference from deploy job
```

**Total**: 22 files deleted, 11 files edited.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Wait script breaks if `APP_SHORT_NAME` not exported | Low | High | Script already runs in CI where `APP_SHORT_NAME` is set via secret |
| Docker Compose local dev breaks without `.env` set | Medium | Low | Shell default `:-akvo-mis` prevents empty path |
| Coveralls reporting stops working | Low | Low | Token stays in build stage; only deploy-stage reference removed |
| Form seeder breaks (no prod forms) | None | None | Seeder uses example forms; numbered forms were not seeded by `seeder.sh` |
| Mobile app fails to build | None | None | Empty URL is caught at runtime, not build time; existing behavior for unconfigured deployments |

---

### D-7: Nginx APK Location — Hardcoded `dws-datapro.apk`

**File**: `frontend/nginx/conf.d/default.conf`

**Finding**: The `/app` location block hardcodes the APK filename:
```nginx
try_files /storage/apk/dws-datapro.apk =404;
add_header Content-Disposition 'attachment; filename="dws-datapro.apk"';
```

`dws-datapro` is the IWSIMS/DWS project APK name, matching the old `APK_SHORT_NAME="dws-datapro"`.

**Decision**: Replace with `akvo-mis.apk`, consistent with the new `APK_SHORT_NAME=akvo-mis`.

**Note**: Nginx configs do not natively support environment variables. The filename is baked into the static config. Each deployment must update this file if they use a different APK name.

---

### D-8: Mobile App Identity — Full Rename

**Files**: `app/app.json`, `app/package.json`

**Decision**: Rename all DWS/project-specific identifiers to `akvo-mis`:

| Field | Old | New |
|---|---|---|
| `package.json` → `name` | `dws-datapro-mobile` | `akvo-mis-mobile` |
| `app.json` → `expo.name` | `DWS DataPro` | `Akvo MIS` |
| `app.json` → `expo.slug` | `dws-datapro-mobile` | `akvo-mis-mobile` |
| `app.json` → `android.package` | `com.akvo.dws_datapro` | `com.akvo.akvo_mis` |
| `app.json` → Sentry `project` | `dws-datapro-mobile` | `akvo-mis-mobile` |

**Rationale for Android package rename**: This repo is a clean SaaS base for new deployments — not an upgrade path for existing IWSIMS production users. The IWSIMS production APK is a separate concern. A new Expo project and Sentry project will be created for the SaaS platform, making the old slugs irrelevant.

**Rationale for dev proxy APK path** (`frontend/src/setupProxy.js`): Updated to `akvo-mis.apk` to match nginx config and `APK_SHORT_NAME`.

---

## What This Does Not Change

- Application logic (zero behavior changes)
- Database schema or migrations
- API endpoints or response formats
- Test suite structure or coverage targets
- Sentry integration (already generic)
- Any Docker image build process
- The `deploy/app.env.template` (already uses generic placeholder comments)
