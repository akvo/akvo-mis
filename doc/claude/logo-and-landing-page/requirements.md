# Requirements: Logo Generalisation & Landing Page Cleanup

**Issue**: #226  
**Branch**: `feature/226-clean-up-akvo-mis-for-new-development`

---

## User Acceptance Criteria

- No DWS/IWSIMS/Fiji-specific images or text are visible in the frontend (login, home page, navbar)
- Deployers can replace the logo by dropping a single file into `frontend/public/`
- The landing page can be toggled on/off via `.env`; the default is **off** (unauthenticated users see the login page)
- Binary PWA assets (`logo192.png`, `logo512.png`, `favicon.ico`) are documented as deployer-replaceable

---

## Functional Requirements

### FR-1: Replace Logo Images with a Generic SVG Placeholder

**Context**: `frontend/public/logo-full.png` is the DWS Department of Water & Sewerage logo and is referenced by `siteLogo` in `frontend/src/lib/config.js`. `frontend/public/logo.png` is an older DWS logo that is unreferenced but still present.

**Changes**:
- `frontend/public/logo.svg` — already created; placeholder SVG with "Akvo MIS" text and "Replace with your organisation logo" subtitle
- `frontend/public/logo-full.png` — delete
- `frontend/public/logo.png` — delete
- `frontend/src/lib/config.js` line 4: `siteLogo: "/logo-full.png"` → `siteLogo: "/logo.svg"`
- `frontend/src/pages/login/Login.jsx`: login logo `src="./logo192.png"` → `src="./logo.svg"`

**Acceptance**: After changes, no DWS logo image is served or referenced; the generic SVG placeholder is shown on the login page and navbar.

---

### FR-2: Generalise DWS/Fiji-Specific Home Page Text

**Context**: `frontend/src/lib/ui-text.js` contains the entire home page copy. All strings are specific to the Department of Water & Sewerage, Fiji. They must be replaced with platform-neutral defaults that any deployer can understand and override.

**Strings to generalise** (all under the `// Home Page` comment, lines ~750–876):

| Key | Current value | Generic replacement |
|---|---|---|
| `homeJumbotronSubtitle` | "The Fiji {appConfig.name} is a comprehensive platform designed to enhance the management of water and sewerage services in Fiji." | "A comprehensive platform designed to support data collection, monitoring, and decision-making for your organisation." |
| `homeHeroEyebrowOrg` | `"Government of Fiji"` | `"<Your Organisation>"` |
| `homeHeroEyebrowDept` | `"Department of Water & Sewerage"` | `"<Your Department>"` |
| `homeHeroTitleAccent` | `"water & sewerage"` | `"monitoring & information"` |
| `homeHeroTitleSuffix` | `"services in Fiji."` | `"services."` |
| `homeHeroCtaLearnMore` | `"Learn about our mandate"` | `"Learn more"` |
| `homeHeroCaptionTitle` | "Safe, reliable water for every community in Fiji." | "Reliable data for every community you serve." |
| `homeMandateTitle` | `"Our Mandate"` | `"Our Mandate"` (keep) |
| `homeMandateHeadline` | "Ensuring a sustainable water and sewerage sector." | "Ensuring a sustainable monitoring and reporting system." |
| `homeMandateText` | DWS-specific mandate paragraph | Generic MIS mandate paragraph |
| `homeStructureTitle` | `"Department Structure"` | `"Organisation Structure"` |
| `homeStructureText` | DWS-specific org description | Generic org structure placeholder |
| `homeStructureImage.src` | `"/assets/department-structure.jpg"` | `"/logo.svg"` |
| `homeVideoText` | Fiji water/sewerage walkthrough text | Generic platform walkthrough text |
| `homeKeyRolesHeadline` | "Policy, oversight and compliance across Fiji's water sector." | "Policy, oversight and compliance across your sector." |
| `homeKeyRolesText` | DWS key roles description | Generic MIS key roles description |
| `homeKeyRolesItems[*]` | 4 DWS-specific role cards (incl. "Water Authority of Fiji Oversight") | 4 generic MIS platform role cards |
| `homeFooterContactDetails` | DWS org and ministry names | `["<Your Organisation>", "<Your Department>"]` |
| `homeFooterContactAddress` | Fiji postal address | `["<Your Address>"]` |
| `homeFooterContactPhone` | `"(+679) 3384111"` | `"<Your Phone Number>"` |
| `homeFooterAboutText` | IWSIMS/Fiji-specific description | Generic Akvo MIS description |
| `homeFooterCopyrightText` | `"© 2025 Department of Water and Sewerage"` | `"© 2025 <Your Organisation>"` |

**Also update**:
- `frontend/src/pages/home/Home.jsx` line 18: fallback `"IWSIMS"` → `"Akvo MIS"`

**Acceptance**: Home page displays no DWS/Fiji-specific text when loaded with default env configuration.

---

### FR-3: Generalise Map Default Centre

**Context**: `frontend/src/lib/config.js` has `mapConfig.defaultCenter: [-18.1236015, 178.3805867]` — the centre of Fiji. This should be a world-neutral default.

**Change**: `defaultCenter: [0, 0]` (equator/prime meridian — centred on the world map)

**Acceptance**: Map loads centred near the world view, not Fiji.

---

### FR-4: Add `SHOW_LANDING_PAGE` Environment Toggle

**Context**: The landing page (`/`) is a rich, organisation-specific marketing page. For most platform deployments the login page is the right entry point. The toggle lets deployers opt in to showing the landing page without code changes.

**Mechanism**:
1. `env.example` — add `SHOW_LANDING_PAGE=false`
2. `backend/mis/settings.py` — read `SHOW_LANDING_PAGE = environ.get("SHOW_LANDING_PAGE", "false").lower() == "true"`
3. `backend/api/v1/v1_data/management/commands/generate_config.py` — include `"showLandingPage": SHOW_LANDING_PAGE` in the `appConfig` JSON block
4. `frontend/src/App.js` — replace `<Route exact path="/" element={<Home />} />` with a three-way conditional:
   - `showLandingPage=true` → render `<Home />`
   - `showLandingPage=false` + user logged in → `<Navigate to="/control-center" />`
   - `showLandingPage=false` + user not logged in → `<Navigate to="/login" />`

The logged-in redirect to `/control-center` is required because `Login.jsx` does not guard against already-authenticated users — without it, a logged-in user navigating to `/` would see the login form.

**Default**: `SHOW_LANDING_PAGE=false` — unauthenticated users see the login page; authenticated users go directly to the control centre.

**Acceptance**:
- With default config, navigating to `/` as an unauthenticated user redirects to `/login`
- With default config, navigating to `/` as a logged-in user redirects to `/control-center`
- Setting `SHOW_LANDING_PAGE=true` and regenerating config makes `/` render the home page for all users

---

## Non-Functional Requirements

### NFR-1: No External Image Dependencies

The logo placeholder must be self-hosted (local SVG). External URLs such as `https://placehold.net/` must not be used — they create an external runtime dependency and will fail in air-gapped deployments.

### NFR-2: Binary PWA Assets Are Documented, Not Changed

`logo192.png`, `logo512.png`, and `favicon.ico` are binary files. They are not changed by this initiative. Deployers are responsible for replacing them. This requirement is satisfied by documentation in the implementation plan and README.

### NFR-3: Frontend ESLint Compliance

All changes to `frontend/src/` must pass `npx eslint` with the project's config:
- Every `if/else` body uses braces (`curly: error`)
- No bare `undefined` references (`no-undefined: warn`)
- Callbacks use arrow functions
