# Implementation Plan: Logo Generalisation & Landing Page Cleanup

**Issue**: #226  
**Branch**: `feature/226-clean-up-akvo-mis-for-new-development`

---

## Group 1: Logo Cleanup

### 1.1 Delete DWS logo files

```bash
git rm frontend/public/logo-full.png
git rm frontend/public/logo.png
```

Files:
- `frontend/public/logo-full.png` — DWS Department of Water & Sewerage logo
- `frontend/public/logo.png` — older DWS logo (unreferenced)

Note: `frontend/public/logo.svg` was already created in a previous step.

### 1.2 Update `config.js` — `siteLogo`

File: `frontend/src/lib/config.js` line 4

```diff
-  siteLogo: "/logo-full.png",
+  siteLogo: "/logo.svg",
```

### 1.3 Update `Login.jsx` — login logo `src`

File: `frontend/src/pages/login/Login.jsx` — find the `<img>` with `alt="login-logo"`

```diff
-  <img src="./logo192.png" alt="login-logo" />
+  <img src="./logo.svg" alt="login-logo" />
```

### 1.4 Generalise map default centre

File: `frontend/src/lib/config.js` — `mapConfig.defaultCenter`

```diff
-    defaultCenter: [-18.1236015, 178.3805867], // Fiji
+    defaultCenter: [0, 0],
```

**Verify Group 1**:
```bash
grep -r "logo-full\|logo\.png\|logo192" frontend/src/ frontend/public/
# Should return empty
ls frontend/public/logo.svg
# Should exist
```

---

## Group 2: Home Page Content Generalisation

### 2.1 Fix fallback in `Home.jsx`

File: `frontend/src/pages/home/Home.jsx` line 18

```diff
-  const appName = window?.appConfig?.name || "IWSIMS";
+  const appName = window?.appConfig?.name || "Akvo MIS";
```

### 2.2 Generalise home page strings in `ui-text.js`

File: `frontend/src/lib/ui-text.js` — section `// Home Page` (~lines 762–876)

**`homeJumbotronSubtitle`** — replace Fiji/water-sewerage copy:
```diff
-      The Fiji {window.appConfig.name} is a comprehensive platform designed to
-      enhance the management of water and sewerage services in Fiji.
+      A comprehensive platform designed to support data collection, monitoring,
+      and decision-making for your organisation.
```

**`homeHeroEyebrowOrg`**:
```diff
-    homeHeroEyebrowOrg: "Government of Fiji",
+    homeHeroEyebrowOrg: "<Your Organisation>",
```

**`homeHeroEyebrowDept`**:
```diff
-    homeHeroEyebrowDept: "Department of Water & Sewerage",
+    homeHeroEyebrowDept: "<Your Department>",
```

**`homeHeroTitleAccent`**:
```diff
-    homeHeroTitleAccent: "water & sewerage",
+    homeHeroTitleAccent: "monitoring & information",
```

**`homeHeroTitleSuffix`**:
```diff
-    homeHeroTitleSuffix: "services in Fiji.",
+    homeHeroTitleSuffix: "services.",
```

**`homeHeroCtaLearnMore`**:
```diff
-    homeHeroCtaLearnMore: "Learn about our mandate",
+    homeHeroCtaLearnMore: "Learn more",
```

**`homeHeroCaptionTitle`**:
```diff
-      Safe, reliable water
-      <br />
-      for every community in Fiji.
+      Reliable data
+      <br />
+      for every community you serve.
```

**`homeMandateHeadline`**:
```diff
-      Ensuring a <span className="accent">sustainable</span> water and
-      sewerage sector.
+      Ensuring a <span className="accent">sustainable</span> monitoring
+      and reporting system.
```

**`homeMandateText`**:
```diff
-    homeMandateText:
-      "The Department of Water and Sewerage is mandated with the responsibility of ensuring a sustainable water and sewerage sector through the development of innovative policies, efficient service delivery, and rigorous compliance monitoring.",
+    homeMandateText:
+      "Your organisation is mandated with the responsibility of ensuring sustainable service delivery through the development of evidence-based policies, efficient data management, and rigorous compliance monitoring.",
```

**`homeStructureTitle`**:
```diff
-    homeStructureTitle: "Department Structure",
+    homeStructureTitle: "Organisation Structure",
```

