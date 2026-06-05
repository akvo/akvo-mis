#!/usr/bin/env bash
set -exuo pipefail

# Skip on tag builds (production deploy not yet configured for akvo-mis SaaS).
tag_pattern="^[0-9]+\.[0-9]+\.[0-9]+$"
if [[ "${CI_BRANCH}" =~ $tag_pattern || "${CI_TAG:=}" =~ $tag_pattern ]]; then
    echo "Tag build detected. Production deploy not yet configured for akvo-mis SaaS. Skip deploy."
    exit 0
fi

[[ "${CI_BRANCH}" != "main" ]] && { echo "Branch is not main. Skip deploy."; exit 0; }
[[ "${CI_PULL_REQUEST}" == "true" ]] && { echo "Pull request. Skip deploy."; exit 0; }

NAMESPACE="akvo-mis-namespace"
IMAGE_PREFIX="eu.gcr.io/akvo-lumen/akvo-mis"

auth () {
    gcloud auth activate-service-account --key-file=/home/runner/work/akvo-mis/credentials/gcp.json
    gcloud config set project akvo-lumen
    gcloud config set container/cluster europe-west1-d
    gcloud config set compute/zone europe-west1-d
    gcloud config set container/use_client_certificate False
    gcloud auth configure-docker "eu.gcr.io"
    gcloud container clusters get-credentials test
}

push_image () {
    docker push "${IMAGE_PREFIX}/${1}:latest-test"
    docker push "${IMAGE_PREFIX}/${1}:${CI_COMMIT}"
}

auth

push_image backend
push_image worker
push_image frontend

# Rollout-restart each Deployment in the new namespace.
for d in frontend-deployment backend-deployment worker-deployment; do
    kubectl -n "${NAMESPACE}" rollout restart deployment/"${d}"
done

# Wait for the longest-to-converge (backend) — its readiness probe holds
# the rollout until /api/v1/health/check returns 200.
kubectl -n "${NAMESPACE}" rollout status deployment/backend-deployment --timeout=5m
