import React, { Fragment } from "react";
import { appName, apkName } from "../app-name";

const downloadAppText = <Fragment>Download {apkName} App</Fragment>;

// English — the source of truth and per-key fallback for every locale.
// JSX elements and functions live here, which is why these locale files
// are JS, not JSON.
const en = {
  // Sidebar Menu Labels
  menuUsers: "Users",
  menuControlCenter: "Control Center",
  menuManagePlatformUsers: "Manage Platform Users",
  menuValidationTree: "Validation Tree",
  menuManageMobileUsers: "Manage Mobile Users",
  menuManageRoles: "Manage Roles",
  menuMasterData: "Master Data",
  menuAdministrativeList: "Administrative List",
  menuLevels: "Levels",
  menuAttributes: "Attributes",
  menuEntities: "Entities",
  menuEntityTypes: "Entity Types",
  menuOrganisations: "Organisations",
  menuData: "Data",
  menuManageData: "Manage Data",
  menuPendingSubmissions: "Submissions",
  menuApprovals: "Approvals",
  menuDownloads: "Downloads",
  menuManageDraft: "Manage Drafts",
  menuDownloadApps: "Download App",
  menuDocumentation: "Documentation",
  menuProductTour: "Take a tour",
  menuFormBuilder: "Form Builder",
  menuDashboards: "Dashboards",
  menuSettings: "Settings",
  // Dashboards
  dashboardListTitle: "My dashboards",
  dashboardListSubtitle: "Build and manage your custom data dashboards.",
  dashboardNew: "New dashboard",
  dashboardEmptyTitle: "No dashboards yet",
  dashboardEmptyDesc:
    "Create your first custom dashboard to visualise data from your forms.",
  dashboardCreateTitle: "Create a dashboard",
  dashboardCreateHint:
    "Name it, then pick the registration form whose data this dashboard will show.",
  dashboardCreateBtn: "Create dashboard",
  dashboardNameLabel: "Dashboard name",
  dashboardNameRequired: "Please enter a dashboard name",
  dashboardFormLabel: "Data source",
  dashboardFormExtra:
    "This dashboard will show data from this form and its monitoring forms. This cannot be changed later.",
  dashboardFormRequired: "Please select a registration form",
  dashboardFormPlaceholder: "Select a registration form",
  dashboardNoForms: "No published registration forms available.",
  dashboardGoFormBuilder: "Go to Form Builder to create and publish a form.",
  dashboardForbidden: "You no longer have permission to perform this action.",
  dashboardCreated: "Dashboard created",
  dashboardAiApplyWarning:
    "Dashboard created, but some AI widgets could not be applied.",
  dashboardDeleted: "Dashboard deleted",
  dashboardDuplicated: "Dashboard duplicated",
  dashboardDeleteConfirm: "Delete this dashboard?",
  dashboardSlugConflict:
    "A dashboard with a similar name already exists. Please choose a different name.",
  dashboardSaved: "Dashboard saved",
  dashboardPublished: "Dashboard published",
  // Viewer and preview (VIZ-008)
  dashboardViewEmpty: "This dashboard has no widgets yet.",
  dashboardNotFound: "Dashboard is empty",
  dashboardNotFoundHint:
    "This dashboard has not been published yet, or it may have been deleted.",
  dashboardEdit: "Edit dashboard",
  dashboardPreview: "Preview",
  dashboardBackToEditing: "Back to editing",
  dashboardWidgetError: "Couldn't load this widget",
  dashboardWidgetRetry: "Retry",
  dashboardWidgetNoData: "No data available",
  dashboardWidgetNoDataFiltered: "No data found for current filters",
  dashboardWidgetQuestionGone: "This widget's question no longer exists.",
  dashboardWidgetFormGone: "This widget's form no longer exists.",
  // Export (VIZ-023)
  dashboardExport: "Export",
  dashboardExportPng: "PNG image",
  dashboardExportPdf: "PDF document",
  dashboardExportFailed: "Couldn't export this dashboard",
  dashboardFilterPeriod: "Date",
  dashboardFilterAllLocations: "All locations",
  dashboardFilterLocation: "Location",
  dashboardExportFiltered: "Filtered by",
  // Question filters (VIZ-027)
  dashboardFilters: "Filters",
  dashboardFiltersActive: "active",
  dashboardFiltersApply: "Apply",
  dashboardFiltersClear: "Clear all",
  dashboardFiltersHowTo:
    "Tick options to show only the ticked ones. Data without an answer to a filtered question is hidden.",
  dashboardFiltersMatch: "Show data matching",
  dashboardFiltersMatchAll: "All filters",
  dashboardFiltersMatchAny: "Any filter",
  dashboardFiltersRemove: "Remove filter",
  dashboardFiltersMore: "more filters",
  dashboardFiltersTooMany:
    "Too many options ticked: at most {max} in all. Untick some.",
  dashboardFilterQuestions: "Filter questions",
  dashboardFilterChoose: "Choose questions…",
  dashboardFilterScope: "Answers from",
  dashboardFilterSearch: "Search by question, name or group",
  dashboardFilterNoMatch: "No question matches",
  dashboardFilterSelected: "selected",
  dashboardFilterAllForms: "All forms",
  dashboardFilterSuggested: "Used in your widgets",
  dashboardFilterRemove: "Remove",
  dashboardFilterCovers: "Covers:",
  dashboardFilterOnlyOn: "only on",
  dashboardDateQuestion: "Date to filter on",
  dashboardDateSubmission: "Submission date",
  dashboardDateSaved: "Saved date question",
  dashboardFilterGone: "(no longer in the form)",
  // Visibility (VIZ-011)
  dashboardVisibilityTitle: "Public dashboard",
  dashboardVisibilityHintOn:
    "Anyone can open this without signing in, and it is listed in the Dashboard menu for every visitor. Takes effect immediately — no need to save.",
  dashboardVisibilityHintDraft:
    "Publish this dashboard first. Only a published dashboard can be made public.",
  dashboardMakePublicTitle: "Make this dashboard public?",
  dashboardMakePublicBody:
    "Anyone with the link will be able to open this dashboard without signing in, and it will be listed in the Dashboard menu for every visitor to this workspace.",
  dashboardMakePublicRawData:
    "This dashboard includes a table and a map. Public visitors will see individual submission rows and the location of every registered point, not only the totals.",
  dashboardMakePublicOk: "Make public",
  dashboardMadePublic: "Dashboard is now public",
  dashboardMadePrivate: "Dashboard is now private",
  dashboardVisibilityPublic: "Public",
  dashboardVisibilityPrivate: "Private",
  // Embedded dashboards (VIZ-019)
  dashboardKindLabel: "What is this dashboard?",
  dashboardKindWidgets: "Build it here",
  dashboardKindWidgetsHint:
    "Compose charts and tables from your own form data.",
  dashboardKindEmbed: "Embed an external dashboard",
  dashboardKindEmbedHint:
    "Show a report published by Power BI, Tableau, Looker Studio or another tool.",
  dashboardEmbedLabel: "Embed code",
  dashboardEmbedPlaceholder:
    "Paste the embed code from your reporting tool's Share dialog",
  dashboardEmbedRequired: "Please paste the embed code",
  dashboardEmbedHint:
    "Pasted exactly as given, and the size comes from the snippet: give it a width and height to have it shown at that size, centred. A plain frame with neither fills the page instead. If the report requires signing in, visitors will see a login screen even though it looks correct to you.",
  dashboardEmbedBadge: "External",
  dashboardEmbedUnavailable:
    "This dashboard's external content cannot be shown, because embedded dashboards are not available here.",
  preview: "Preview",
  publish: "Publish",
  published: "Published",
  draft: "Draft",
  // Login
  loginLoadingTex: (
    <Fragment>
      Verifying
      <br />
      <small>Please wait..</small>
    </Fragment>
  ),
  // Error messages
  error: "Error",
  errorPageNA: "Oops, this page is not available",
  errorAuth: "You are not authorised to access this page",
  errorUnknown: "An unknown error occurred",
  errorURL: (
    <Fragment>
      Please check the URL again or let us take you back to the {appName}{" "}
      homepage
    </Fragment>
  ),
  errorVerifyCreds: "Please verify your credentials for the requested resource",
  backHome: "Back to Homepage",
  errorDataLoad: "Could not load data",
  errorUserLoad: "Failed to load user data",
  errorFileList: "Could not fetch File list",
  errorSomething: "Something went wrong",
  errorMandatoryFields: "Please answer all the mandatory questions",
  errorFileUpload: "Could not upload file",
  // Header Links
  controlCenter: "Control Center",
  myProfile: "My Profile",
  settings: "System Settings",
  signOut: "Sign Out",
  dashboards: "Dashboards",
  reports: "Reports",
  newsEvents: "News & Events",
  login: "Log in",
  // Reports
  noTemplate: "No templates found",
  chooseTemplate: "Choose a template",
  backBtn: "Back",
  printBtn: "Print",
  //Events
  upcomingEventText: "Upcoming Events",
  eventTitle: "News & Events",
  latestUpdateText: "Latest Updates",
  // Placeholder text
  showEmpty: "Show empty values",
  noInformationAvailable: "No information available",
  // User Management
  manageDataValidationSetup: "Validation Tree",
  manageUsers: "Manage Users",
  addUser: "Add User",
  addNewUser: "Add new user",
  editUser: "Edit User",
  updateUser: "Update User",
  // Organisation Management
  manageOrganisations: "Manage Organizations",
  addOrganisation: "Add Organization",
  editOrganisation: "Edit Organization",
  updateOrganisation: "Update Organization",
  // Validations
  valFirstName: "First name is required",
  valLastName: "Last name is required",
  valEmail: "Please enter a valid Email Address",
  valPhone: "Phone number is required",
  valRole: "Please select a Role",
  valOrganization: "Please select an Organization",
  valOrgName: "Organization name is required",
  valOrgAttributes: "Please select an Attributes",
  // Control Center
  manageDataTitle: "Manage Data",
  manageDataButton: "Manage Data",
  newSubmissionBtn: "Add New Submission",
  finishSubmissionBtn: "Finish and Go to Manage Data",
  finishSubmissionBatchBtn: "Finish and Go to Batch",
  noFormText: "No data",
  noFormSelectedText: "No form selected",
  manageDataText: (
    <Fragment>
      This is where you :
      <ul>
        <li>Add new data using webforms</li>
        <li>Bulk upload data using spreadsheets</li>
        <li>Download data</li>
      </ul>
    </Fragment>
  ),
  formBuilderDescription: (
    <Fragment>
      This is where you can create and manage your Forms. You can :
      <ul>
        <li>Create new forms with various question types</li>
        <li>Modify existing forms with version control</li>
        <li>Delete forms that are no longer needed</li>
      </ul>
    </Fragment>
  ),
  formBuilderCreateTitle: "Create Form",
  formBuilderEditTitle: "Edit Form",
  formBuilderDraftRestored:
    "We recovered your previous work — review it before saving.",
  formBuilderPreviewingBanner: (v) => (
    <Fragment>{`Previewing snapshot v${v} — not the saved state.`}</Fragment>
  ),
  formBuilderBackToSaved: "Back to saved",
  formBuilderSnapshotPending: (v) => (
    <Fragment>
      {`Changes saved as snapshot v${v}. Click Publish to activate.`}
    </Fragment>
  ),
  formBuilderPublishedInfo:
    "Editing a published form creates a new version snapshot. Click Publish to activate it.",
  formBuilderSaveSuccess: "Form saved",
  formBuilderSaveError: "Failed to save form",
  formBuilderCreateSuccess: "Form created successfully",
  formBuilderCreateError: "Failed to create form",
  formBuilderPublishSuccess: "Form published",
  formBuilderPublishError: "Failed to publish form",
  formBuilderUnpublishSuccess: "Form unpublished",
  formBuilderUnpublishError: "Failed to unpublish form",
  formBuilderVersionActivated: (n) => (
    <Fragment>{`Version ${n} is now active. Reloading editor…`}</Fragment>
  ),
  formBuilderActivateError: "Failed to activate version",
  formBuilderPreviewError: "Failed to load version",
  formBuilderVersionHistoryTitle: "Version History",
  formBuilderVersionsButton: "Versions",
  formBuilderRefreshButton: "Refresh",
  formBuilderVersionHistoryEmpty: "No published versions yet",
  formBuilderNameCol: "Name",
  formBuilderTypeCol: "Type",
  formBuilderStatusCol: "Status",
  formBuilderLastUpdatedCol: "Last Updated",
  formBuilderVersionCol: "Version",
  formBuilderPublishedAtCol: "Published At",
  formBuilderPublishedByCol: "Published By",
  formBuilderActionsCol: "Actions",
  formBuilderActiveTag: "Active",
  formBuilderPreviewButton: "Preview",
  formBuilderActivateVersionTitle: (v) => (
    <Fragment>{`Activate version ${v}?`}</Fragment>
  ),
  formBuilderActivateVersionDesc:
    "This will replace the current active schema. The editor will reload.",
  formBuilderActivateButton: "Activate",
  formBuilderSetActiveButton: "Set Active",
  formBuilderPublishButton: "Publish",
  formBuilderUnpublishTitle: "Unpublish this form?",
  formBuilderUnpublishDesc:
    "The form will no longer be available for data collection.",
  formBuilderUnpublishButton: "Unpublish",
  formBuilderStatusPublished: "Published",
  formBuilderStatusDraft: "Draft",
  formBuilderResetDraft: "Load from server",
  formBuilderMonitoringFor: (name) => `Creating monitoring form for: ${name}`,
  formBuilderParentFormError:
    "Parent form not found or not published. Cannot create monitoring form.",
  formBuilderCreateMonitoringButton: "Create Monitoring Form",
  formBuilderCreateButton: "Create New Form",
  formBuilderRegistrationType: "Registration",
  formBuilderMonitoringType: "Monitoring",
  formBuilderTabActive: "Active",
  formBuilderTabArchived: "Archived",
  formBuilderSearchPlaceholder: "Search by name",
  formBuilderFilterStatusAll: "All Statuses",
  formBuilderFilterTypeAll: "All Types",
  formBuilderArchivedAtCol: "Archived",
  formBuilderDuplicateButton: "Duplicate",
  formBuilderArchiveButton: "Archive",
  formBuilderRestoreButton: "Restore",
  formBuilderDeleteButton: "Delete permanently",
  formBuilderPublishConfirmTitle: "Publish this form?",
  formBuilderPublishConfirmDesc:
    "It will become available for data collection.",
  formBuilderArchiveConfirmTitle: "Archive this form?",
  formBuilderArchiveConfirmDesc: (count) =>
    count > 0
      ? `It will be removed from data collection (web and mobile) and ` +
        `moved to the Archived tab. This form has ${count} ` +
        `submission(s) — they are preserved. You can restore it later.`
      : `It will be removed from data collection (web and mobile) and ` +
        `moved to the Archived tab. You can restore it later.`,
  formBuilderRestoreConfirmTitle: "Restore this form?",
  formBuilderRestoreConfirmDesc:
    "It will return as a draft; re-publish it to resume data collection.",
  formBuilderDeleteConfirmTitle: "Permanently delete this form?",
  formBuilderDeleteConfirmDesc: "This action cannot be undone.",
  formBuilderDeleteDisabledTooltip:
    "Forms with submissions can't be deleted — keep it archived or restore it.",
  formBuilderArchiveSuccess: "Form archived",
  formBuilderArchiveError: "Failed to archive form",
  formBuilderRestoreSuccess: "Form restored",
  formBuilderRestoreError: "Failed to restore form",
  formBuilderDuplicateSuccess: "Form duplicated",
  formBuilderDuplicateError: "Failed to duplicate form",
  formBuilderDeleteSuccess: "Form permanently deleted",
  formBuilderDeleteError: "Failed to delete form",
  formBuilderStatusArchived: "Archived",
  formBuilderEmptyText: "No forms found",
  // FB-018 Form Library
  formLibraryTitle: "Form Library",
  formLibraryDescription:
    "Browse curated, ready-to-use form templates and start a new form from one with a single click.",
  formLibrarySearchPlaceholder: "Search templates",
  formLibraryAllCategories: "All categories",
  formLibraryUncategorized: "Uncategorized",
  formLibraryUsedCount: "Used",
  formLibraryMonitoringLabel: "monitoring form(s)",
  formLibraryPreviewButton: "Preview",
  formLibraryUseButton: "Use this form",
  formLibraryViewOnly: "View only",
  formLibraryEmptyText: "No templates available",
  formLibraryPreviewTitle: "Template preview",
  formLibraryRegistrationTab: "Registration",
  formLibraryMonitoringTab: "Monitoring",
  formLibraryUseSuccess: "Template copied to your workspace as a new draft.",
  formLibraryUseError: "Failed to use this template",
  formBuilderExportButton: "Export",
  formBuilderExportError: "Failed to export form",
  formBuilderExportXlsformButton: "Export XLSForm",
  formBuilderExportXlsformError: "Failed to export XLSForm",
  formBuilderExportXlsformWarningTitle: "XLSForm Export Warnings",
  formBuilderExportCascadeCsvButton: "Export Cascade CSV",
  formBuilderExportCascadeCsvError: "Failed to export Cascade CSV",
  formBuilderImportButton: "Import Form",
  formBuilderDataOnboardingButton: "Onboard spreadsheet",
  dataOnboardingUploadHint:
    "Click or drag one CSV or xlsx file here (up to 10 MB and 50,000 rows)",
  dataOnboardingDrafting:
    "Drafting the Proposal. A large file can take a few minutes.",
  dataOnboardingFailed: "The Proposal could not be drafted.",
  dataOnboardingUnits: "Administration units to add",
  dataOnboardingNoUnits: "No units to add",
  dataOnboardingUnitsOutside:
    "These units are outside your administration area. Apply will not add them or load their rows:",
  dataOnboardingParentForm: "Registration form",
  dataOnboardingForms: "Forms",
  dataOnboardingMapping: "Column to question",
  dataOnboardingKeyColumns: "Key columns",
  dataOnboardingValueMaps: "Value maps",
  dataOnboardingDropped: "Columns not loaded",
  dataOnboardingNotes: "Notes",
  dataOnboardingQuestion: "Question",
  dataOnboardingName: "Name",
  dataOnboardingType: "Type",
  dataOnboardingRequired: "Required",
  dataOnboardingOptions: "Options",
  dataOnboardingColumn: "Column",
  dataOnboardingRaw: "Value in the file",
  dataOnboardingReason: "Reason",
  dataOnboardingApply: "Apply",
  dataOnboardingApplying:
    "Applying the Proposal: adding units, creating forms and loading records.",
  dataOnboardingReport: "Onboarding Report",
  dataOnboardingLoaded: "Records loaded",
  dataOnboardingIssues: "Skipped rows and dropped answers",
  dataOnboardingNoIssues: "Every row loaded.",
  dataOnboardingSheet: "Sheet",
  dataOnboardingRow: "Row",
  dataOnboardingSkipped: "Row skipped",
  dataOnboardingDroppedAnswer: "Answer dropped",
  dataOnboardingBlocked: "Blocked",
  dataOnboardingBlockedNote:
    "Blocked forms are not applied. Apply loads the other forms.",
  dataOnboardingNotApplied: "Forms not applied",
  dataOnboardingApplyFailed: "The Proposal could not be applied.",
  dataOnboardingDownloadReport: "Download report",
  dataOnboardingDownloadFailed: "The report could not be downloaded.",
  dataOnboardingHistory: "Data Onboardings",
  dataOnboardingFile: "File",
  dataOnboardingStatus: "Status",
  dataOnboardingCreatedBy: "Started by",
  dataOnboardingCreated: "Started",
  dataOnboardingUpdated: "Last updated",
  dataOnboardingDropColumn: "Drop",
  dataOnboardingKeepColumn: "Keep",
  dataOnboardingReviseHint:
    "Describe any other change, for example: treat Status as a yes/no question.",
  dataOnboardingRevise: "Revise",
  dataOnboardingRevisionFailed: "The Proposal could not be revised.",
  dataOnboardingUseExisting: "Use the existing unit",
  dataOnboardingAddNew: "Add as a new unit",
  dataOnboardingChooseParent: "Choose the parent",
  dataOnboardingLocationColumns: "Location columns, top level first",
  dataOnboardingFirstLevel: "Level of the first column",
  dataOnboardingLocationColumn: "Location column",
  dataOnboardingDropForm: "Drop this form",
  formBuilderImportModalTitle: "Import Form",
  formBuilderImportFormatLabel: "Format",
  formBuilderImportFormatJson: "JSON (Native)",
  formBuilderImportFormatXlsform: "XLSForm (.xlsx)",
  formBuilderImportDraggerText: "Click or drag a form file here",
  formBuilderImportDraggerHint: (mb) =>
    `Only .json form export files, up to ${mb} MB`,
  formBuilderImportDraggerHintXlsform: (mb) =>
    `Only .xlsx or .xls files, up to ${mb} MB`,
  formBuilderImportFileTooLarge: (mb) => `File exceeds the ${mb} MB limit`,
  formBuilderImportInvalidFile: "Only .json files are supported",
  formBuilderImportInvalidFileXlsform: "Only .xlsx or .xls files are supported",
  formBuilderImportPreflightError: "Failed to validate the file",
  formBuilderImportErrorsTitle: "Validation errors",
  formBuilderImportWarningsTitle: "Warnings",
  formBuilderImportFormLabel: "Form",
  formBuilderImportQuestionsLabel: "Questions",
  formBuilderImportGroupsLabel: "Groups",
  formBuilderImportFormTypeLabel: "Form Type",
  formBuilderImportFormTypeRegistration: "Registration",
  formBuilderImportFormTypeMonitoring: "Monitoring",
  formBuilderImportFormTypeRequired: "Please select a form type",
  formBuilderImportSkippedCount: (count) =>
    `${count} unsupported row(s) will be skipped`,
  formBuilderImportXlsformNoticeTitle: "This import needs a quick review",
  formBuilderImportXlsformNoticeDesc: (
    <div style={{ textAlign: "left", fontSize: 13, lineHeight: 1.5 }}>
      <p style={{ margin: "4px 0 8px 0", textAlign: "left" }}>
        Your XLSForm was imported successfully, but Kobo and Akvo MIS don&apos;t
        work identically and some form logic may need manual adjustment to fully
        match your original. Please review the warnings below and test the form
        before publishing.
      </p>
      <p
        style={{
          margin: "8px 0 4px 0",
          fontWeight: 600,
          textAlign: "left",
        }}
      >
        Common things to check:
      </p>
      <ul
        style={{
          margin: "0 0 8px 0",
          paddingLeft: 18,
          textAlign: "left",
          listStyleType: "disc",
        }}
      >
        <li style={{ marginBottom: 4 }}>
          Calculated fields – formulas may need to be re-verified
        </li>
        <li style={{ marginBottom: 4 }}>
          Dynamic repeat counts – repeat groups driven by a variable may need
          manual setup
        </li>
        <li style={{ marginBottom: 4 }}>
          Group relevance / skip logic – conditional group visibility should be
          double-checked
        </li>
        <li style={{ marginBottom: 4 }}>
          &quot;Other&quot; follow-up questions – these aren&apos;t
          auto-converted; add them manually if needed
        </li>
      </ul>
      <p style={{ margin: "8px 0 0 0", textAlign: "left" }}>
        We recommend previewing the full form and testing a submission before it
        goes live.
      </p>
    </div>
  ),
  formBuilderImportUpdateTitle: (name) => `Update existing form "${name}"?`,
  formBuilderImportUpdateDesc: (count) =>
    `A form with the same ID already exists in this environment` +
    (count > 0 ? ` and has ${count} submission(s)` : "") +
    `. Updating changes its structure in place; submissions are preserved.`,
  formBuilderImportNameMismatchWarning:
    "The name in the file differs from the existing form's name — " +
    "make sure you are updating the right form.",
  formBuilderImportModeUpdate: "Update existing form",
  formBuilderImportModeCopy: "Import as new copy",
  formBuilderImportParentLabel: "Parent registration form",
  formBuilderImportParentPlaceholder: "Select a registration form",
  formBuilderImportParentRequired:
    "A monitoring form requires a parent registration form.",
  formBuilderImportConfirmButton: "Import",
  formBuilderImportInProgress: "Importing form…",
  formBuilderImportSuccess: "Form imported",
  formBuilderImportFailed: "Import failed",
  formBuilderImportOpenEditor: "Open in editor",
  formBuilderImportRetryButton: "Try another file",
  formBuilderImportCloseButton: "Close",
  dataUploadTitle: "Data Upload",
  AdministrationDataUpload: "Administration Data Upload",
  dataUploadText: (
    <Fragment>
      This is where you :
      <ul>
        <li>Download upload template</li>
        <li>Bulk upload new data</li>
        <li>Bulk update existing data</li>
      </ul>
    </Fragment>
  ),
  dataAdministrationUploadText: (
    <Fragment>
      This is where you :
      <ul>
        <li>Bulk upload administration data</li>
      </ul>
    </Fragment>
  ),
  AdministrationDataDownload: "Administration Data Download",
  AdministrationDownloadPageHint:
    "Uncheck Prefilled if you only want an upload template",
  dataAdministrationDownloadText: (
    <Fragment>
      This is where you :
      <ul>
        <li>Download administration data</li>
      </ul>
    </Fragment>
  ),
  EntitiesDataUpload: "Entities Data Upload",
  dataEntitiesUploadText: (
    <Fragment>
      This is where you :
      <ul>
        <li>Bulk upload entities data</li>
      </ul>
    </Fragment>
  ),
  EntitiesDataDownload: "Entities Data Download",
  EntitiesDownloadPageHint:
    "Uncheck Prefilled if you only want an upload template",
  dataEntitiesDownloadText: (
    <Fragment>
      This is where you :
      <ul>
        <li>Download entities data</li>
      </ul>
    </Fragment>
  ),
  manageUserText: (
    <Fragment>
      This is where you manage users based on their roles , regions and
      questionnaire access . You can :
      <ul>
        <li>Add new user</li>
        <li>Modify existing user</li>
        <li>Delete existing user</li>
      </ul>
    </Fragment>
  ),
  manageAttributeText: (
    <Fragment>
      This is where you manage attributes based on their fields. You can :
      <ul>
        <li>Add new attribute</li>
        <li>Modify existing attribute</li>
        <li>Delete existing attribute</li>
      </ul>
    </Fragment>
  ),
  manageEntitiesText: (
    <Fragment>
      This is where you manage entitys based on their fields. You can :
      <ul>
        <li>Add new entity</li>
        <li>Modify existing entity</li>
        <li>Delete existing entity</li>
      </ul>
    </Fragment>
  ),
  manageEntityTypesText: (
    <Fragment>
      This is where you manage entity types based on their fields. You can :
      <ul>
        <li>Add new entity type</li>
        <li>Modify existing entity type</li>
        <li>Delete existing entity type</li>
      </ul>
    </Fragment>
  ),
  manageAdministrativeList: "Manage Administrative List",
  editAdministration: "Edit Administration",
  addAdministration: "Add Administration",
  manageAttributes: "Manage Attributes",
  editAttributes: "Edit Attribute",
  addAttributes: "Add Attribute",
  manageLevels: "Manage Levels",
  manageLevelText:
    "Define the tiers of your administrative hierarchy, from the top " +
    "level down. Tiers can be renamed at any time, but they can only " +
    "be added or removed while no administrative units exist below " +
    "your top level.",
  addLevel: "Add Level",
  levelFrozenHint:
    "Levels can no longer be added or removed because administrative " +
    "units already exist. Renaming is still available.",
  levelDeleteTitle: "Remove the deepest level?",
  manageEntities: "Manage Entities",
  manageEntityTypes: "Manage Entity Types",
  entityTabTitle: "Entities",
  exportEntityError: "Unable to export entities",
  administrationLabel: "Administration",
  codeLabel: "Code",
  nameLabel: "Name",
  levelLabel: "Level",
  roleLabel: "Role",
  profileLabel: "Profile",
  profileDes:
    "This page shows your current user setup. It also shows the most important activities for your current user setup",
  ccDescriptionPanel:
    "Instant access to all the administration pages and overview panels for data approvals.",
  // Settings
  orgTabTitle: "Organisations",
  orgPanelTitle: "Manage Organization",
  orgPanelButton: "Manage Organization",
  orgPanelText: (
    <Fragment>
      This is where you :
      <ul>
        <li>Add new organization</li>
        <li>Modify existing organization</li>
        <li>Delete existing organization</li>
      </ul>
    </Fragment>
  ),
  admPanelText: (
    <Fragment>
      This is where you :
      <ul>
        <li>Add new administration</li>
        <li>Modify existing administration</li>
        <li>Delete existing administration</li>
        <li>Bulk upload administration</li>
      </ul>
    </Fragment>
  ),
  settingsDescriptionPanel:
    "This page allows Super Admin to maintain system critical master lists.",
  // Approvals
  approvalsTab1: "My Pending",
  approvalsTab2: "Subordinates Approvals",
  approvalsTab3: "Approved",
  notAssigned: "Not assigned",
  questionnaireText: "Questionnaire",
  approversDescription: (
    <Fragment>
      This is where you can see the approvers for each submitted form across
      different administrative areas:
    </Fragment>
  ),
  // Misc
  informUser: "Inform User for Changes",
  // Data Uploads
  batchSelectedDatasets: "Batch Selected Datasets",
  uploadsTab1: "Pending Submission",
  uploadsTab2: "Pending Approval",
  uploadsTab3: "Approved",
  batchName: "Batch Name",
  submissionComment: "Submission comment",
  sendNewRequest: "Notify Approver",
  createNewBatch: "Create a new batch",
  batchHintText: "You are about to create a Batch CSV File",
  batchHintDesc:
    "The operation of merging datasets cannot be undone, and will Create a new batch that will require approval from you admin",
  // Upload Detail
  uploadTab1: "Data Summary",
  uploadTab2: "Raw Data",
  notesFeedback: "Notes & Feedback",
  // Export Data
  generating: "Generating",
  failed: "Failed",
  download: "Download",
  uploadDataLabel: "Upload your data",
  uploadMasterDataLabel: "Upload your data",
  uploadAnotherFileLabel: "Upload Another File",
  backToCenterLabel: "Back to Control Center",
  backToAdmLabel: "Back to Administrative List",
  uploadThankyouText: (
    <Fragment>
      Thank you for uploading the data file. Do note that the data will be
      validated by the system . You will be notified via email if the data fails
      the validation tests . There will also be an attachment of the validation
      errors that needs to be corrected. If there are no validation errors ,
      then the data will be forwarded for verification, approval, and
      certification
    </Fragment>
  ),
  exportPanelText: (
    <Fragment>
      <p>
        This page shows your list of data export requests.
        <br />
        For exports which are already generated, please click on the Download
        button to download the data.
      </p>
    </Fragment>
  ),
  // Webform
  formDescription: (
    <p>
      Please fill up the webform below with relevant responses. You will need to
      answer all mandatory questions before you can submit.
      <br />
      Once you have sumitted a webform, please do not forget to add it as part
      of a batch and send it for approval.
    </p>
  ),
  // Draft Webform
  draftFormDescription: (
    <p>
      Please fill up the webform below with relevant responses. You can save
      your responses and continue later or if you have completed the form then
      you can submit it.
    </p>
  ),
  formSuccessTitle: "Thank you for the submission",
  administrationUploadSuccessTitle:
    "Administration Data has been Successfully Uploaded",
  administrationUploadFailedTitle: "Your file could not be imported",
  administrationUploadFailedHint:
    "Nothing was changed. We have emailed you a file listing the rows that need fixing.",
  uploadNotReadyHint:
    "Define your administrative levels first: name the top level and add at least one level below it. You can do that under Master Data → Levels.",
  entitiesUploadSuccessTitle: "Entities Data has been Successfully Uploaded",
  formSuccessSubTitle:
    "Do note that this data has NOT been sent for approval. If you are ready to send the submissions for approval, please create a batch and send to the approver",
  formSuccessSubTitleForAdmin:
    "Do note that the data submitted by SUPER ADMIN role will not go through the approval flow and recorded as approved data",
  fetchingForm: "Fetching form..",
  // Forgot Password
  forgotTitle: "Reset your password",
  forgotDesc:
    "Enter the email associated with your account and we&apos;ll Send an email with instructions to reset your password",
  instructionsMailed: "Instructions mailed successfully",
  sendInstructions: "Send Instructions",
  // Reset Password
  welcomeShort: (
    <Fragment>
      Welcome to the <b>{appName}</b> platform
    </Fragment>
  ),
  resetHint: (
    <Fragment>
      Please set your password for the platform.
      <br />
      Your password must include:
    </Fragment>
  ),
  invalidInviteTitle: "Invalid Invite Code",
  invalidInviteDesc:
    "Lorem, ipsum dolor sit amet consectetur adipisicing elit. Autem provident voluptatum cum numquam, quidem vitae, qui quam beatae exercitationem ullam perferendis! Nobis in aut fuga voluptate harum, tempore distinctio optio.",
  // Register
  passwordRule1: "Lowercase Character",
  passwordRule2: "Numbers",
  passwordRule3: "Special Character ( -._!`'#%&,:;<>=@{}~$()*+/?[]^|] )",
  passwordRule4: "Uppercase Character",
  passwordRule5: "No White Space",
  passwordRule6: "Minimum 8 Characters",
  passwordUpdateSuccess: "Password updated successfully",
  passwordRequired: "Please input your Password!",
  passwordCriteriaError: "False Password Criteria",
  passwordMatchError: "The two passwords that you entered do not match!",
  // Log in
  loginTitle: "Welcome back",
  loginAccountDetails: "Please enter your account details",
  loginTroublePrefix: "Having trouble accessing the platform? Please",
  loginContactLink: "contact",
  loginEmailPlaceholder: "Email",
  loginPasswordLabel: "Password",
  loginPasswordPlaceholder: "Password",
  recoverPassword: "Recover Password",
  createAccount: "Create an account",
  loginNotActivated: "This account has not been activated yet",
  loginResendActivation: "Resend the activation email",
  // Activate / email verification
  activateVerifiedTitle: "Email verified",
  activateVerifiedDesc:
    "Your account is active. One quick step left — tell us about your project.",
  activateContinueSetup: "Continue to setup →",
  activateVerifying: "Verifying your email…",
  activateCheckInboxTitle: "Check your inbox",
  activateCheckInboxDesc:
    "If that account still needs activating, a fresh link is on its way.",
  activateErrorTitle: "We could not check your link",
  activateErrorDesc:
    "Something went wrong on the way to the server. Your link is probably fine — try again in a moment.",
  activateTryAgain: "Try again",
  activateExpiredTitle: "This link has expired",
  activateExpiredDesc:
    "Activation links are valid for 7 days. Request a fresh one and we'll email it right away.",
  activateEmailPlaceholder: "you@organisation.org",
  backToLogin: "Back to login",
  couldNotSendEmail: "Could not send the email",
  // Configure / project setup
  configureStep1: "Sign up",
  configureStep2: "Verify email",
  configureStep3: "Configure project",
  configureStep4: "Dashboard",
  configureTitle: "Set up your project",
  configureSubtitle:
    "This names your administrative hierarchy. You can add deeper tiers afterwards; these two top-level names are set once here.",
  configureFirstName: "First name",
  configureFirstNamePlaceholder: "Jane",
  configureLastName: "Last name",
  configureLastNamePlaceholder: "Doe",
  configureRequired: "Required",
  configureTopLevelName: "Top level name",
  configureTopLevelExtra:
    "The label for your highest administrative tier — e.g. Country, National, or Region. Not a place, a tier.",
  configureTopLevelRequired: "Give your top tier a name.",
  configureTopLevelPlaceholder: "Country",
  configureTopUnitName: "Top unit name",
  configureTopUnitExtra:
    "Your single top unit at that tier — e.g. Kenya. Everything you upload later sits under it.",
  configureTopUnitRequired: "Name your top unit.",
  configureTopUnitPlaceholder: "Kenya",
  configureLogoLabel: "Workspace logo",
  configureLogoExtra:
    "Optional. PNG, JPG, or JPEG up to 2MB. Displayed in the top navigation and login page.",
  configureUploadLogo: "Upload logo",
  configureLogoUploadError: "Failed to upload logo",
  configurePreview: "Preview — this is the hierarchy you're creating:",
  configureLevel0Tag: "Level 0",
  configureTopUnitHint: "└ top unit",
  configureFinish: "Finish setup",
  configureSaveError: "Could not save your workspace",
  configureDoneTitle: "You're all set",
  configureWelcome: "Welcome",
  configureReadyWith: "Your workspace is ready with",
  configureAtTop: "at the top. Next, add the tiers beneath it.",
  configureContinue: "Continue to Level management →",
  contactAdmin: "Please contact the administrator",
  formAssignmentError:
    "You don't have any form assignment, please contact the administrator",
  usernameRequired: "Please input your Username!",
  // Approvals Panel
  panelApprovalsDesc: (
    <Fragment>
      This is where you :
      <ul>
        <li>View pending data approvals awaiting your approval </li>
        <li>View pending approvals by your subordinate approvers</li>
        <li>Assign subordinate approvers</li>
      </ul>
    </Fragment>
  ),
  // Upload Data
  dataExportSuccess: "Data downloaded successfully",
  dataExportFail: "Data download failed",
  fileUploadSuccess: "File uploaded successfully",
  fileUploadFail: "Could not upload file",
  templateFetchFail: "Could not fetch template",
  updateExisting: "Update Existing Data",
  templateDownloadHint:
    "If you do not already have a template, please download",
  templateDownloadAdministrationHint:
    "If you do not already have a template, please ",
  templateDownloadEntityHint:
    "If you do not already have an entity template, please ",
  downloadHere: "download here",
  uploading: "Uploading..",
  dropFile: "Drop your file here",
  selectForm: "Please select a form",
  browseComputer: "Browse your computer",
  usersLoadFail: "Could not load users",
  userDeleteFail: "Could not delete user",
  deleteUserHint: "Deleting this user will not delete the data association(s)",
  deleteUserTitle: "You are about to delete the user",
  deleteUserDesc: (
    <Fragment>
      The User will no longer be able to access the {appName} platform as an
      Enumrator/Admin etc
    </Fragment>
  ),
  userAssociations: "This user has following data association(s)",
  organisationsLoadFail: "Could not load organizations",
  organisationDeleteFail: "Could not delete organization",
  deleteOrganisationDesc: ({ count = 0 }) => (
    <span>
      There are <b>{count} Users</b> associated with this organisation. Please
      reassign or delete these user(s) before deleting the organisation to
      prevent unexpected results
    </span>
  ),
  deleteOrganisationTitle: "You are about to delete the organization",
  // Tour
  prev: "Prev",
  next: "Next",
  finish: "Finish",
  tourControlCenter: "Lorem ipsum dolor sit, amet consectetur adipisicing elit",
  tourDataUploads: "Velit amet omnis dolores. Ad eveniet ex beatae dolorum",
  tourApprovals: "Placeat impedit iure quaerat neque sit quasi",
  tourApprovers: "Magni provident aliquam harum cupiditate iste",
  tourManageData: "Lorem ipsum dolor sit, amet consectetur adipisicing elit",
  tourExports: "Velit amet omnis dolores. Ad eveniet ex beatae dolorum",
  tourUserManagement: "Magni provident aliquam harum cupiditate iste",
  tourDataUploadsPanel:
    "Velit amet omnis dolores. Ad eveniet ex beatae dolorum",
  //downloads
  downloadTitle: "Downloads",
  // Add user modal notification
  existingApproverTitle: "There are existing approvers for:",
  existingApproverDescription:
    "Please update the setup in manage validation tree or remove these forms for the current user",
  bulkUploadNoApproverMessage:
    "Can't upload data, because there's no approver yet.",
  batchNoApproverMessage:
    "Can't create batch data, because there's no approver yet.",
  mobilePanelTitle: "Mobile Data Collectors",
  mobilePanelText: (
    <Fragment>
      This is where you :
      <ul>
        <li>Add new mobile data collector</li>
        <li>Modify existing mobile data collector</li>
        <li>Delete existing mobile data collector</li>
      </ul>
    </Fragment>
  ),
  mobileEditText: "Edit Assignment",
  mobileAddText: "Add Assignment",
  mobileButtonSave: "Save",
  mobileButtonAdd: "Add new data collector",
  mobileLabelName: "Name",
  mobileLabelAdm: "Administrations",
  mobileLabelForms: "Forms",
  mobileNameRequired: "Name is required",
  mobileLevelRequired: "Level is required",
  mobileAdmRequired: "Administration is required: one or multiple",
  mobileFormsRequired: "Form is required: one or multiple",
  mobileSelectForms: "Select forms...",
  mobilePanelAddDesc: (
    <Fragment>
      This page allows you to add mobile data collectors to the {appName}{" "}
      platform.
    </Fragment>
  ),
  mobilePanelEditDesc: (
    <Fragment>
      This page allows you to edit mobile data collectors to the {appName}{" "}
      platform.
    </Fragment>
  ),
  mobileErrDelete: "Unable to delete assingment",
  mobileConfirmDelete: "Are you sure you want to delete this assignment?",
  mobileSuccessAdded: "Mobile assignment added",
  mobileSuccessUpdated: "Mobile assignment update",
  actionColumn: "Action",
  formColumn: "Form",
  nameField: "Name",
  codeField: "Code",
  levelField: "Level",
  administrationField: "Administration",
  nameFieldRequired: "Name is required",
  codeFieldRequired: "Code is required",
  levelFieldRequired: "Level is required",
  admFieldRequired: "Administration is required",
  editButton: "Edit",
  saveButton: "Save",
  saveEditButton: "Save Edits",
  bulkUploadButton: "Bulk Upload",
  addNewButton: "Add New",
  cancelButton: "Cancel",
  deleteText: "Delete",
  errDeleteCascadeText1:
    "It is associated with other resources or has cascade restrictions.",
  errDeleteCascadeText2:
    "Please review and resolve dependencies before attempting to delete.",
  addEntity: "Add New",
  editEntity: "Edit Entity",
  confirmDeleteEntity: "Are you sure you want to delete this entity?",
  errDeleteEntityTitle: "Unable to delete the entity",
  successAddedEntity: "Entity added",
  successUpdatedEntity: "Entity updated",
  successDeletedEntity: "Entity deleted",
  entityText: "Entity",
  addEntityData: "Add New",
  editEntityData: "Edit data",
  selectEntity: "Select entity...",
  entityIsRequired: "Entity is required",
  selectLevel: "Select level...",
  selectType: "Select type...",
  selectText: "Select...",
  selectOne: "Select one...",
  confirmDeleteEntityData: "Are you sure you want to delete this data?",
  errDeleteEntityDataTitle: "Unable to delete the data",
  errSaveEntityDataTitle: "Unable to save the data",
  successEntityDataAdded: "Entity data added",
  successEntityDataUpdated: "Entity data updated",
  successEntityDataDeleted: "Entity data deleted",
  entityTypes: "Entity Types",
  entityType: "Entity Type",
  searchEntityType: "Enter name...",
  searchEntity: "Enter name...",
  addOrgDesc: (
    <Fragment>
      This page allows you to add organisations to the {appName} platform.
    </Fragment>
  ),
  addEntityDesc: (
    <Fragment>
      This page allows you to add entity to the {appName} platform.
    </Fragment>
  ),
  addEntityTypeDesc: (
    <Fragment>
      This page allows you to add entity type to the {appName} platform.
    </Fragment>
  ),
  addAttributeDesc: (
    <Fragment>
      This page allows you to add attribute to the {appName} platform.
    </Fragment>
  ),
  addAdmDesc: (
    <Fragment>
      This page allows you to add administration to the {appName} platform.
    </Fragment>
  ),
  editOrgDesc: (
    <Fragment>
      This page allows you to edit organisations to the {appName} platform.
    </Fragment>
  ),
  editEntityDesc: (
    <Fragment>
      This page allows you to edit entity to the {appName} platform.
    </Fragment>
  ),
  editEntityTypeDesc: (
    <Fragment>
      This page allows you to edit entity type to the {appName} platform.
    </Fragment>
  ),
  editAttributeDesc: (
    <Fragment>
      This page allows you to edit attribute to the {appName} platform.
    </Fragment>
  ),
  editAdmDesc: (
    <Fragment>
      This page allows you to edit administration to the {appName} platform.
    </Fragment>
  ),
  successAddedOrg: "Organisation added",
  successUpdatedOrg: "Organisation updated",
  errAddOrg: "Organization could not be added",
  errUpdateOrg: "Organization could not be updated",
  admSuccessDeleted: "Administration deleted",
  admSuccessUpdated: "Administration updated",
  admSuccessAdded: "Administration added",
  admErrDeleteTitle: "Unable to delete the administration",
  admErrSaveTitle: "Unable to save the administration",
  admConfirmDelete: "Are you sure you want to delete this administration?",
  admParent: "Administration Parent",
  admName: "Administration Name",
  admLevel: "Administration Level",
  admNameRequired: "Administration name is required",
  admTabTitle: "Administrative List",
  attrSuccessDeleted: "Attribute deleted",
  attrSuccessUpdated: "Attribute updated",
  attrSuccessAdded: "Attribute added",
  attrErrDeleteTitle: "Unable to delete the attribute",
  attrConfirmDelete: "Are you sure you want to delete this attribute?",
  attrType: "Attribute type",
  attrName: "Attribute name",
  attrTypeRequired: "Attribute type is required",
  attrNameRequired: "Attribute name is required",
  attrTabTitle: "Attributes",
  addOptionButton: "Add option",
  optionsField: "Options",
  searchNameOrCode: "Enter name or code...",
  userFirstName: "First name",
  userLastName: "Last name",
  userEmail: "Email Address",
  userPhoneNumber: "Phone Number",
  userOrganisation: "Organization",
  loadingText: "Loading...",
  questionnairesLabel: "Questionnaires",
  lastLoginLabel: "Last login",
  submissionsText: "Submissions",
  notifyError: "An error occured",
  successDataUpdated: "Data updated",
  loadMoreLable: "Load More",
  endOfListLabel: "End of List",
  searchPlaceholder: "Search...",
  bulkUploadAttr: "Attributes",
  bulkUploadAttrPlaceholder: "Select Attributes...",
  bulkUploadCheckboxPrefilled: "Prefilled administrative list",
  errorEntityData: (entity) =>
    `The selected administration doesn't have ${entity} entities`,
  errorEntityNotExists: (entity) =>
    `Unfortunately, ${entity} entities are not yet available. Please get in touch with Admin to add it`,
  errorMonitoringRequiresRegistration: (monitoring, registration) =>
    `"${monitoring}" requires its parent registration form "${registration}" to be selected`,
  questionCol: "Question",
  responseCol: "Response",
  lastResponseCol: "Last Response",
  backManageData: "Back to Manage Data",
  monitoringDataTitle: "Monitoring data",
  monitoringDataDescription: (
    <Fragment>
      This is where you :
      <ul>
        <li>
          Get the list of forms that were collected for this datapoint (new and
          update)
        </li>
        <li>Edit monitoring data</li>
      </ul>
    </Fragment>
  ),
  updateDataButton: "Update data",
  updateDataError: "Unable to update data",
  requiredError: "{{field}} is required",
  helloText: "Hello",
  // User Management
  addUserDescription: (
    <Fragment>
      This page allows you to add users to the {appName} platform. You will only
      be able to add users for regions under your jurisdisction.
      <br />
      Once you have added the user, the user will be notified by email to set
      their password and access the platform
    </Fragment>
  ),
  // Home Page
  manageDataTab1: "Registration Data",
  manageDataTab2: "Monitoring Data",
  manageDataTab3: "Monitoring Overview",
  selectFormPlaceholder: "Select Form",
  selectIndicatorPlaceholder: "Select Indicator",
  lastUpdatedCol: "Last Updated",
  recentActivityCol: "Recent Activity",
  initialRegistration: "Initial Registration",
  nameCol: "Name",
  channelCol: "Channel",
  userCol: "User",
  regionCol: "Region",
  mobileAppText: "Mobile App",
  webformText: "Webform",
  registrationView: "Registration",
  selectViewMode: "Select View",
  submissionDateCol: "Submission Date",
  datapointCol: "Datapoint",
  viewFullContext: "View Full Context",
  manageRoles: "Manage Roles",
  manageRoleText: (
    <Fragment>
      This is where you manage roles based on their fields. You can :
      <ul>
        <li>Add new role</li>
        <li>Modify existing role</li>
        <li>Delete existing role</li>
      </ul>
    </Fragment>
  ),
  manageRolesTitle: "Manage Roles",
  addRole: "Add Role",
  editRole: "Edit Role",
  roleName: "Role Name",
  roleNameRequired: "Role name is required",
  roleDescription: "Role Description",
  roleAdmLevel: "Administration Level",
  roleAdmLevelRequired: "Administration level is required",
  roleAdmLevelPlaceholder: "Select administration level...",
  roleAccess: "Role Access",
  roleAccessRequired: "Role access is required",
  roleTotalUsers: "Total Users",
  roleSuccessAdded: "Role added",
  roleSuccessUpdated: "Role updated",
  roleErrorAdd: "Role could not be added",
  roleErrorUpdate: "Role could not be updated",
  roleDeleteTitle: "You are about to delete the role",
  roleConfirmDelete: "Are you sure you want to delete {roleName}?",
  addRoleDescription: (id) => (
    <Fragment>
      This page allows you to {id ? "edit" : "add"} roles to the {appName}{" "}
      platform.
    </Fragment>
  ),
  selectRole: "Select role...",
  rolesRequired: "Please select at least one role",
  yesText: "Yes",
  noText: "No",
  editProfile: "Edit Profile",
  batchFileTypeError:
    "Invalid attachment file type. Please upload a valid file.",
  batchFilesHint:
    "Please upload a file with one of the following extensions: .xlsx, .xls, .csv, .ods, .pdf, .docx, .doc",
  batchAttachments: "Attachments",
  editText: "Edit",
  uploadText: "Upload",
  uploadAttachmentsSuccess: "Attachments uploaded successfully",
  uploadAttachmentsError: "Unable to upload attachments",
  uploadAttachmentsComment: "Add a comment for the attachment",
  deleteAttachmentTitle: "Delete Attachment",
  deleteAttachmentDesc: "Are you sure you want to delete this attachment?",
  deleteAttachmentSuccess: "Attachment deleted successfully",
  deleteAttachmentError: "Unable to delete attachment",
  viewAttachment: "View Attachment",
  viewText: "View",
  addAttachment: "Add Attachment",
  addAttachmentDesc: "Add a new attachment to the batch",
  editAttachment: "Edit Attachment",
  editAttachmentDesc: "Replace the existing attachment with a new one",
  uploadAttachmentsRequired: "Please upload at least one attachment file",
  approveNoteRequired:
    "Please provide notes or feedback to decline or approved the submission",
  downloadReport: "Download Report",
  downloadReportSuccess: "Report downloaded successfully",
  downloadReportError: "Unable to download report",
  downloadData: "Download Data",
  bulkUpload: "Bulk Upload",
  selectChildForms: "Select Monitoring Forms",
  allData: "All Data",
  latestData: "Latest Data",
  moreItems: "More Items",
  moreCount: "+{{count}} more",
  allEntities: "All Entities",
  manageDraftTitle: "Manage Drafts",
  manageDraftText: (
    <Fragment>
      This is where you can manage your drafts. You can:
      <ul>
        <li>View your saved drafts</li>
        <li>Edit existing drafts</li>
        <li>Delete existing drafts</li>
      </ul>
    </Fragment>
  ),
  deleteDraftTitle: "Delete Draft",
  deleteDraftContent: "Are you sure you want to delete {{draftName}}?",
  deleteDraftSuccess: "Draft deleted successfully",
  deleteDraftError: "Unable to delete draft",
  draftCreatedByCol: "Created by",
  draftUpdatedByPrefix: "by",
  editAndPublishDraft: "Edit and Publish Draft",
  createDraftMonitoring: "Create Draft Monitoring Data",
  rejectText: "Reject",
  draftFormPublishConfirmTitle: "Publish Draft",
  draftFormPublishConfirmContent:
    "Are you sure you want to publish this draft ? This action cannot be undone.",
  draftFormPublishSuccess: "Draft published successfully",
  draftFormPublishError: "Unable to publish draft",
  draftFormSaveSuccess: "Draft saved successfully",
  draftFormSaveError: "Unable to save draft",
  selectRowsToDownload: "Please select rows to download",
  manageDataTabList: "Datapoint List",
  manageDataTabMap: "Map View",
  checkboxSelectAll: "Select all {{name}}",
  selectMonitoringFormPlaceholder: "Select Monitoring Form",
  selectQuestionPlaceholder: "Select Question",
  formAccess: "Form Access",
  roleFeatures: "Role Features",
  rolesLabel: "Role(s)",
  isSuperAdminLabel: "Is Superadmin?",
  showPendingUsers: "Show Pending Users",
  export2ExcelSuccess: "Data exported to Excel successfully",
  export2ExcelError: "Unable to export data to Excel",
  downloadAppText,
  showAllQuestionsSwitch: "Show all questions",
  totalMonitoring: "Total Monitoring",
  downloadAppsQRText: (
    <Fragment>
      Download the <b>{apkName} App</b> using the QR codes below
    </Fragment>
  ),
  downloadAppsLinkText: "or download using the links below:",
  dateFromPlaceholder: "From",
  dateToPlaceholder: "To",
  viewDetails: "View Details",

  // Platform console (MT-022). `de` is empty for every key in this
  // catalogue, console strings included, so nothing here is mirrored
  // into it: a German placeholder for this one feature would read as
  // translated when the rest of the app is not.
  platformConsole: "Platform Console",
  consoleTenants: "Tenants",
  consoleOperators: "Operators",
  // FB-018 Form Library console
  consoleFormLibrary: "Form Library",
  consoleFLDescription: "Curate the shared catalog of reusable form templates.",
  consoleFLNameCol: "Template",
  consoleFLCategoriesCol: "Categories",
  consoleFLUsedCol: "Used",
  consoleFLMonitoringCol: "Monitoring forms",
  consoleFLActionsCol: "Actions",
  consoleFLManageCategories: "Manage categories",
  consoleFLPromoteButton: "Promote from workspace",
  consoleFLPromoteTitle: "Promote a workspace form to the library",
  consoleFLEmpty: "No templates yet",
  consoleFLDeleteButton: "Delete",
  consoleFLDeleteConfirm:
    "Remove this template from the library? Existing copies are unaffected.",
  consoleFLDeleteSuccess: "Template removed from the library",
  consoleFLDeleteError: "Failed to remove template",
  consoleFLWorkspaceLabel: "Workspace",
  consoleFLWorkspacePlaceholder: "Select a workspace",
  consoleFLWorkspaceRequired: "Please select a workspace",
  consoleFLSourceLabel: "Source form",
  consoleFLSourcePlaceholder: "Select a published registration form",
  consoleFLSourceRequired: "Please select a source form",
  consoleFLCategoriesLabel: "Categories",
  consoleFLCategoriesPlaceholder: "Assign one or more categories",
  consoleFLPromoteSuccess: "Form promoted to the library",
  consoleFLPromoteError: "Failed to promote form",
  consoleFLPromotedFrom: "Promoted from",
  consoleFLNewTemplate: "New template",
  consoleFLFromWorkspace: "Select from an existing workspace",
  consoleFLFromScratch: "From scratch (Form Builder)",
  consoleFLEditButton: "Edit in Form Builder",
  consoleFLAddMonitoring: "Add monitoring form",
  consoleFLBack: "Back to library",
  consoleFLCancel: "Cancel",
  consoleFLPreviewHeading: "Form preview",
  consoleFLPreviewEmpty: "Select a source form to preview it here",
  consoleFLCategoryPlaceholder: "New category name",
  consoleFLCategoryAdd: "Add",
  consoleFLCategoryEmpty: "No categories yet",
  consoleFLCategoryDeleteConfirm: "Delete this category?",
  consoleFLCategoryError: "Category operation failed",
  closeButton: "Close",
  consoleSearchTenants: "Search subdomain or name",
  consoleStateAll: "All",
  consoleStateActive: "Active",
  consoleStateSuspended: "Suspended",
  consoleStateDeleted: "Deleted",
  consoleResultCount: "Results: {from} – {to} of {total} workspaces",
  consoleTotalWorkspaces: "Workspaces",
  consoleTotalUsers: "Users",
  consoleTotalForms: "Forms",
  consoleTotalDashboards: "Dashboards",
  consoleTotalDatapoints: "Datapoints",
  consoleTotalDevices: "Devices",
  consoleTotalsRow: "Total",
  consoleInspect: "Inspect",
  consoleInspectFailed: "Could not open that workspace",
  consoleSuspend: "Suspend",
  consoleRestore: "Restore",
  consoleRename: "Rename",
  consoleDelete: "Delete",
  consoleFeatures: "Features",
  consoleUsers: "Users",
  consoleDeactivate: "Deactivate",
  consoleReactivate: "Reactivate",
  consoleInviteOperator: "Invite operator",
  consoleRevoke: "Revoke",
  consoleLogo: "Logo",
  consoleUploadLogo: "Upload logo",
  consoleRemoveLogo: "Remove logo",
  consoleLogoUpdated: "Logo updated successfully",
  consoleLogoRemoved: "Logo removed successfully",
  brandingPanelTitle: "Workspace Branding",
  brandingPanelDescription:
    "Customise your workspace logo displayed on navigation and login.",
  brandingPanelButton: "Manage Branding",
  brandingModalTitle: "Workspace Branding",
  brandingLogoLabel: "Workspace Logo",
  brandingLogoHint: "Supported formats: PNG, JPG, JPEG, SVG up to 2MB.",
  brandingUploadSuccess: "Branding updated successfully",
  brandingUploadError: "Could not update branding",
  brandingRemoveSuccess: "Logo removed successfully",
  brandingRemoveError: "Could not remove logo",
  brandingRemoveBtn: "Remove logo",
  brandingUploadBtn: "Upload logo",
  brandingCurrentLogo: "Current logo",
  brandingNoLogo: "No custom logo set (using default Akvo logo)",

  // Onboarding Tour
  tourWelcomeTitle: "Welcome to Akvo MIS",
  tourWelcomeSubtitle:
    "What do you want to do first? We’ll show you around in under a minute.",
  tourGoalRecommended: "Recommended",
  tourGoalSetupTitle: "Set up a data collection",
  tourGoalSetupDesc: "Build a form and get it to your field team",
  tourGoalReviewTitle: "Review and approve data",
  tourGoalReviewDesc: "Check submissions waiting for you",
  tourGoalExploreTitle: "Explore data and dashboards",
  tourGoalExploreDesc: "Browse, chart and download results",
  tourBtnShowMeHow: "Show me how",
  tourBtnSkip: "Skip",
  tourBtnBack: "Back",
  tourBtnNext: "Next",
  tourStepOf: "STEP {current} OF {total}",
  tourCopyAppLink: "Copy app link",
  tourLinkCopied: "App download link copied to clipboard",
  tourLinkCopyError: "Unable to copy link to clipboard",
  tourSetupStep1Title: "Build a form",
  tourSetupStep1Desc:
    "Add sections and questions, then publish — or skip the blank page and start from a ready-made template in the Form Library. Your field team can fill it in as soon as it is published.",
  tourSetupStep2Title: "Get the app to your field team",
  tourSetupStep2Desc:
    "Your field team collects data offline in the mobile app. Share the download link with them.",
  tourSetupStep3Title: "Watch submissions arrive",
  tourSetupStep3Desc:
    "New submissions from the field appear here. Filter by form, or add one yourself from the web.",
  tourSetupFinalBtn: "Create your first form",
  tourReviewStep1Title: "Your pending approvals",
  tourReviewStep1Desc:
    "Submissions waiting for your decision land here. You can also see what your subordinate approvers still have to review.",
  tourReviewStep2Title: "Review submissions",
  tourReviewStep2Desc:
    "Open Manage Data to browse and filter submissions. Approvals and drafts also live under Data.",
  tourReviewFinalBtn: "Review pending approvals",
  tourExploreStep1Title: "Browse your data",
  tourExploreStep1Desc:
    "Open Manage Data to browse, filter and review submissions by form and location.",
  tourExploreStep2Title: "Chart it in a dashboard",
  tourExploreStep2Desc:
    "Build a dashboard from your data, publish it, then keep it private or share it publicly.",
  tourExploreStep3Title: "Download your data",
  tourExploreStep3Desc:
    "Export submissions from Manage Data. Large exports run in the background and wait for you here.",
  tourExploreFinalBtn: "Create a dashboard",
  tourExploreViewDataBtn: "Browse data",
  tourGetHelpTitle: "Get help any time",
  tourGetHelpDesc:
    "Have questions? Use our AI assistant anytime at the bottom right, or browse our Documentation for in-depth guides.",
};

export default en;
