#!/usr/bin/env bash
#
# Move a single-host MIS install into one workspace of the multi-tenant
# instance.  Design: doc/design/MT-014-single-host-to-workspace-migration.md
#
#   ./migration/migrate-tenant.sh \
#       --tenant mohhs \
#       --dump   storage/mohhs/db/mohhs.sql \
#       --files  storage/mohhs/storage \
#       --env    local \
#       --reset --dry-run
#
# Host requirements: docker, and for --env test|prod also kubectl.  No
# Postgres client is needed -- psql runs from a pinned container, because
# neither this machine nor the backend image has one.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PSQL_IMAGE="postgres:14-alpine"
NAMESPACE="akvo-mis-namespace"
CTX_TEST="gke_akvo-lumen_europe-west1-d_test"
CTX_PROD="gke_akvo-lumen_europe-west1-d_production"

# The tables that make up a workspace, in the order import.sql inserts
# them.  A table absent here is never extracted from the dump and so can
# never be loaded -- which is how jobs, mobile_apks and the django_*
# operational tables are excluded (MT-014 D-2, D4, D5).
TABLES="levels organisation administrator system_user form question_group \
question option form_published_version user_form data answer \
mobile_assignments mobile_assignments_forms mobile_assignments_administrations"

TENANT="" DUMP="" FILES="" ENVIRONMENT="local"
DO_RESET="off" DRY_RUN="off" SKIP_FILES="no"

die()  { printf '\nerror: %s\n' "$*" >&2; exit 1; }
info() { printf '==> %s\n' "$*"; }

usage() {
    sed -n '3,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --tenant)     TENANT="${2:?--tenant needs a subdomain}"; shift 2 ;;
        --dump)       DUMP="${2:?--dump needs a path}";          shift 2 ;;
        --files)      FILES="${2:?--files needs a path}";        shift 2 ;;
        --env)        ENVIRONMENT="${2:?--env needs local|test|prod}"; shift 2 ;;
        --reset)      DO_RESET="on";    shift ;;
        --dry-run)    DRY_RUN="on";     shift ;;
        --skip-files) SKIP_FILES="yes"; shift ;;
        -h|--help)    usage 0 ;;
        *)            die "unknown argument: $1" ;;
    esac
done

[ -n "$TENANT" ] || die "--tenant is required"
[ -n "$DUMP" ]   || die "--dump is required"
[ -f "$DUMP" ]   || die "dump not found: $DUMP"
if [ "$SKIP_FILES" = "no" ]; then
    [ -n "$FILES" ] || die "--files is required (or pass --skip-files)"
    [ -d "$FILES/images" ] || die "no images/ directory under $FILES"
fi
case "$ENVIRONMENT" in local|test|prod) ;; *) die "--env must be local, test or prod" ;; esac

command -v docker >/dev/null || die "docker is required"
[ "$ENVIRONMENT" = "local" ] || command -v kubectl >/dev/null || die "kubectl is required for --env $ENVIRONMENT"

DUMP="$(cd "$(dirname "$DUMP")" && pwd)/$(basename "$DUMP")"
[ "$SKIP_FILES" = "yes" ] || FILES="$(cd "$FILES" && pwd)"

# Under the repo rather than /tmp: Docker Desktop only bind-mounts paths it
# has been told to share, and the repo is already one of them.
WORK="$(mktemp -d "${REPO_ROOT}/.migration-work.XXXXXX")"
PF_PID=""
cleanup() {
    [ -z "$PF_PID" ] || kill "$PF_PID" 2>/dev/null || true
    rm -rf "$WORK"
}
trap cleanup EXIT

# ---------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------
# Production and test reach Cloud SQL through the proxy sidecar already
# running in the backend pod (MT-014 D-7): port-forward lands in the pod's
# network namespace, where the proxy listens on 127.0.0.1:5432.  That
# reuses the deployment's own authorised path -- no new credentials, no IP
# allowlist entry, nothing to install.

secret_key() {
    kubectl --context="$KCTX" -n "$NAMESPACE" get secret akvo-mis \
        -o "jsonpath={.data.$1}" | base64 -d
}

