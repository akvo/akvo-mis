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
