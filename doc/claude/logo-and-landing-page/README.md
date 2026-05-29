# Logo Generalisation & Landing Page Cleanup

## Overview

This sub-initiative removes the remaining IWSIMS/DWS/Fiji-specific branding from the frontend: the logo images and the entire public-facing home page content.

It also adds a `SHOW_LANDING_PAGE` environment toggle so deployers can choose whether unauthenticated users land on the rich home page or are sent directly to login. The default is `false` (login as main page), which is the right default for most platform deployments.

**Parent issue**: #226  
**Branch**: `feature/226-clean-up-akvo-mis-for-new-development`

## Scope

| Area | What changes |
|---|---|
| `frontend/public/logo.svg` | Already created — SVG placeholder (no action needed) |
| `frontend/public/logo-full.png` | Delete (DWS logo) |
| `frontend/public/logo.png` | Delete (DWS logo, unreferenced) |
| `frontend/src/lib/config.js` | `siteLogo` → `/logo.svg` |
| `frontend/src/pages/login/Login.jsx` | Login logo `src` → `./logo.svg` |
| `frontend/src/pages/home/Home.jsx` | Fallback `"IWSIMS"` → `"Akvo MIS"` |
| `frontend/src/lib/ui-text.js` | Generalise ~12 DWS/Fiji-specific home-page strings |
| `frontend/src/lib/config.js` | Map default centre → world centre (0, 0) |
| `backend/mis/settings.py` | Add `SHOW_LANDING_PAGE` setting |
| `backend/api/v1/v1_data/management/commands/generate_config.py` | Emit `showLandingPage` in `appConfig` |
| `frontend/src/App.js` | Route `/` conditionally to `<Home />` or `<Navigate to="/login" />` |
| `env.example` | Document `SHOW_LANDING_PAGE=false` |

## Binary Assets (deployer action required)

`frontend/public/logo192.png`, `logo512.png`, and `favicon.ico` are binary files that cannot carry generic text. They are left in place but documented: deployers **must** replace them with their own branding before going live.

## Documents

- [requirements.md](requirements.md) — functional and non-functional requirements
- [design.md](design.md) — key decisions and rationale
- [implementation-plan.md](implementation-plan.md) — ordered task list with file targets
