import "./App.scss";
import React, { useContext, useEffect, useState } from "react";
import { Route, Routes, Navigate, useLocation } from "react-router-dom";
import {
  Home,
  Login,
  Register,
  Activate,
  Configure,
  ControlCenterLayout,
  Users,
  AddUser,
  Forms,
  ManageData,
  Approvals,
  ApproversTree,
  Profile,
  EditProfile,
  UploadData,
  NewsEvents,
  HowWeWork,
  Terms,
  Privacy,
  Reports,
  Report,
  Submissions,
  Settings,
  Organisations,
  AddOrganisation,
  MobileAssignment,
  AddAssignment,
  Levels,
  MasterData,
  MasterDataAttributes,
  ManageEntityTypes,
  AddAdministration,
  AddAttribute,
  AddEntity,
  EntityData,
  AddEntityData,
  ControlCenter,
  UploadAdministrationData,
  UploadEntitiesData,
  DownloadAdministrationData,
  MonitoringDetail,
  Downloads,
  DownloadEntitiesData,
  Roles,
  AddRole,
  ManageDraft,
  ManageDraftForm,
  FormBuilderList,
  FormBuilderCreate,
  FormBuilderEdit,
  FindWorkspace,
  WorkspaceNotFound,
  DashboardList,
  DashboardBuilder,
  DashboardViewer,
} from "./pages";
import { useCookies } from "react-cookie";
import { store, api, config } from "./lib";
import { Layout, PageLoader, ChatbotWidget } from "./components";
import { useNotification } from "./util/hooks";
import { eraseCookieFromAllPaths } from "./util/date";
import { reloadData, fetchPublishedForms } from "./util/form";
import { fetchLevels } from "./util/level";
import {
  baseDomain,
  fetchTenant,
  onBaseDomainHost,
  workspaceUrl,
} from "./util/tenant";
import { ability, AbilityContext } from "./components/can";

// Session validity is not decided here. Two authorities already settle it and
// neither can be poisoned by client state: the browser drops AUTH_TOKEN of its
// own accord when the expiry the server set passes, and the API answers 401 on
// a token that is no longer good — which the bootstrap below turns into a
// sign-out. This component used to consult a third, JS-written `expiration_time`
// cookie, which was written with no path and so bound itself to whichever page
// happened to write it. A copy under one path shadowed the value at "/" on
// read, so a single expired session locked the account out permanently: every
// later login wrote a fresh expiry that could never be seen.
const Private = ({ element: Element, alias }) => {
  const ability = useContext(AbilityContext);

  const { user: authUser } = store.useState((state) => state);
  if (authUser) {
    // A workspace with no named level 0 and no root cannot render a
    // dashboard — every administration-scoped screen would come up empty.
    // The configuration form is the only reachable route until it is done.
    if (!authUser.configured) {
      return <Navigate to="/configure" />;
    }
    return ability.can("manage", alias) ||
      ability.can("read", alias) ||
      ability.can("create", alias) ||
      ability.can("edit", alias) ||
      ability.can("upload", alias) ? (
      <Element />
    ) : (
      <Navigate to="/not-found" />
    );
  }
  return <Navigate to="/login" />;
};

