# Design: Logo Generalisation & Landing Page Cleanup

**Issue**: #226

---

## Decision Log

### D-1: Local SVG Placeholder vs. External Placeholder Service

**Options considered**:
- A: Use `https://placehold.net/400x400.png` (or similar external service)
- B: Inline SVG in HTML/JSX
- C: Self-hosted local SVG file at `frontend/public/logo.svg` ✅

**Decision**: C — local SVG file.

**Rationale**:
- Option A creates a hard runtime dependency on an external service. Air-gapped and low-connectivity deployments would fail to display the logo.
- Option B ties the placeholder to a specific component, making it harder for deployers to replace with a single file swap.
- Option C gives deployers one clear replacement target (`frontend/public/logo.svg`) and works offline. The SVG already contains a short "Replace with your organisation logo" subtitle, making the placeholder intent self-documenting.

---

### D-2: Where to Toggle the Landing Page

**Options considered**:
- A: Django URL-level guard — 404 or redirect `/` at the backend
- B: Nginx-level rewrite rule
- C: `appConfig.showLandingPage` flag evaluated in frontend routing ✅

**Decision**: C — frontend routing via `appConfig`.

**Rationale**:
- Option A requires a backend route change and a Django request round-trip for what is a purely presentational decision.
- Option B requires nginx config changes and knowledge of the nginx layer, which varies between development and production.
- Option C fits the existing pattern: `window.appConfig` already carries `name`, `shortName`, `apkName`. Adding `showLandingPage` keeps all runtime UI configuration in one place. The frontend already reads `appConfig` before rendering; the route guard is a single ternary in `App.js`.

**Flow**:
```
SHOW_LANDING_PAGE (env)
  → settings.py (Python bool)
    → generate_config.py (JSON bool in appConfig)
      → /api/v1/config.js (served by backend)
        → window.appConfig.showLandingPage (frontend)
          → App.js: route / → <Home /> or <Navigate to="/login" />
```

---

### D-3: Default for `SHOW_LANDING_PAGE`

**Decision**: `false`

**Rationale**: The home page is DWS/Fiji-specific content even after generalisation. Most new deployers will configure their own home page content or not need one at all. Making the default `false` means a fresh deployment is immediately functional (login page) without requiring any env configuration. Deployers who want the landing page opt in explicitly.

---

### D-4: Scope of Home Page Text Changes

**Decision**: Replace all DWS/Fiji-specific strings in `ui-text.js` with generic placeholder text (angle-bracket style for contact details, generic MIS copy for narrative sections). Do not delete the home page sections.

**Rationale**: Deleting sections (hero, mandate, key roles, footer) would break the React components that render them. The components themselves are generic and reusable. Replacing text with clearly marked placeholders (`"<Your Organisation>"`) signals to deployers exactly what to customise without touching component code.

---

### D-5: `homeKeyRolesItems` Image Sources

The four key-role cards contain a mix of Unsplash URLs and a local asset path (`/assets/technical-advisory.jpg`). The Unsplash URLs are external but generic (not DWS-specific photos). The local path references a DWS-specific asset.

**Decision**: Keep Unsplash URLs as-is (they are not DWS-branded); replace `/assets/technical-advisory.jpg` with `/logo.svg` as a visible placeholder. Document that deployers should replace role card images.

---

### D-6: `homeJumbotronImage`

The hero jumbotron image is an Unsplash water landscape photo. It is not DWS-branded.

**Decision**: Leave unchanged. It is generic content that any deployer will likely replace alongside the role card images.

---

## Component Interaction

```mermaid
graph LR
    A[env.example\nSHOW_LANDING_PAGE=false] --> B[settings.py\nSHOW_LANDING_PAGE bool]
    B --> C[generate_config.py\nappConfig.showLandingPage]
    C --> D[/api/v1/config.js]
    D --> E[window.appConfig]
    E --> F{App.js route /}
    F -->|true| G[Home page]
    F -->|false| H[Navigate to /login]

    I[frontend/public/logo.svg] --> J[config.js siteLogo]
    J --> K[Navbar logo]
    I --> L[Login.jsx logo]
```