**`homeStructureText`**:
```diff
-    homeStructureText:
-      "The Department is headed by the Director of Water and Sewerage with the Technical Unit responsible for monitoring and compliance and Policy Unit responsible for policy and regulatory matters, supported by common cadre support staff.",
+    homeStructureText:
+      "Replace this text with a description of your organisation structure. This section can be updated in ui-text.js or configured via a content management system.",
```

**`homeStructureImage.src`** — replace DWS asset with logo placeholder:
```diff
-      src: "/assets/department-structure.jpg",
+      src: "/logo.svg",
```

**`homeVideoText`**:
```diff
-    homeVideoText:
-      "A short walkthrough of how the platform supports water and sewerage service delivery, monitoring, and decision-making across Fiji.",
+    homeVideoText:
+      "A short walkthrough of how the platform supports data collection, monitoring, and decision-making for your organisation.",
```

**`homeKeyRolesHeadline`**:
```diff
-      Policy, oversight and <span className="accent">compliance</span> across
-      Fiji&apos;s water sector.
+      Policy, oversight and <span className="accent">compliance</span> across
+      your sector.
```

**`homeKeyRolesText`**:
```diff
-    homeKeyRolesText:
-      "The key roles and responsibilities of the Department include policy and legislation development, technical and policy advisory, compliance monitoring, and Water Authority of Fiji oversight.",
+    homeKeyRolesText:
+      "The key roles and responsibilities of the organisation include policy and legislation development, technical and policy advisory, compliance monitoring, and service delivery oversight.",
```

**`homeKeyRolesItems`** — replace all 4 cards with generic MIS platform roles:
```js
homeKeyRolesItems: [
  {
    imgSrc:
      "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?q=80&w=2070&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
    imgAlt: "Policy and legislation",
    title: "Policy & Legislation",
    text: "Formulating regulatory frameworks and policies to promote sustainable and equitable service delivery. Providing expert advice to support effective governance.",
    type: "right",
  },
  {
    imgSrc:
      "https://images.unsplash.com/photo-1708807472445-d33589e6b090?q=80&w=1974&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
    imgAlt: "Monitoring and oversight",
    title: "Monitoring & Oversight",
    text: "Overseeing adherence to established policies, legislation, and industry standards. Ensuring accountability and transparency in service delivery.",
    type: "left",
  },
  {
    imgSrc: "/logo.svg",
    imgAlt: "Technical and policy advisory",
    title: "Technical & Policy Advisory",
    text: "Providing expert advice on sector issues to support effective governance and operational efficiency.",
    type: "right",
  },
  {
    imgSrc:
      "https://plus.unsplash.com/premium_photo-1661964131234-fda88ca041c5?q=80&w=2071&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
    imgAlt: "Service delivery oversight",
    title: "Service Delivery Oversight",
    text: "Serving as the primary organisation responsible for monitoring service delivery and ensuring compliance with national regulations and standards.",
    type: "left",
  },
],
```

**`homeFooterContactDetails`**:
```diff
-    homeFooterContactDetails: [
-      "Department of Water and Sewerage",
-      "Ministry of Public Works and Meteorological Services, and Transport",
-    ],
+    homeFooterContactDetails: [
+      "<Your Organisation>",
+      "<Your Department>",
+    ],
```

**`homeFooterContactAddress`**:
```diff
-    homeFooterContactAddress: [
-      "Private Mail Bag, Suva, Fiji",
-      "Level 4, Nasilivata House, Ratu Mara Road,",
-      "Samabula, Suva",
-    ],
+    homeFooterContactAddress: ["<Your Address>"],
```

**`homeFooterContactPhone`**:
```diff
-    homeFooterContactPhone: "(+679) 3384111",
+    homeFooterContactPhone: "<Your Phone Number>",
```

**`homeFooterAboutText`**:
```diff
-      The Fiji Integrated Water and Sewerage Information Management System (
-      {window.appConfig.name}) is a comprehensive platform designed to enhance
-      the management of water and sewerage services in Fiji. It serves as a
-      centralized hub for data collection, analysis, and reporting, enabling
-      informed decision-making and efficient resource allocation.
+      {window.appConfig.name} is a comprehensive platform designed to support
+      data collection, monitoring, and decision-making for your organisation.
+      It serves as a centralised hub for evidence-based reporting and efficient
+      resource allocation.
```

**`homeFooterCopyrightText`**:
```diff
-    homeFooterCopyrightText: "© 2025 Department of Water and Sewerage",
+    homeFooterCopyrightText: "© 2025 <Your Organisation>",
```