const RouteList = () => {
  const { user: authUser, tenantMissing } = store.useState((state) => state);
  // The main site of a SaaS deployment: it signs people up and points
  // them at their workspace, but it belongs to none, so there is nothing
  // to sign in to here — the backend refuses a login on it. A
  // single-host deployment has no base domain and so never takes this
  // branch, which is what keeps its /login working exactly as before.
  //
  // Decided by the host, not by the tenant lookup. This used to wait for
  // the lookup and read "no tenant" as "the main site", which is also
  // what an address like `sleman.app.com` that belongs to nobody answers
  // — so the sign-up form rendered there and offered to create
  // `<name>.sleman.app.com`.
  const onBaseDomain = Boolean(baseDomain()) && onBaseDomainHost();

  // Not a route: on a host the deployment does not serve, every call the
  // app would make is refused, so there is no page here to be on.
  if (tenantMissing) {
    return <WorkspaceNotFound />;
  }
  return (
    <Routes>
      <Route
        exact
        path="/"
        element={
          window?.appConfig?.showLandingPage ? (
            <Home />
          ) : authUser ? (
            <Navigate to="/control-center" />
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        exact
        path="/login"
        element={onBaseDomain ? <Navigate to="/find-workspace" /> : <Login />}
      />
      <Route exact path="/find-workspace" element={<FindWorkspace />} />
      <Route exact path="/login/:invitationId" element={<Login />} />
      <Route exact path="/forgot-password" element={<Login />} />
      <Route
        exact
        path="/register"
        element={onBaseDomainHost() ? <Register /> : <Navigate to="/" />}
      />
      <Route exact path="/activate/:token" element={<Activate />} />
      {/* Not wrapped in Private: Private sends every unconfigured user
          here, so guarding this route the same way would loop. Configure
          does its own redirects for the no-session and already-done
          cases. */}
      <Route exact path="/configure" element={<Configure />} />
      <Route exact path="/data" element={<Home />} />
      <Route
        path="/control-center"
        element={
          <Private element={ControlCenterLayout} alias="control-center" />
        }
      >
        <Route
          path="users/add"
          element={<Private element={AddUser} alias="user" />}
        />
        <Route
          path="users/:id"
          element={<Private element={AddUser} alias="user" />}
        />
        <Route
          index
          element={<Private element={ControlCenter} alias="control-center" />}
        />
        <Route
          path="users"
          element={<Private element={Users} alias="user" />}
        />
        <Route
          path="roles"
          element={<Private element={Roles} alias="roles" />}
        />
        <Route
          path="roles/add"
          element={<Private element={AddRole} alias="roles" />}
        />
        <Route
          path="roles/:id"
          element={<Private element={AddRole} alias="roles" />}
        />
        <Route
          path="approvers/tree"
          element={<Private element={ApproversTree} alias="approvers" />}
        />
        <Route
          path="form-builder"
          element={<Private element={FormBuilderList} alias="form-builder" />}
        />
        <Route
          path="form-builder/create"
          element={<Private element={FormBuilderCreate} alias="form-builder" />}
        />
        <Route
          path="form-builder/:formId/edit"
          element={<Private element={FormBuilderEdit} alias="form-builder" />}
        />
        <Route
          path="data"
          element={<Private element={ManageData} alias="data" />}
        />
        <Route
          path="data/:form/monitoring/:parentId"
          element={<Private element={MonitoringDetail} alias="data" />}
        />
        <Route
          path="master-data/administration"
          element={<Private element={MasterData} alias="master-data" />}
        />
        <Route
          path="master-data/levels"
          element={<Private element={Levels} alias="master-data" />}
        />
        <Route
          path="master-data/administration/upload"
          element={
            <Private element={UploadAdministrationData} alias="master-data" />
          }
        />
        <Route
          path="master-data/administration/download"
          element={
            <Private element={DownloadAdministrationData} alias="master-data" />
          }
        />
        <Route
          path="master-data/administration/add"
          element={<Private element={AddAdministration} alias="master-data" />}
        />
        <Route
          path="master-data/administration/:id"
          element={<Private element={AddAdministration} alias="master-data" />}
        />
        <Route
          path="master-data/attributes"
          element={
            <Private element={MasterDataAttributes} alias="master-data" />
          }
        />
        <Route
          path="master-data/attributes/add"
          element={<Private element={AddAttribute} alias="master-data" />}
        />
        <Route
          path="master-data/attributes/:id"
          element={<Private element={AddAttribute} alias="master-data" />}
        />
        <Route
          path="master-data/entity-types"
          element={<Private element={ManageEntityTypes} alias="master-data" />}
        />
        <Route
          path="master-data/entity-types/add"
          element={<Private element={AddEntity} alias="master-data" />}
        />
        <Route
          path="master-data/entity-types/:id"
          element={<Private element={AddEntity} alias="master-data" />}
        />
        <Route
          path="master-data/entities"
          element={<Private element={EntityData} alias="master-data" />}
        />
        <Route
          path="master-data/entities/add"
          element={<Private element={AddEntityData} alias="master-data" />}
        />
        <Route
          path="master-data/entities/upload"
          element={<Private element={UploadEntitiesData} alias="master-data" />}
        />
        <Route
          path="master-data/entities/download"
          element={
            <Private element={DownloadEntitiesData} alias="master-data" />
          }
        />
        <Route
          path="master-data/entities/:id"
          element={<Private element={AddEntityData} alias="master-data" />}
        />
        <Route
          path="data/upload"
          element={<Private element={UploadData} alias="data" />}
        />
        <Route
          path="data/submissions"
          element={<Private element={Submissions} alias="data" />}
        />
        <Route
          path="data/draft"
          element={<Private element={ManageDraft} alias="data" />}
        />
        <Route
          path="data/draft/:formId"
          element={<Private element={ManageDraftForm} alias="data" />}
        />
        <Route
          path="approvals"
          element={<Private element={Approvals} alias="approvals" />}
        />
        <Route
          path="master-data/organisations/add"
          element={<Private element={AddOrganisation} alias="organisation" />}
        />
        <Route
          path="master-data/organisations/:id"
          element={<Private element={AddOrganisation} alias="organisation" />}
        />
        <Route
          path="master-data/organisations"
          element={<Private element={Organisations} alias="organisation" />}
        />
        <Route
          path="mobile-assignment"
          element={<Private element={MobileAssignment} alias="mobile" />}
        />
        <Route
          path="mobile-assignment/add"
          element={<Private element={AddAssignment} alias="mobile" />}
        />
        <Route
          path="mobile-assignment/:id"
          element={<Private element={AddAssignment} alias="mobile" />}
        />
        <Route exact path="form/:formId" element={<Forms />} />
        <Route exact path="form/:formId/:uuid" element={<Forms />} />
        <Route
          path="profile"
          element={<Private element={Profile} alias="profile" />}
        />
        <Route
          path="profile/edit"
          element={<Private element={EditProfile} alias="profile" />}
        />
        <Route
          path="dashboard"
          element={<Private element={DashboardList} alias="dashboard" />}
        />
      </Route>
      <Route
        path="/control-center/dashboard/:slug"
        element={<Private element={DashboardBuilder} alias="dashboard" />}
      />
      <Route
        path="/dashboards/:slug"
        element={<Private element={DashboardViewer} alias="dashboard" />}
      />
      <Route
        path="/downloads"
        element={<Private element={Downloads} alias="downloads" />}
      />
      <Route
        path="/settings"
        element={<Private element={Settings} alias="settings" />}
      />
      <Route
        path="/reports"
        element={<Private element={Reports} alias="reports" />}
      />
      <Route
        path="/report/:templateId"
        element={<Private element={Report} alias="reports" />}
      />
      <Route path="/news-events" element={<NewsEvents />} />
      <Route path="/how-we-work" element={<HowWeWork />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/privacy-policy" element={<Privacy />} />
      <Route exact path="/coming-soon" element={<div />} />
      <Route exact path="/not-found" element={<div />} />
      <Route path="*" element={<Navigate replace to="/not-found" />} />
    </Routes>
  );
};

const App = () => {
  const {
    user: authUser,
    isLoggedIn,
    tenant,
    tenantLoaded,
  } = store.useState((state) => state);
  const [cookies] = useCookies(["AUTH_TOKEN"]);
  const [loading, setLoading] = useState(true);
  const [formsLoading, setFormsLoading] = useState(true);
  const { notify } = useNotification();
  const pageLocation = useLocation();

  const public_state = config.allowedGlobal
    .map((x) => location.pathname.includes(x))
    .filter((x) => x)?.length;

  // detect location change to reset advanced filters
  useEffect(() => {
    store.update((s) => {
      s.advancedFilters = [];
      s.showAdvancedFilters = false;
    });
  }, [pageLocation]);

  // Fetch published forms at bootstrap (replaces the window.forms global
  // baked into config.js). Gates render so dropdowns/dashboards never show an
  // empty list before the forms resolve.
  //
  // Refetched when auth changes: the endpoint is now tenant-scoped, so the
  // bootstrap call made before sign-in returns nothing and the list has to
  // be rebuilt for the tenant once we know who is asking.
  useEffect(() => {
    // Re-gate on every refetch, not just the bootstrap one: without this the
    // post-login pass leaves the old (empty, pre-tenant) list on screen while
    // the tenant-scoped request is in flight.
    setFormsLoading(true);
    fetchLevels();
    // Which workspace this host is, resolved under the same gate as the
    // forms: no route decision may be made before the answer arrives, or
    // the base domain renders /login for a moment before redirecting to
    // find-workspace.
    Promise.all([fetchTenant(), fetchPublishedForms()])
      .catch((err) => {
        console.error(err);
      })
      .finally(() => {
        setFormsLoading(false);
      });
  }, [isLoggedIn]);

  useEffect(() => {
    if (!location.pathname.includes("/login")) {
      if (!authUser && !isLoggedIn && cookies && !!cookies.AUTH_TOKEN) {
        api
          .get("profile", {
            headers: { Authorization: `Bearer ${cookies.AUTH_TOKEN}` },
          })
          .then((res) => {
            store.update((s) => {
              s.isLoggedIn = true;
              s.user = res.data;
            });
            reloadData(res.data);
            api.setToken(cookies.AUTH_TOKEN);
            setLoading(false);
          })
          .catch((err) => {
            // The host boundary refuses this session and names the
            // workspace it does belong to. Nothing is wrong with the
            // session — only with where it is being used — so the fix is
            // to go there, not to sign out. This is also the only place
            // the right address can come from: the profile call that
            // would have carried it is the very call being refused.
            const ownWorkspace = err.response?.data?.subdomain;
            if (err.response?.status === 403 && ownWorkspace) {
              window.location.replace(workspaceUrl(ownWorkspace));
              return;
            }
            if (err.response?.status === 401) {
              notify({
                type: "error",
                message: "Your session has expired",
              });
              store.update((s) => {
                s.isLoggedIn = false;
                s.user = null;
              });
              eraseCookieFromAllPaths("AUTH_TOKEN");
            }
            setLoading(false);
            console.error(err);
          });
      } else if (!cookies.AUTH_TOKEN) {
        // Deliberately does not erase anything. `cookies` is react-cookie's
        // cached snapshot, which refreshes only when a cookie is written
        // through that instance — a cookie the *server* sets in a Set-Cookie
        // header never updates it. So this branch runs right after login and
        // activation, believing the token is missing while it is sitting in
        // document.cookie, and an erase here deletes the session that was
        // just established. Erasing a cookie you think is already absent can
        // only be a no-op or a mistake.
        setLoading(false);
      }
    } else {
      setLoading(false);
    }
  }, [authUser, isLoggedIn, cookies, notify]);

  // A signed-in user on the main site is sent to their own workspace.
  // The wrong-*workspace* case never reaches here — the profile call is
  // refused there, so `authUser` stays empty and the 403 handler above
  // does the redirecting. This branch covers only the tenant-less base
  // domain, where the session loads fine but there is no app to show.
  useEffect(() => {
    const ownWorkspace = authUser?.subdomain;
    if (!tenantLoaded || !baseDomain() || !ownWorkspace) {
      return;
    }
    if (tenant?.subdomain !== ownWorkspace) {
      window.location.replace(workspaceUrl(ownWorkspace));
    }
  }, [authUser, tenant, tenantLoaded]);

  useEffect(() => {
    // A workspace that has been activated but not yet configured owns no root
    // administration, so the profile carries an `administration` with no id.
    // Reading `.id` blindly produced a GET /administration/undefined that
    // 404'd and rejected with nobody listening.
    const administrationId = authUser?.administration?.id;
    if (isLoggedIn && !public_state && administrationId) {
      config.fn
        .administration(administrationId)
        .then((res) => {
          store.update((s) => {
            s.administration = [res];
          });
        })
        .catch((err) => {
          console.error("Could not resolve the user's administration", err);
        });
    }
  }, [authUser, isLoggedIn, public_state]);

  // Only treat "/" as a public home (bypassing the auth loader) when the
  // landing page is enabled. When it is disabled, "/" is an authenticated
  // redirect target, so we must keep the loader until the profile fetch
  // resolves — otherwise a valid session is wrongly redirected to /login.
  const showLandingPage = window?.appConfig?.showLandingPage;
  const isHome = location.pathname === "/" && showLandingPage;

  const isPublic = config.allowedGlobal
    .map((x) => location.pathname.includes(x))
    .filter((x) => x)?.length;

  return (
    <AbilityContext.Provider value={ability(authUser)}>
      <Layout>
        <Layout.Header />
        <Layout.Body>
          {(loading || formsLoading) && !isHome && !isPublic ? (
            <PageLoader message="Initializing. Please wait.." />
          ) : (
            <RouteList />
          )}
        </Layout.Body>
        <ChatbotWidget />
      </Layout>
    </AbilityContext.Provider>
  );
};

export default App;
