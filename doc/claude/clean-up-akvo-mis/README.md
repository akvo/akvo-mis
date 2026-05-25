# Clean Up Akvo MIS for Open Core SaaS Platform

## Overview

This initiative removes all IWSIMS project-specific configurations and data from the `akvo/akvo-mis` repository, repositioning it as a clean, deployable Open Core SaaS platform base.

**GitHub Issue**: #226

## Problem Statement

The `akvo-mis` repository was originally developed and operated as the **IWSIMS** (Integrated Water Supply Information Management System) deployment. As a result, the codebase accumulated project-specific identifiers, form definitions, and hardcoded references that make it difficult to use as a generic platform.

The repository needs to read as a neutral SaaS platform — not as an IWSIMS product — so that:
- New tenants can deploy it without stripping out another organization's data
- The open-source identity is clearly `akvo-mis`, not IWSIMS
- CI/CD pipelines are clean and free of legacy duplicate tokens

## Scope

| Area | Files | Change Type |
|---|---|---|
| `backend/source/forms/` | 15 numbered JSON files | Delete |
| Platform identity | `env.example`, `frontend/package.json`, `frontend/public/manifest.json` | Rebrand `IWSIMS` → `Akvo MIS` |
| Mobile build configs | `app/src/build.{prod,staging,testing}.js` | Replace hardcoded URLs with placeholders |
| Mobile app identity | `app/app.json`, `app/package.json`, `app/src/build.json` | Rename `dws-datapro` → `akvo-mis` |
| K8s deployment template | `ci/k8s/deployment.template.yml` | Fix 3× hardcoded `iwsims` service-account subPath |
| K8s wait script | `ci/k8s/wait-for-k8s-deployment-to-be-ready.sh` | Fix hardcoded pod labels |
| CI deploy script | `ci/deploy.sh` | Fix hardcoded credentials path |
| Docker Compose | `docker-compose.override.yml`, `docker-compose.test.yml` | Fix credential paths |
| CI pipeline | `.github/workflows/main.yml` | Remove `COVERALLS_IWSIMS_TOKEN` |
| Nginx + dev proxy | `frontend/nginx/conf.d/default.conf`, `frontend/src/setupProxy.js` | Fix APK filename `dws-datapro` → `akvo-mis` |
| Stress test scripts | `doc/script/stress_tests/` (3 files) | Replace hardcoded `iwsims.akvotest.org` URLs |

## Documents in This Directory

| File | Purpose |
|---|---|
| [README.md](README.md) | This file — initiative overview |
| [requirements.md](requirements.md) | Functional and non-functional requirements |
| [design.md](design.md) | Design decisions and rationale |
| [implementation-plan.md](implementation-plan.md) | Step-by-step task breakdown with file targets |

## Key Decisions

- **Keep** example and test form files — they serve as generic demos
- **Identity**: `APP_SHORT_NAME=akvo-mis`, `APP_NAME="Akvo MIS"`
- **Mobile URLs**: Replaced with placeholder pattern, not a new hardcoded domain
- **Sentry**: Already generic (env-var driven) — no changes needed
- **K8s namespace**: Template-driven via `APP_SHORT_NAME` — consistent after fixes

## Branch

`feature/226-clean-up-akvo-mis-for-new-development`
