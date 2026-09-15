import { Store } from "pullstate";

const defaultUIState = {
  isLoggedIn: false,
  user: null,
  filters: {
    trained: null,
    role: null,
    organisation: null,
    query: null,
    attributeType: null,
    entityType: [],
  },
  language: {
    active: "en",
    langs: { en: "English", de: "German" },
  },
  administration: [],
  selectedAdministration: null,
  loadingMap: false,
  // allForms: full published list fetched at runtime from
  // GET /api/v1/forms/published (replaces the old window.forms global).
  // forms: assignment-filtered, sorted subset rendered by the UI.
  allForms: [],
  forms: [],
  // Populated at runtime from GET /api/v1/levels (tenant-owned).
  levels: [],
  // The workspace this host belongs to, from GET /api/v1/tenant-info.
  // Null on the base domain and on a single-host deployment.
  tenant: null,
  // Whether that answer has arrived. "No workspace" and "not asked yet"
  // are both `null` but demand opposite behaviour: acting on the second
  // sends a workspace's own users to the find-workspace page, and a
  // redirect is not something a later answer can undo.
  tenantLoaded: false,
  // The server said this host serves no workspace at all — a 404 from
  // tenant-info, not merely an absent one. Nothing on such a host can
  // work, because every other call is refused the same way.
  tenantMissing: false,
  selectedForm: null,
  selectedFormData: null,
  loadingForm: false,
  questionGroups: [],
  showAdvancedFilters: false,
  advancedFilters: [],
  dateRange: null,
  administrationLevel: null,
  showContactFormModal: false,
  masterData: {
    administration: {},
    attribute: {},
    entity: {},
  },
  options: {
    entityTypes: [],
  },
  initialValue: [],
  monitoring: null,
};

const store = new Store(defaultUIState);

export default store;