if [ "$ENVIRONMENT" = "local" ]; then
    # shellcheck disable=SC1091
    set -a; . "${REPO_ROOT}/.env"; set +a
    PGHOST="127.0.0.1"; PGPORT="5432"
    PGUSER="${DB_USER:-akvo}"; PGPASSWORD="${DB_PASSWORD:-password}"
    PGDATABASE="${DB_SCHEMA:-mis}"
    STORAGE_DEST="${REPO_ROOT}/${STORAGE_PATH:-./storage}"
else
    [ "$ENVIRONMENT" = "prod" ] && KCTX="$CTX_PROD" || KCTX="$CTX_TEST"
    info "using cluster ${KCTX}"
    POD="$(kubectl --context="$KCTX" -n "$NAMESPACE" get pods \
            -l app=backend -o name 2>/dev/null | head -1)"
    [ -n "$POD" ] || POD="pod/$(kubectl --context="$KCTX" -n "$NAMESPACE" get pods \
            -o name | sed 's|pod/||' | grep '^backend-deployment' | head -1)"
    [ -n "${POD#pod/}" ] || die "no backend pod found in $NAMESPACE"

    PGUSER="$(secret_key db-user)"
    PGPASSWORD="$(secret_key db-password)"
    PGDATABASE="$(secret_key db-schema)"

    PGHOST="127.0.0.1"; PGPORT="55432"
    info "port-forwarding ${POD} ${PGPORT} -> 5432 (Cloud SQL proxy sidecar)"
    kubectl --context="$KCTX" -n "$NAMESPACE" port-forward "$POD" "${PGPORT}:5432" >/dev/null 2>&1 &
    PF_PID=$!
    for _ in $(seq 1 30); do
        (exec 3<>/dev/tcp/127.0.0.1/"$PGPORT") 2>/dev/null && break
        sleep 1
    done
    kill -0 "$PF_PID" 2>/dev/null || die "port-forward died; check cluster credentials (kube ${ENVIRONMENT})"
fi

# How a container reaches the database depends on the Docker flavour, and
# getting it wrong looks like "connection refused" with a healthy listener.
#
# Plain Docker Engine shares the host's network stack, so --network=host
# plus 127.0.0.1 is right.  Docker Desktop (and Colima, Rancher Desktop,
# any VM-backed engine) runs containers inside a VM, where --network=host
# means the VM's loopback -- kubectl port-forward listens on the real host
# and is invisible from there.  host.docker.internal crosses back out.
#
# Probed rather than assumed, because the answer differs per machine and
# the symptom gives no hint which case you are in.
DOCKER_NET_ARGS=()
detect_docker_net() {
    if docker run --rm --network=host "$PSQL_IMAGE" \
            sh -c "nc -z -w3 127.0.0.1 ${PGPORT}" >/dev/null 2>&1; then
        DOCKER_NET_ARGS=(--network=host)
        PGHOST="127.0.0.1"
    elif docker run --rm --add-host=host.docker.internal:host-gateway "$PSQL_IMAGE" \
            sh -c "nc -z -w3 host.docker.internal ${PGPORT}" >/dev/null 2>&1; then
        DOCKER_NET_ARGS=(--add-host=host.docker.internal:host-gateway)
        PGHOST="host.docker.internal"
        info "VM-backed Docker detected; reaching the database via host.docker.internal"
    else
        die "no container route to the database on port ${PGPORT}.
   Tried --network=host and host.docker.internal. Is the database up
   (local) or did the port-forward fail (test/prod)?"
    fi
}

psql_run() {
    docker run --rm -i "${DOCKER_NET_ARGS[@]}" \
        -e PGPASSWORD="$PGPASSWORD" \
        -v "${WORK}:/work:ro" -v "${SCRIPT_DIR}:/sql:ro" \
        "$PSQL_IMAGE" \
        psql -v ON_ERROR_STOP=1 -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" "$@"
}

detect_docker_net

# ---------------------------------------------------------------------
# Resolve the workspace before touching anything
# ---------------------------------------------------------------------
# An unknown subdomain is a typo, and finding out halfway through is worse
# than finding out now.

TENANT_ID="$(psql_run -tAc "SELECT id FROM public.tenant WHERE subdomain = '${TENANT//\'/\'\'}'" | tr -d '[:space:]')"
[ -n "$TENANT_ID" ] || die "no workspace with subdomain '${TENANT}' on ${ENVIRONMENT}. Register it first."
info "workspace '${TENANT}' is tenant id ${TENANT_ID} on ${ENVIRONMENT}"

