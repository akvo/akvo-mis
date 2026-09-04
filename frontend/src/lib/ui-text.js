import React, { Fragment } from "react";

// window.appConfig comes from the /config.js bootstrap script, and this
// module reads it while the bundle is still evaluating — before any
// component renders and before any error boundary exists. Dereferencing
// it directly means a config.js that fails to arrive takes the entire
// app down with a TypeError rather than degrading to a default name.
const appName = window?.appConfig?.name || "Akvo MIS";
const apkName = window?.appConfig?.apkName || appName;

const downloadAppText = <Fragment>Download {apkName} App</Fragment>;

const uiText = {
  en: {
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
    menuFormBuilder: "Form Builder",
    menuDashboards: "Dashboards",
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
    dashboardWidgetQuestionGone: "This widget's question no longer exists.",
    dashboardWidgetFormGone: "This widget's form no longer exists.",
    dashboardFilterPeriod: "Date",
    dashboardFilterAllLocations: "All locations",
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
      "Pasted exactly as given. A snippet with no width of its own stretches to fill the page; give it a width and height to have it centred instead. If the report requires signing in, visitors will see a login screen even though it looks correct to you.",
    dashboardEmbedBadge: "External",
    dashboardEmbedUnavailable:
      "This dashboard's external content cannot be shown, because embedding is not configured for this deployment.",
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
    errorVerifyCreds:
      "Please verify your credentials for the requested resource",
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
    lorem:
      "Lorem ipsum dolor sit amet consectetur adipisicing elit. Possimus, assumenda quos? Quia deleniti sapiente aut! Ab consequatur cumque fugit ea. Dolore ex rerum quisquam inventore eum dicta doloribus harum cum.",
    lorem2: "Lorem ipsum dolor sit amet consectetur adipisicing elit.",
    // Charts
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
    formBuilderExportButton: "Export",
    formBuilderExportError: "Failed to export form",
    formBuilderExportXlsformButton: "Export XLSForm",
    formBuilderExportXlsformError: "Failed to export XLSForm",
    formBuilderExportXlsformWarningTitle: "XLSForm Export Warnings",
    formBuilderExportCascadeCsvButton: "Export Cascade CSV",
    formBuilderExportCascadeCsvError: "Failed to export Cascade CSV",
    formBuilderImportButton: "Import Form",
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
    formBuilderImportInvalidFileXlsform:
      "Only .xlsx or .xls files are supported",
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
    formBuilderImportXlsformNoticeTitle: "XLSForm Compatibility Note",
    formBuilderImportXlsformNoticeDesc:
      "Akvo MIS imports standard question types, options, multi-language labels, validations, and skip-logic. Follow-up questions for 'Other' choices are preserved as dependent questions (which you can optionally streamline using 'Allow other' in the Form Editor). Advanced features such as dynamic calculations, programmatic repeat counts, or complex XPath expressions are skipped. Please review any warnings below and verify the form in the Form Editor after import.",
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
    dataDownloadTitle: "Data Download",
    dataDownloadButton: "Download Data",
    dataDownloadText: (
      <Fragment>
        This is where you :
        <ul>
          <li>Access downloaded data</li>
        </ul>
      </Fragment>
    ),
    dataUploadTitle: "Data Upload",
    AdministrationDataUpload: "Administration Data Upload",
    dataUploadButton: "Data Upload",
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
    manageUserTitle: "User Management",
    manageUserButton: "Manage Users",
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
    newLevelName: "New level name",
    levelFrozenHint:
      "Levels can no longer be added or removed because administrative " +
      "units already exist. Renaming is still available.",
    levelDeleteTitle: "Remove the deepest level?",
    manageEntities: "Manage Entities",
    manageEntityTypes: "Manage Entity Types",
    addEntities: "Add Entities",
    entityTabTitle: "Entities",
    entityLabel: "Entity",
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
    approvalsTitle: "Approvals",
    // Approvers Tree
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
    batchDatasets: "Batch Datasets",
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
        validated by the system . You will be notified via email if the data
        fails the validation tests . There will also be an attachment of the
        validation errors that needs to be corrected. If there are no validation
        errors , then the data will be forwarded for verification, approval, and
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
        Please fill up the webform below with relevant responses. You will need
        to answer all mandatory questions before you can submit.
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
    resetText: "Reset",
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
    accountDisclaimer:
      "The user is accountable for his/her account and in case there are any changes (Transfers, retirement, any kind of leave, resignation etc) this should be communicated to the County Administrator or National Super Admin who might be able to assign the roles to the new officer.",
    // Log in
    loginTitle: "Welcome back",
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
    deleteUserHint:
      "Deleting this user will not delete the data association(s)",
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
    tourControlCenter:
      "Lorem ipsum dolor sit, amet consectetur adipisicing elit",
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
    mobilePanelButton: "Manage Data Collectors",
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
    mobileSelectAdm: "Select administrations...",
    mobileSelectForms: "Select forms...",
    mobileConfirmDeletion: "Are you sure?",
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
    mdPanelTitle: "Master Data",
    mdPanelButton: "Master Data",
    mdPanelText: (
      <Fragment>
        This is where you :
        <ul>
          <li>View all master data</li>
          <li>Modify existing data</li>
          <li>Delete existing data</li>
        </ul>
      </Fragment>
    ),
    formPasscode: "Form Passcode",
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
    exportButton: "Export",
    bulkUploadButton: "Bulk Upload",
    addNewButton: "Add New",
    cancelButton: "Cancel",
    deleteText: "Delete",
    errDeleteCascadeText1:
      "It is associated with other resources or has cascade restrictions.",
    errDeleteCascadeText2:
      "Please review and resolve dependencies before attempting to delete.",
    manageEntityTitle: "Manage Entities",
    addEntity: "Add New",
    editEntity: "Edit Entity",
    confirmDeleteEntity: "Are you sure you want to delete this entity?",
    errDeleteEntityTitle: "Unable to delete the entity",
    successAddedEntity: "Entity added",
    successUpdatedEntity: "Entity updated",
    successDeletedEntity: "Entity deleted",
    entityText: "Entity",
    entityDataTitle: "Entity Data",
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
    successDeletedOrg: "Organisation deleted",
    errAddOrg: "Organization could not be added",
    errUpdateOrg: "Organization could not be updated",
    orgLabelName: "Organization Name",
    orgLabelAttr: "Organization Attributes",
    selectAttributes: "Select attributes...",
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
    userTrained: "Trained",
    userSelectLevelRequired: "Please select an administration level",
    userNationalApprover: "National Approver",
    loadingText: "Loading...",
    questionnairesLabel: "Questionnaires",
    questionnairesRequired:
      "Please select at least one questionnaire access level: Read-only, Editor, or Approver.",
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
    prefilledAdmModalTitle: "Prefilled Administration requested",
    prefilledAdmModalContent:
      "We're processing your request. Once complete, the prefilled administration template will be sent to your email shortly.  Please keep a close eye on your email, Thank you. ",
    prefilledAdmUploadLabel: "Upload the data",
    prefilledDownloadTitle: "Administrative Download",
    prefilledPanelText: (
      <Fragment>
        <p>
          This page shows your pre-filled administrative data export requests.
          <br />
          For exports which are already generated, please click on the Download
          button to download the data.
        </p>
      </Fragment>
    ),
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
            Get the list of forms that were collected for this datapoint (new
            and update)
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
        This page allows you to add users to the {appName} platform. You will
        only be able to add users for regions under your jurisdisction.
        <br />
        Once you have added the user, the user will be notified by email to set
        their password and access the platform
      </Fragment>
    ),
    // Home Page
    homeQuickLinks: [
      { text: "Privacy Policy", href: "/privacy-policy", isPage: true },
      { text: "Terms & Conditions", href: "/terms-n-conditions", isPage: true },
      { text: "Cookie Policy", href: "/cookie-policy", isPage: true },
      {
        text: downloadAppText,
        href: "/app",
        isPage: false,
      },
    ],
    homeJumbotronTitle: <Fragment>{appName}</Fragment>,
    homeJumbotronSubtitle: (
      <Fragment>
        A comprehensive platform designed to support data collection,
        monitoring, and decision-making for your organisation.
      </Fragment>
    ),
    homeHeroEyebrowLive: "Live",
    homeHeroEyebrowOrg: "<Your Organisation>",
    homeHeroEyebrowDept: "<Your Department>",
    homeHeroTitlePrefix: "— a comprehensive platform for",
    homeHeroTitleAccent: "monitoring & information",
    homeHeroTitleSuffix: "services.",
    homeHeroCtaLearnMore: "Learn more",
    homeHeroCaptionTitle: (
      <Fragment>
        Reliable data
        <br />
        for every community you serve.
      </Fragment>
    ),
    homeHeroCaptionEyebrowSuffix: "Platform",
    homeJumbotronImage: {
      src: "https://images.unsplash.com/photo-1642450909999-7106494ef779?q=80&w=1974&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
      alt: "Water landscape",
    },
    homeMandateTitle: "Our Mandate",
    homeMandateHeadline: (
      <Fragment>
        Ensuring a <span className="accent">sustainable</span> monitoring and
        reporting system.
      </Fragment>
    ),
    homeMandateText:
      "Your organisation is mandated with the responsibility of ensuring sustainable service delivery through the development of evidence-based policies, efficient data management, and rigorous compliance monitoring.",
    homeStructureTitle: "Organisation Structure",
    homeStructureText:
      "Replace this text with a description of your organisation structure. This section can be updated in ui-text.js or configured via a content management system.",
    homeStructureImage: {
      src: "/logo.svg",
      alt: "Organisation Structure",
    },
    homeVideoTitle: "Watch & Learn",
    homeVideoHeadline: (
      <Fragment>
        See <span className="accent">{appName}</span> in action.
      </Fragment>
    ),
    homeVideoText:
      "A short walkthrough of how the platform supports data collection, monitoring, and decision-making for your organisation.",
    homeVideoIframeTitle: `${appName} introduction video"`,
    homeKeyRolesTitle: "Key Roles and Responsibilities",
    homeKeyRolesHeadline: (
      <Fragment>
        Policy, oversight and <span className="accent">compliance</span> across
        your sector.
      </Fragment>
    ),
    homeKeyRolesText:
      "The key roles and responsibilities of the organisation include policy and legislation development, technical and policy advisory, compliance monitoring, and service delivery oversight.",
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
    homeFooterQuickLinksTitle: "Quick Links",
    homeFooterContactTitle: "Contact Us",
    homeFooterContactDetails: ["<Your Organisation>", "<Your Department>"],
    homeFooterContactAddress: ["<Your Address>"],
    homeFooterContactPhone: "<Your Phone Number>",
    homeFooterAboutTitle: <Fragment>About {appName}</Fragment>,
    homeFooterAboutText: (
      <Fragment>
        {appName} is a comprehensive platform designed to support data
        collection, monitoring, and decision-making for your organisation. It
        serves as a centralised hub for evidence-based reporting and efficient
        resource allocation.
      </Fragment>
    ),
    homeFooterCopyrightText: "© 2025 <Your Organisation>",
    homeFooterPoweredByText: "Powered by",
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
    roleDescriptionRequired: "Role description is required",
    roleAdmLevel: "Administration Level",
    roleAdmLevelRequired: "Administration level is required",
    roleAdmLevelPlaceholder: "Select administration level...",
    roleAccess: "Role Access",
    roleAccessRequired: "Role access is required",
    roleTotalUsers: "Total Users",
    roleSuccessAdded: "Role added",
    roleSuccessUpdated: "Role updated",
    roleSuccessDeleted: "Role deleted",
    roleErrorAdd: "Role could not be added",
    roleErrorUpdate: "Role could not be updated",
    roleErrDeleteTitle: "Unable to delete the role",
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
    fileTypeError: "Invalid file type. Please upload a valid file.",
    batchFileTypeError:
      "Invalid attachment file type. Please upload a valid file.",
    batchFilesHint:
      "Please upload a file with one of the following extensions: .xlsx, .xls, .csv, .ods, .pdf, .docx, .doc",
    batchAttachments: "Attachments",
    editText: "Edit",
    uploadText: "Upload",
    uploadAttachments: "Upload Attachments",
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
    addNew: "Add New",
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
    editAndPublishDraft: "Edit and Publish Draft",
    editDraft: "Edit Draft",
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
  },

  de: {},
};

export default uiText;
