# Akvo MIS

[![Build Status](https://github.com/akvo/akvo-mis/actions/workflows/main.yml/badge.svg)](https://github.com/akvo/akvo-mis/actions/workflows/main.yml?query=branch%3Amain) [![Build Status](https://github.com/akvo/akvo-mis/actions/workflows/apk-release.yml/badge.svg)](https://github.com/akvo/akvo-mis/actions/workflows/apk-release.yml?query=branch%3Amain) [![Repo Size](https://img.shields.io/github/repo-size/akvo/akvo-mis)](https://img.shields.io/github/repo-size/akvo/akvo-mis) [![Languages](https://img.shields.io/github/languages/count/akvo/akvo-mis)](https://img.shields.io/github/languages/count/akvo/akvo-mis) [![Issues](https://img.shields.io/github/issues/akvo/akvo-mis)](https://img.shields.io/github/issues/akvo/akvo-mis) [![Last Commit](https://img.shields.io/github/last-commit/akvo/akvo-mis/main)](https://img.shields.io/github/last-commit/akvo/akvo-mis/main) [![Coverage Status](https://coveralls.io/repos/github/akvo/akvo-mis/badge.svg)](https://coveralls.io/github/akvo/akvo-mis) [![Coverage Status](https://img.shields.io/readthedocs/akvo-mis?label=read%20the%20docs)](https://akvo-mis.readthedocs.io/en/latest)

Real Time Monitoring Information Systems

## Prerequisite

- Docker > v19
- Docker Compose > v2.1

## Development

### Environment Setup

Ensure that PORT 5432 and 3000 are not being used by other services.

Copy `env.example` to create a `.env` file. Here’s what it should look like:

.env

```bash
APP_NAME="Akvo MIS"
APP_SHORT_NAME="akvo-mis"
APK_NAME="MIS Mobile"
APK_SHORT_NAME="mis-mobile"
DB_HOST=db
DB_PASSWORD=password
DB_SCHEMA=mis
DB_USER=akvo
DEBUG="True"
DJANGO_SECRET=local-secret
GOOGLE_APPLICATION_CREDENTIALS
MAILJET_APIKEY
MAILJET_SECRET
WEBDOMAIN
EXPO_TOKEN="<<your secret expo token>>"
POSTGRES_PASSWORD=password
PGADMIN_DEFAULT_EMAIL=dev@akvo.org
PGADMIN_DEFAULT_PASSWORD=password
PGADMIN_LISTEN_PORT="5050"
IP_ADDRESS="http://<your_ip_address>:3000/api/v1/device"
APK_UPLOAD_SECRET="123456789AU"
STORAGE_PATH="./storage"
SENTRY_DSN="<<your sentry DSN for BACKEND>>"
SENTRY_MOBILE_ENV="<<your sentry env>>"
SENTRY_MOBILE_DSN="<<your_sentry_mobile_DSN>>"
SENTRY_MOBILE_AUTH_TOKEN="<<your_sentry_mobile_auth_token>>"
```


You can generate a Sentry auth token by following [this official Sentry documentation](https://docs.sentry.io/account/auth-tokens/).

#### Start

The frontend's `node_modules` live in a named Docker volume that is declared
`external`, so Docker never creates it automatically. On **every** operating
system (Linux, macOS and Windows) you must create it once before the first run,
otherwise `docker compose up` aborts with an _"external volume not found"_
error:

```bash
docker volume create akvo-mis-docker-sync
```

Then start the stack:

```bash
./dc.sh up -d
```

> **Note:** the separate `docker-sync` tool is **not** required on any OS — the
> stack uses this named volume with native bind mounts. The legacy
> `docker-sync.yml` in the repo is only an optional file-sync accelerator for
> macOS/Windows Docker Desktop and can be ignored.

##### Adjusting volume permissions on Linux

On a standard Docker Engine setup the frontend container runs as `root` and
installs `node_modules` into the volume without trouble. On some Linux
configurations — **rootless Docker**, **user-namespace remapping**, or an
**SELinux-enforcing** host — the container cannot write into the freshly
created (root-owned) volume, and startup fails with a _permission denied_ /
`EACCES` error while installing dependencies.

If that happens, fix the volume's ownership with a throwaway container — no
`sudo`, and no need to touch `/var/lib/docker/volumes` directly:

```bash
# Own the volume as your host user (fixes rootless / userns-remap setups)
docker run --rm -v akvo-mis-docker-sync:/data alpine \
    chown -R "$(id -u):$(id -g)" /data
```

On an **SELinux** host the volume is readable but mislabeled; relabel it for
container access instead (run on the host, where `chcon` is available):

```bash
sudo chcon -Rt svirt_sandbox_file_t \
    "$(docker volume inspect akvo-mis-docker-sync --format '{{.Mountpoint}}')"
```

Then re-run `./dc.sh up -d`.

The development site should be running at: [localhost:3000](http://localhost:3000). Any endpoints with prefix

- `^/api/*` is redirected to [localhost:8000/api](http://localhost:8000/api)
- `^/static-files/*` is for worker service in [localhost:8000](http://localhost:8000/static-files)

Network Config:

- [setupProxy.js](https://github.com/akvo/akvo-mis/blob/main/frontend/src/setupProxy.js)
- [mainnetwork](https://github.com/akvo/akvo-mis/blob/docker-compose.override.yml#L4-L8) container setup

Add New User and Seed Master Data:

Once the containers are up and running, you can seed the necessary data by running the following command:

```bash
./dc.sh exec backend ./seeder.sh
```

The script will prompt you for various actions related to data seeding such as:

- seed administrative data
- add a new super admin
- seed fake users
- seed forms

Answer each prompt by entering 'y' or 'n' followed by the Enter key.

Default Fake User's password: `Test#123`

Generate QR Code for Mobile App Download:

To generate a QR code image for the mobile app download link, run:

```bash
./dc.sh exec backend python manage.py generate_qr_code
```

This generates a QR code PNG image at `storage/images/download-app.png` encoding the default URL (`WEBDOMAIN/app`).

To specify a custom URL:

```bash
./dc.sh exec backend python manage.py generate_qr_code --url https://example.com/app
```

Refresh Materialized Views:

The dashboard map/visualization queries read from the `view_data_options`
materialized view. By default, `generate_config` (run on backend startup, by
the seeder, and lazily by the `/config-file` endpoint when the JS bundle is
missing) **does not** refresh this view because `REFRESH MATERIALIZED VIEW`
acquires an `ACCESS EXCLUSIVE` lock that blocks readers and writers for the
full refresh duration. `CONCURRENTLY` is not used because
`refresh_materialized_data()` runs inside `@transaction.atomic`.

Routine refreshes already happen as part of the data seeders
(`fake_complete_data_seeder`, `flow_data_seeder`) and the
`v1_data.tasks.refresh_materialized_data` async task. To refresh explicitly
during a maintenance window:

```bash
./dc.sh exec backend python manage.py generate_config --refresh-views
```

#### Log

```bash
./dc.sh log --follow <container_name>
```

Available containers:

- backend
- frontend
- mainnetwork
- db
- pgadmin

#### Stop

```bash
./dc.sh stop
```

#### Teardown

```bash
./dc.sh down -t1
docker volume rm akvo-mis-docker-sync
```

## Mobile App Development

For initial run, you need to create a separate docker volume.

```bash
docker volume create akvo-mis-mobile-docker-sync
```

```bash
./dc-mobile.sh up -d
```

1. Install the [**Expo Go**](https://play.google.com/store/apps/details?id=host.exp.exponent&hl=en&gl=US&pli=1) app from Playstore
2. Connect your android to the same wireless network as your machine.
3. Open The Expo Go
4. Enter URL Manually: `Your_IP_Address:19000`

#### Teardown Mobile App

```bash
./dc-mobile.sh down -t1
```

## Production

```bash
export CI_COMMIT='local'
./ci/build.sh
```

Above command will generate two docker images with prefix `eu.gcr.io/akvo-lumen/akvo-mis` for backend and frontend

```bash
docker-compose -f docker-compose.yml -f docker-compose.ci.yml up -d
```

Network config: [nginx](https://github.com/akvo/akvo-mis/blob/main/frontend/nginx/conf.d/default.conf)

### Dedicated Tenant Deployment (UNICEF FSM)

This branch deploys one customer at `https://unicef-fsm.akvotest.org`, while
the multi-tenant SaaS build of `main` runs separately at
`https://mis.akvotest.org`. Three things follow, and the third is the one
that bites.

**Run single-host: leave `BASE_DOMAIN` unset.** With no base domain,
`is_base_domain()` answers true for every host, so `TenantMiddleware`
resolves no tenant, never returns its "workspace not found" 404, and never
enforces the host/session match. The `Host` header stops mattering, and
activation and invite links keep pointing at `WEBDOMAIN` unchanged. No DNS
change is needed to run the multi-tenant code this way.

**Set `ALLOW_REGISTRATION=false`.** It defaults to on, which is right for
the SaaS install and wrong here: a dedicated deployment's one workspace
already exists, so an open `/register` only lets strangers create tenants
and accounts in this customer's database. The deployment runs on GKE via
`ci/deploy.sh` into `unicef-fsm-namespace`, so `deploy/app.env.template`
covers the self-hosted Compose path only and does *not* reach the cluster —
the variable has to be added to the backend Deployment manifest.

> **Confirm the manifest location.** The `akvo-config` checkout used while
> preparing this branch was from 2026-06-29 and contained no `unicef-fsm`
> directory (it did contain `mohhs-mis`). That is either staleness or a
> deployment that does not exist yet. Check against a current checkout
> before assuming where this variable belongs.

**Never set `BASE_DOMAIN` on this deployment.** `unicef-fsm.akvotest.org`
is a *sibling* of `mis.akvotest.org` under `akvotest.org`, not a subdomain
of it. Copying `BASE_DOMAIN=mis.akvotest.org` across from the SaaS config
means the host no longer ends in `.mis.akvotest.org`, so
`resolve_tenant_from_host` returns `None` while `is_base_domain` returns
`False` — and the middleware 404s every request except `health/check` and
`config.js`. The site goes dark while the readiness probe stays green,
which is the worst possible way to fail.


## Dashboard Visualizations

Dashboards at `/dashboard/:formId` are **config-driven** — a new form family
can get a full dashboard without any component code changes. Each dashboard is
a single JSON file whose top-level `items[]` is a flat array of self-describing
widgets (cards, charts, tables, map, filters) dispatched by `chart_type`.
Recursive containers (`tabs`, `filter_bar`) group widgets; layout emerges from
per-item `order` + `col_span`. Cross-references between widgets resolve by
globally-unique `id`.

To add a new dashboard:

1. Drop a `<parent_form_id>.json` file in [frontend/src/config/visualizations/](frontend/src/config/visualizations/)
2. Register it in [frontend/src/config/visualizations/index.js](frontend/src/config/visualizations/index.js)
3. Visit `/dashboard/<parent_form_id>`

References:

- Full schema, `chart_type` catalogue, filter hints, troubleshooting: [frontend/src/config/visualizations/README.md](frontend/src/config/visualizations/README.md)
- Reference implementation (EPS Overview): [1749623934933.json](frontend/src/config/visualizations/1749623934933.json)
- Extended example walkthrough + migration mapping from the legacy nested schema: [doc/claude/iwsims-dashboard-config-example.md](doc/claude/iwsims-dashboard-config-example.md)

## Data Seeder

### Akvo Flow

The Akvo Flow Data Seeder enables you to migrate data from Akvo Flow to Akvo MIS. The process involves downloading forms and data, mapping administration and question data, and seeding the final data via Docker.

**Quick Start Steps:**

1. **Navigate to the scripts directory:**
   ```bash
   cd scripts/akvo-flow
   ```

2. **Configure environment:** Copy [`env.example`](scripts/akvo-flow/env.example) to [`.env`](scripts/akvo-flow/.env) and populate with your Akvo Flow credentials

3. **Configure survey IDs:** Update `flow_ids` in [`af_downloader.ipynb`](scripts/akvo-flow/af_downloader.ipynb) and [`af_forms_mapping.ipynb`](scripts/akvo-flow/af_forms_mapping.ipynb) with your target surveys

4. **Start JupyterLab:**
   ```bash
   jupyterlab .
   ```

5. **Download forms and data:** Run all cells in `af_downloader.ipynb`

6. **Map administration data:** Run all cells in `af_administration_mapping.ipynb`

7. **Map form questions:** Run all cells in `af_forms_mapping.ipynb`

8. **Generate parent and child data files:** Run all cells in `af_data_registration_monitoring.ipynb` to produce the final data files in the output folder

9. **Pre-download photos (optional but recommended):** If your forms contain photo questions, pre-download them before seeding:
    ```bash
    python manage.py predownload_photos --form=<akvo_flow_survey_id>
    ```

   **Optional parameters:**
   - `--workers=<number>` - Number of concurrent download workers (default: 5)

   This creates a success log at `storage/akvo-flow/<form_id>_photo_downloads.csv` and a failed log at `storage/akvo-flow/<form_id>_photo_downloads_failed.csv` for manual review. Re-running skips already downloaded photos.

10. **Seed the data:** Run the Django management command:
    ```bash
    python manage.py flow_data_seeder --form=<akvo_flow_survey_id> --email=<youremail@domain.com>
    ```

   **Optional parameters:**
   - `--limit=<number>` - Limit the number of records to process
   - `--revert=True` - Revert previously seeded data

For comprehensive documentation covering environment setup, detailed command explanations, output expectations, and troubleshooting, see the [Akvo Flow Data Seeder Guide](./scripts/akvo-flow/README.md).