# ---------------------------------------------------------------------
# Extract the COPY blocks
# ---------------------------------------------------------------------
# The dump is consumed as data, never as DDL (MT-014 D-2): only whitelisted
# COPY blocks are kept, their schema prefix rewritten to the staging
# schema.  \restrict / \unrestrict are stripped -- recent pg_dump builds
# emit them and older psql does not understand them.

info "extracting source rows"
awk -v TABLES="$TABLES" '
    BEGIN { n = split(TABLES, a, " "); for (i = 1; i <= n; i++) want[a[i]] = 1 }
    inblock { print; if ($0 == "\\.") inblock = 0; next }
    /^\\restrict/ || /^\\unrestrict/ { next }
    /^COPY public\./ {
        t = $2; sub(/^public\./, "", t)
        if (t in want) {
            inblock = 1
            line = $0; sub(/public\./, "mig_src.", line); print line
        }
        next
    }
    { next }
' "$DUMP" > "${WORK}/copy.sql"

[ -s "${WORK}/copy.sql" ] || die "no matching COPY blocks found in ${DUMP} -- is it a plain-format pg_dump?"
info "extracted $(grep -c '^COPY mig_src\.' "${WORK}/copy.sql") table(s), $(wc -l < "${WORK}/copy.sql") lines"

# ---------------------------------------------------------------------
# Files first, deliberately (MT-014 D-8)
# ---------------------------------------------------------------------
# If the copy succeeds and the transaction then fails, the result is
# unreferenced files -- harmless, and overwritten by the next attempt.  The
# reverse order risks committed rows whose images 404.

if [ "$SKIP_FILES" = "yes" ]; then
    info "skipping file transfer (--skip-files)"
elif [ "$DRY_RUN" = "on" ]; then
    info "skipping file transfer (--dry-run)"
else
    FILE_COUNT="$(find "$FILES/images" "$FILES/datapoints" -type f 2>/dev/null | wc -l)"
    info "transferring ${FILE_COUNT} file(s) from images/ and datapoints/"
    if [ "$ENVIRONMENT" = "local" ]; then
        mkdir -p "${STORAGE_DEST}/images" "${STORAGE_DEST}/datapoints"
        tar cf - -C "$FILES" images datapoints | tar xf - -C "$STORAGE_DEST"
    else
        tar cf - -C "$FILES" images datapoints \
            | kubectl --context="$KCTX" -n "$NAMESPACE" exec -i "$POD" -- \
                tar xf - -C /app/storage
    fi
    info "files in place"
fi

# ---------------------------------------------------------------------
# The import, as one transaction
# ---------------------------------------------------------------------

[ "$DO_RESET" = "on" ] && info "RESET: every row workspace '${TENANT}' owns will be deleted first"
[ "$DRY_RUN" = "on" ]  && info "DRY RUN: the transaction will be rolled back"

info "importing"
psql_run \
    -v "tenant_id=${TENANT_ID}" \
    -v "copy_data=/work/copy.sql" \
    -v "verify_sql=/sql/verify.sql" \
    -v "do_reset=${DO_RESET}" \
    -v "dry_run=${DRY_RUN}" \
    -f /sql/import.sql

if [ "$DRY_RUN" = "on" ]; then
    info "dry run complete -- nothing was written"
    exit 0
fi

# Printed for the environment that was actually migrated, so the commands
# can be pasted as-is.
if [ "$ENVIRONMENT" = "local" ]; then
    RUN_PREFIX="./dc.sh exec backend"
else
    RUN_PREFIX="kubectl --context=${KCTX} -n ${NAMESPACE} exec -it ${POD} --"
fi

cat <<EOF

==> done. Remaining steps, which are deliberately not automated:

    1. Create a superadmin for the workspace:
         ${RUN_PREFIX} ./manage.py createsuperuser --tenant=${TENANT}
       --tenant is mandatory. Without it the account gets tenant=NULL and
       can sign in at no workspace host at all.

    2. Rebuild the mobile master-data SQLite:
         ${RUN_PREFIX} ./manage.py generate_sqlite --tenant=${TENANT}

    3. Assign roles. Imported users are superusers with no user_role,
       which reproduces the source install rather than repairing it.

EOF