**Verify Group 2**:
```bash
grep -n "Fiji\|IWSIMS\|Water and Sewerage\|DWS\|iwsims" frontend/src/lib/ui-text.js
grep -n "IWSIMS" frontend/src/pages/home/Home.jsx
# Both should return empty
```

---

## Group 3: `SHOW_LANDING_PAGE` Environment Toggle

### 3.1 `env.example`

Add after the existing APP_* block:

```env
SHOW_LANDING_PAGE=false
```

### 3.2 `backend/mis/settings.py`

Add after the existing `APP_NAME`/`APP_SHORT_NAME` block:

```python
SHOW_LANDING_PAGE = environ.get("SHOW_LANDING_PAGE", "false").lower() == "true"
```

### 3.3 `backend/api/v1/v1_data/management/commands/generate_config.py`

Add import:
```diff
-from mis.settings import COUNTRY_NAME, APP_NAME, APP_SHORT_NAME, APK_NAME
+from mis.settings import COUNTRY_NAME, APP_NAME, APP_SHORT_NAME, APK_NAME, SHOW_LANDING_PAGE
```

Add field to `appConfig` dict:
```diff
     json.dumps({
         "name": APP_NAME,
         "shortName": APP_SHORT_NAME,
         "apkName": APK_NAME,
+        "showLandingPage": SHOW_LANDING_PAGE,
     }),
```

### 3.4 `frontend/src/App.js`

**Context**: When `showLandingPage` is false a logged-in user navigating to `/` must not be bounced to `/login` — they should go to `/control-center`. `Login.jsx` does not guard against already-authenticated users, so a redirect chain `/` → `/login` would show the login form to a logged-in user. The route needs three-way logic.

`authUser` from the store is already destructured in `App` but `RouteList` is a separate component without store access. Add a `store.useState` call inside `RouteList` to get `authUser` for the route element.

Replace the home route (line ~105):
```diff
 const RouteList = () => {
+  const { user: authUser } = store.useState((state) => state);
   return (
     <Routes>
-      <Route exact path="/" element={<Home />} />
+      <Route
+        exact
+        path="/"
+        element={
+          window?.appConfig?.showLandingPage ? (
+            <Home />
+          ) : authUser ? (
+            <Navigate to="/control-center" />
+          ) : (
+            <Navigate to="/login" />
+          )
+        }
+      />
```

Behaviour:
- `showLandingPage=true` → render `<Home />`
- `showLandingPage=false` + logged in (`authUser` set) → redirect to `/control-center`
- `showLandingPage=false` + not logged in → redirect to `/login`

Also leave the `/data` route as-is — it stays for deployers who enable the landing page.

**Verify Group 3**:
```bash
grep -n "SHOW_LANDING_PAGE" env.example backend/mis/settings.py backend/api/v1/v1_data/management/commands/generate_config.py
grep -n "showLandingPage" frontend/src/App.js
```

---

## Group 4: Document Binary PWA Assets

No code changes. Add a comment block in `frontend/public/` relevant README or CLAUDE.md section.

**Binary files that deployers must replace**:

| File | Purpose | Size |
|---|---|---|
| `frontend/public/logo192.png` | PWA icon (192×192) | — |
| `frontend/public/logo512.png` | PWA icon (512×512) | — |
| `frontend/public/favicon.ico` | Browser tab icon | — |

These files are referenced in `frontend/public/manifest.json` and `frontend/public/index.html`. They cannot carry generic placeholder text and are intentionally left as generic Akvo MIS placeholders. Deployers should replace them with their own branded images before going live.

---

## Commit Strategy

All changes in this plan are committed together as one logical commit under issue #226:

```
[#226] Generalise logo and home page content; add SHOW_LANDING_PAGE toggle
```

---

## Verification Checklist

```bash
# No DWS/Fiji references remain in frontend source
grep -rn "Fiji\|IWSIMS\|Water and Sewerage\|logo-full\|logo192\.png\|department-structure" \
  frontend/src/ frontend/public/logo*.png 2>/dev/null

# Logo SVG exists and is self-hosted
ls -la frontend/public/logo.svg

# Deleted files are gone
ls frontend/public/logo-full.png frontend/public/logo.png 2>/dev/null
# Should show "No such file"

# SHOW_LANDING_PAGE wired end-to-end
grep "SHOW_LANDING_PAGE" env.example
grep "SHOW_LANDING_PAGE" backend/mis/settings.py
grep "showLandingPage" backend/api/v1/v1_data/management/commands/generate_config.py
grep "showLandingPage" frontend/src/App.js
```
