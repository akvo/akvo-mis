import React, { Fragment } from "react";
import { appName, apkName } from "../app-name";

// Spanish UI strings. Real translations (not an English copy). Only the keys
// that differ from English; the assembler (../ui.js) fills the rest from
// English, the same way French does.
const es = {
  // Sidebar Menu Labels
  menuUsers: "Usuarios",
  menuControlCenter: "Centro de control",
  menuManagePlatformUsers: "Gestionar usuarios de la plataforma",
  menuValidationTree: "Árbol de validación",
  menuManageMobileUsers: "Gestionar usuarios móviles",
  menuManageRoles: "Gestionar roles",
  menuMasterData: "Datos maestros",
  menuAdministrativeList: "Lista administrativa",
  menuLevels: "Niveles",
  menuAttributes: "Atributos",
  menuEntities: "Entidades",
  menuEntityTypes: "Tipos de entidad",
  menuOrganisations: "Organizaciones",
  menuData: "Datos",
  menuManageData: "Gestionar datos",
  menuPendingSubmissions: "Envíos",
  menuApprovals: "Aprobaciones",
  menuDownloads: "Descargas",
  menuManageDraft: "Gestionar borradores",
  menuDownloadApps: "Descargar la aplicación",
  menuDocumentation: "Documentación",
  menuProductTour: "Hacer un recorrido",
  menuFormBuilder: "Creador de formularios",
  // FB-018 Form Library
  formLibraryTitle: "Biblioteca de formularios",
  formLibraryDescription:
    "Explore plantillas de formularios listas para usar y cree un formulario nuevo a partir de una con un solo clic.",
  formLibrarySearchPlaceholder: "Buscar plantillas",
  formLibraryAllCategories: "Todas las categorías",
  formLibraryUncategorized: "Sin categoría",
  formLibraryUsedCount: "Usado",
  formLibraryMonitoringLabel: "formulario(s) de seguimiento",
  formLibraryPreviewButton: "Vista previa",
  formLibraryUseButton: "Usar este formulario",
  formLibraryViewOnly: "Solo lectura",
  formLibraryEmptyText: "No hay plantillas disponibles",
  formLibraryPreviewTitle: "Vista previa de la plantilla",
  formLibraryRegistrationTab: "Registro",
  formLibraryMonitoringTab: "Seguimiento",
  formLibraryUseSuccess:
    "Plantilla copiada a su espacio de trabajo como un nuevo borrador.",
  formLibraryUseError: "No se pudo usar esta plantilla",
  menuDashboards: "Paneles",
  menuSettings: "Ajustes",

  // Dashboards
  dashboardListTitle: "Mis paneles",
  dashboardListSubtitle: "Cree y gestione sus paneles de datos personalizados.",
  dashboardNew: "Nuevo panel",
  dashboardEmptyTitle: "Aún no hay paneles",
  dashboardEmptyDesc:
    "Cree su primer panel personalizado para visualizar los datos de sus formularios.",
  dashboardCreateTitle: "Crear un panel",
  dashboardCreateHint:
    "Asígnele un nombre y luego elija el formulario de registro cuyos datos mostrará este panel.",
  dashboardCreateBtn: "Crear panel",
  dashboardNameLabel: "Nombre del panel",
  dashboardNameRequired: "Introduzca un nombre de panel",
  dashboardFormLabel: "Fuente de datos",
  dashboardFormExtra:
    "Este panel mostrará los datos de este formulario y de sus formularios de seguimiento. Esto no se puede cambiar después.",
  dashboardFormRequired: "Seleccione un formulario de registro",
  dashboardFormPlaceholder: "Seleccione un formulario de registro",
  dashboardNoForms: "No hay formularios de registro publicados disponibles.",
  dashboardGoFormBuilder:
    "Vaya al Creador de formularios para crear y publicar un formulario.",
  dashboardForbidden: "Ya no tiene permiso para realizar esta acción.",
  dashboardCreated: "Panel creado",
  dashboardAiApplyWarning:
    "Panel creado, pero algunos widgets de IA no se pudieron aplicar.",
  dashboardDeleted: "Panel eliminado",
  dashboardDuplicated: "Panel duplicado",
  dashboardDeleteConfirm: "¿Eliminar este panel?",
  dashboardSlugConflict:
    "Ya existe un panel con un nombre similar. Elija un nombre diferente.",
  dashboardSaved: "Panel guardado",
  dashboardPublished: "Panel publicado",

  // Viewer and preview
  dashboardViewEmpty: "Este panel aún no tiene widgets.",
  dashboardNotFound: "El panel está vacío",
  dashboardNotFoundHint:
    "Este panel aún no se ha publicado o puede que se haya eliminado.",
  dashboardEdit: "Editar panel",
  dashboardPreview: "Vista previa",
  dashboardBackToEditing: "Volver a la edición",
  dashboardWidgetError: "No se pudo cargar este widget",
  dashboardWidgetRetry: "Reintentar",
  dashboardWidgetNoData: "No hay datos disponibles",
  dashboardWidgetNoDataFiltered:
    "No se encontraron datos para los filtros actuales",
  dashboardWidgetQuestionGone: "La pregunta de este widget ya no existe.",
  dashboardWidgetFormGone: "El formulario de este widget ya no existe.",

  // Export
  dashboardExport: "Exportar",
  dashboardExportPng: "Imagen PNG",
  dashboardExportPdf: "Documento PDF",
  dashboardExportFailed: "No se pudo exportar este panel",
  dashboardFilterPeriod: "Fecha",
  dashboardFilterAllLocations: "Todas las ubicaciones",
  dashboardFilterLocation: "Ubicación",
  dashboardExportFiltered: "Filtrado por",
  dashboardFilters: "Filtros",
  dashboardFiltersActive: "activo(s)",
  dashboardFiltersApply: "Aplicar",
  dashboardFiltersClear: "Borrar todo",
  dashboardFiltersHowTo:
    "Marque opciones para mostrar solo las marcadas. Los datos sin respuesta a una pregunta filtrada se ocultan.",
  dashboardFiltersMatch: "Mostrar los datos que coincidan con",
  dashboardFiltersMatchAll: "Todos los filtros",
  dashboardFiltersMatchAny: "Cualquier filtro",
  dashboardFiltersRemove: "Quitar el filtro",
  dashboardFiltersMore: "más filtros",
  dashboardFiltersTooMany:
    "Demasiadas opciones marcadas: {max} como máximo en total. Desmarque algunas.",
  dashboardFilterQuestions: "Preguntas de filtro",
  dashboardFilterChoose: "Elegir preguntas…",
  dashboardFilterScope: "Respuestas de",
  dashboardFilterSearch: "Buscar por pregunta, nombre o grupo",
  dashboardFilterNoMatch: "Ninguna pregunta coincide",
  dashboardFilterSelected: "seleccionada(s)",
  dashboardFilterAllForms: "Todos los formularios",
  dashboardFilterSuggested: "Usadas en sus widgets",
  dashboardFilterRemove: "Quitar",
  dashboardFilterCovers: "Cubre:",
  dashboardFilterOnlyOn: "solo en",
  dashboardDateQuestion: "Fecha para filtrar",
  dashboardDateSubmission: "Fecha de envío",
  dashboardDateSaved: "Pregunta de fecha guardada",
  dashboardFilterGone: "(ya no está en el formulario)",

  // Visibility
  dashboardVisibilityTitle: "Panel público",
  dashboardVisibilityHintOn:
    "Cualquiera puede abrirlo sin iniciar sesión, y aparece en el menú Paneles para cada visitante. Surte efecto de inmediato: no es necesario guardar.",
  dashboardVisibilityHintDraft:
    "Publique primero este panel. Solo un panel publicado se puede hacer público.",
  dashboardMakePublicTitle: "¿Hacer público este panel?",
  dashboardMakePublicBody:
    "Cualquier persona con el enlace podrá abrir este panel sin iniciar sesión, y aparecerá en el menú Paneles para cada visitante de este espacio de trabajo.",
  dashboardMakePublicRawData:
    "Este panel incluye una tabla y un mapa. Los visitantes públicos verán las filas de envío individuales y la ubicación de cada punto registrado, no solo los totales.",
  dashboardMakePublicOk: "Hacer público",
  dashboardMadePublic: "El panel ahora es público",
  dashboardMadePrivate: "El panel ahora es privado",
  dashboardVisibilityPublic: "Público",
  dashboardVisibilityPrivate: "Privado",

  // Embedded dashboards
  dashboardKindLabel: "¿Qué es este panel?",
  dashboardKindWidgets: "Construirlo aquí",
  dashboardKindWidgetsHint:
    "Componga gráficos y tablas a partir de los datos de sus propios formularios.",
  dashboardKindEmbed: "Insertar un panel externo",
  dashboardKindEmbedHint:
    "Mostrar un informe publicado por Power BI, Tableau, Looker Studio u otra herramienta.",
  dashboardEmbedLabel: "Código de inserción",
  dashboardEmbedPlaceholder:
    "Pegue el código de inserción desde el cuadro de diálogo Compartir de su herramienta de informes",
  dashboardEmbedRequired: "Pegue el código de inserción",
  dashboardEmbedHint:
    "Pegado exactamente como se proporciona, el tamaño proviene del fragmento: déle un ancho y un alto para mostrarlo a ese tamaño, centrado.",
  dashboardEmbedBadge: "Externo",
  dashboardEmbedUnavailable:
    "El contenido externo de este panel no se puede mostrar porque los paneles insertados no están disponibles aquí.",
  preview: "Vista previa",
  publish: "Publicar",
  published: "Publicado",
  draft: "Borrador",

  // Error messages
  error: "Error",
  errorPageNA: "Vaya, esta página no está disponible",
  errorAuth: "No está autorizado para acceder a esta página",
  errorUnknown: "Se produjo un error desconocido",
  errorVerifyCreds: "Verifique sus credenciales para el recurso solicitado",
  backHome: "Volver a la página de inicio",
  errorDataLoad: "No se pudieron cargar los datos",
  errorUserLoad: "No se pudieron cargar los datos del usuario",
  errorFileList: "No se pudo obtener la lista de archivos",
  errorSomething: "Algo salió mal",
  errorMandatoryFields: "Responda todas las preguntas obligatorias",
  errorFileUpload: "No se pudo subir el archivo",

  // Header Links
  controlCenter: "Centro de control",
  myProfile: "Mi perfil",
  settings: "Ajustes del sistema",
  signOut: "Cerrar sesión",
  dashboards: "Paneles",
  reports: "Informes",
  newsEvents: "Noticias y eventos",
  login: "Iniciar sesión",

  // Log in / Auth
  loginTitle: "Bienvenido de nuevo",
  loginAccountDetails: "Introduzca los datos de su cuenta",
  loginTroublePrefix:
    "¿Tiene problemas para acceder a la plataforma? Por favor",
  loginContactLink: "contáctenos",
  userEmail: "Correo electrónico",
  loginEmailPlaceholder: "Correo electrónico",
  loginPasswordLabel: "Contraseña",
  loginPasswordPlaceholder: "Contraseña",
  usernameRequired: "Introduzca su usuario",
  passwordRequired: "Introduzca su contraseña",
  recoverPassword: "Recuperar contraseña",
  createAccount: "Crear una cuenta",
  loginNotActivated: "Esta cuenta aún no se ha activado",
  loginResendActivation: "Reenviar el correo de activación",
  contactAdmin: "Póngase en contacto con el administrador",
  formAssignmentError:
    "No tiene ningún formulario asignado, póngase en contacto con el administrador",
  forgotTitle: "Restablecer su contraseña",
  forgotDesc:
    "Introduzca el correo electrónico asociado a su cuenta y le enviaremos un correo con instrucciones para restablecer su contraseña",
  instructionsMailed: "Instrucciones enviadas correctamente",
  sendInstructions: "Enviar instrucciones",
  loginLoadingTex: (
    <Fragment>
      Verificando
      <br />
      <small>Espere por favor..</small>
    </Fragment>
  ),
  welcomeShort: (
    <Fragment>
      Bienvenido a la plataforma <b>{appName}</b>
    </Fragment>
  ),
  resetHint: (
    <Fragment>
      Configure su contraseña para la plataforma.
      <br />
      Su contraseña debe incluir:
    </Fragment>
  ),
  invalidInviteTitle: "Código de invitación no válido",
  // Activación / verificación de correo
  activateVerifiedTitle: "Correo verificado",
  activateVerifiedDesc:
    "Su cuenta está activa. Queda un paso rápido: cuéntenos sobre su proyecto.",
  activateContinueSetup: "Continuar con la configuración →",
  activateVerifying: "Verificando su correo electrónico…",
  activateCheckInboxTitle: "Revise su bandeja de entrada",
  activateCheckInboxDesc:
    "Si esa cuenta aún necesita activarse, un nuevo enlace está en camino.",
  activateErrorTitle: "No pudimos comprobar su enlace",
  activateErrorDesc:
    "Algo salió mal al conectar con el servidor. Su enlace probablemente está bien; inténtelo de nuevo en un momento.",
  activateTryAgain: "Intentar de nuevo",
  activateExpiredTitle: "Este enlace ha caducado",
  activateExpiredDesc:
    "Los enlaces de activación son válidos durante 7 días. Solicite uno nuevo y se lo enviaremos por correo de inmediato.",
  activateEmailPlaceholder: "usted@organizacion.org",
  backToLogin: "Volver al inicio de sesión",
  couldNotSendEmail: "No se pudo enviar el correo",
  // Configuración / configuración del proyecto
  configureStep1: "Registrarse",
  configureStep2: "Verificar correo",
  configureStep3: "Configurar proyecto",
  configureStep4: "Panel",
  configureTitle: "Configure su proyecto",
  configureSubtitle:
    "Esto nombra su jerarquía administrativa. Puede añadir niveles más profundos después; estos dos nombres de nivel superior se establecen una sola vez aquí.",
  configureFirstName: "Nombre",
  configureFirstNamePlaceholder: "Juana",
  configureLastName: "Apellido",
  configureLastNamePlaceholder: "Pérez",
  configureRequired: "Obligatorio",
  configureTopLevelName: "Nombre del nivel superior",
  configureTopLevelExtra:
    "La etiqueta de su nivel administrativo más alto, p. ej. País, Nacional o Región. No un lugar, sino un nivel.",
  configureTopLevelRequired: "Asigne un nombre a su nivel superior.",
  configureTopLevelPlaceholder: "País",
  configureTopUnitName: "Nombre de la unidad superior",
  configureTopUnitExtra:
    "Su única unidad superior en ese nivel, p. ej. Kenia. Todo lo que cargue después se ubicará bajo ella.",
  configureTopUnitRequired: "Asigne un nombre a su unidad superior.",
  configureTopUnitPlaceholder: "Kenia",
  configureLogoLabel: "Logotipo del espacio de trabajo",
  configureLogoExtra:
    "Opcional. PNG, JPG o JPEG de hasta 2 MB. Se muestra en la navegación superior y en la página de inicio de sesión.",
  configureUploadLogo: "Subir logotipo",
  configureLogoUploadError: "No se pudo subir el logotipo",
  configurePreview: "Vista previa: esta es la jerarquía que está creando:",
  configureLevel0Tag: "Nivel 0",
  configureTopUnitHint: "└ unidad superior",
  configureFinish: "Finalizar configuración",
  configureSaveError: "No se pudo guardar su espacio de trabajo",
  configureDoneTitle: "Todo listo",
  configureWelcome: "Bienvenido",
  configureReadyWith: "Su espacio de trabajo está listo con",
  configureAtTop:
    "en la parte superior. A continuación, añada los niveles por debajo.",
  configureContinue: "Continuar a la gestión de niveles →",

  // Reports
  noTemplate: "No se encontraron plantillas",
  chooseTemplate: "Elegir una plantilla",
  backBtn: "Atrás",
  printBtn: "Imprimir",

  // Events
  upcomingEventText: "Próximos eventos",
  eventTitle: "Noticias y eventos",
  latestUpdateText: "Últimas actualizaciones",

  // Charts
  showEmpty: "Mostrar valores vacíos",
  noInformationAvailable: "No hay información disponible",

  // User Management
  manageDataValidationSetup: "Árbol de validación",
  manageUsers: "Gestionar usuarios",
  addUser: "Añadir usuario",
  addNewUser: "Añadir nuevo usuario",
  editUser: "Editar usuario",
  updateUser: "Actualizar usuario",
  manageRoleText: (
    <Fragment>
      Aquí es donde gestiona los roles según sus campos. Puede:
      <ul>
        <li>Añadir un nuevo rol</li>
        <li>Modificar un rol existente</li>
        <li>Eliminar un rol existente</li>
      </ul>
    </Fragment>
  ),

  // Organisation Management
  manageOrganisations: "Gestionar organizaciones",
  addOrganisation: "Añadir organización",
  editOrganisation: "Editar organización",
  updateOrganisation: "Actualizar organización",

  // Validations
  valFirstName: "El nombre es obligatorio",
  valLastName: "El apellido es obligatorio",
  valEmail: "Introduzca una dirección de correo electrónico válida",
  valPhone: "El número de teléfono es obligatorio",
  valRole: "Seleccione un rol",
  valOrganization: "Seleccione una organización",
  valOrgName: "El nombre de la organización es obligatorio",
  valOrgAttributes: "Seleccione atributos",

  // Control Center
  manageDataTitle: "Gestionar datos",
  manageDataButton: "Gestionar datos",
  newSubmissionBtn: "Añadir nuevo envío",
  finishSubmissionBtn: "Finalizar e ir a Gestionar datos",
  finishSubmissionBatchBtn: "Finalizar e ir al lote",
  noFormText: "Sin datos",
  noFormSelectedText: "Ningún formulario seleccionado",
  ccDescriptionPanel:
    "Acceso instantáneo a todas las páginas de administración y los paneles de resumen para la aprobación de datos.",
  manageDataText: (
    <Fragment>
      Aquí puede:
      <ul>
        <li>Añadir nuevos datos mediante formularios web</li>
        <li>Cargar datos de forma masiva mediante hojas de cálculo</li>
        <li>Descargar datos</li>
      </ul>
    </Fragment>
  ),

  // Form Builder
  formBuilderCreateTitle: "Crear formulario",
  formBuilderEditTitle: "Editar formulario",
  formBuilderDraftRestored:
    "Hemos recuperado su trabajo anterior: revíselo antes de guardar.",
  formBuilderBackToSaved: "Volver al estado guardado",
  formBuilderSaveSuccess: "Formulario guardado",
  formBuilderSaveError: "No se pudo guardar el formulario",
  formBuilderCreateSuccess: "Formulario creado correctamente",
  formBuilderCreateError: "No se pudo crear el formulario",
  formBuilderPublishSuccess: "Formulario publicado",
  formBuilderPublishError: "No se pudo publicar el formulario",
  formBuilderUnpublishSuccess: "Formulario despublicado",
  formBuilderUnpublishError: "No se pudo despublicar el formulario",
  formBuilderActivateError: "No se pudo activar la versión",
  formBuilderPreviewError: "No se pudo cargar la versión",
  formBuilderVersionHistoryTitle: "Historial de versiones",
  formBuilderVersionsButton: "Versiones",
  formBuilderRefreshButton: "Actualizar",
  formBuilderVersionHistoryEmpty: "Aún no hay versiones publicadas",
  formBuilderNameCol: "Nombre",
  formBuilderTypeCol: "Tipo",
  formBuilderStatusCol: "Estado",
  formBuilderLastUpdatedCol: "Última actualización",
  formBuilderVersionCol: "Versión",
  formBuilderPublishedAtCol: "Publicado el",
  formBuilderPublishedByCol: "Publicado por",
  formBuilderActionsCol: "Acciones",
  formBuilderActiveTag: "Activo",
  formBuilderPreviewButton: "Vista previa",
  formBuilderActivateButton: "Activar",
  formBuilderSetActiveButton: "Establecer como activo",
  formBuilderPublishButton: "Publicar",
  formBuilderUnpublishTitle: "¿Despublicar este formulario?",
  formBuilderUnpublishDesc:
    "El formulario ya no estará disponible para la recopilación de datos.",
  formBuilderUnpublishButton: "Despublicar",
  formBuilderStatusPublished: "Publicado",
  formBuilderStatusDraft: "Borrador",
  formBuilderResetDraft: "Cargar desde el servidor",
  formBuilderCreateMonitoringButton: "Crear formulario de seguimiento",
  formBuilderCreateButton: "Crear nuevo formulario",
  formBuilderRegistrationType: "Registro",
  formBuilderMonitoringType: "Seguimiento",
  formBuilderTabActive: "Activo",
  formBuilderTabArchived: "Archivado",
  formBuilderSearchPlaceholder: "Buscar por nombre",
  formBuilderFilterStatusAll: "Todos los estados",
  formBuilderFilterTypeAll: "Todos los tipos",
  formBuilderArchivedAtCol: "Archivado",
  formBuilderDuplicateButton: "Duplicar",
  formBuilderArchiveButton: "Archivar",
  formBuilderRestoreButton: "Restaurar",
  formBuilderDeleteButton: "Eliminar permanentemente",
  formBuilderPublishConfirmTitle: "¿Publicar este formulario?",
  formBuilderPublishConfirmDesc:
    "Estará disponible para la recopilación de datos.",
  formBuilderArchiveConfirmTitle: "¿Archivar este formulario?",
  formBuilderRestoreConfirmTitle: "¿Restaurar este formulario?",
  formBuilderRestoreConfirmDesc:
    "Volverá como borrador; vuelva a publicarlo para reanudar la recopilación de datos.",
  formBuilderDeleteConfirmTitle: "¿Eliminar permanentemente este formulario?",
  formBuilderDeleteConfirmDesc: "Esta acción no se puede deshacer.",
  formBuilderArchiveSuccess: "Formulario archivado",
  formBuilderArchiveError: "No se pudo archivar el formulario",
  formBuilderRestoreSuccess: "Formulario restaurado",
  formBuilderRestoreError: "No se pudo restaurar el formulario",
  formBuilderDuplicateSuccess: "Formulario duplicado",
  formBuilderDuplicateError: "No se pudo duplicar el formulario",
  formBuilderDeleteSuccess: "Formulario eliminado permanentemente",
  formBuilderDeleteError: "No se pudo eliminar el formulario",
  formBuilderStatusArchived: "Archivado",
  formBuilderEmptyText: "No se encontraron formularios",
  formBuilderExportButton: "Exportar",
  formBuilderExportError: "No se pudo exportar el formulario",
  formBuilderExportXlsformButton: "Exportar XLSForm",
  formBuilderExportXlsformError: "No se pudo exportar XLSForm",
  formBuilderExportXlsformWarningTitle: "Advertencias de exportación XLSForm",
  formBuilderExportCascadeCsvButton: "Exportar CSV en cascada",
  formBuilderExportCascadeCsvError: "No se pudo exportar el CSV en cascada",
  formBuilderImportButton: "Importar un formulario",
  formBuilderDataOnboardingButton: "Crear desde una hoja de cálculo",
  dataOnboardingUploadHint:
    "Haga clic o arrastre aquí un archivo CSV o xlsx (hasta 10 MB y 50 000 filas)",
  dataOnboardingDrafting:
    "Redactando la propuesta. Un archivo grande puede tardar unos minutos.",
  dataOnboardingFailed: "No se pudo redactar la propuesta.",
  dataOnboardingUnits: "Unidades administrativas para añadir",
  dataOnboardingNoUnits: "No hay unidades para añadir",
  dataOnboardingUnitsOutside:
    "Estas unidades están fuera de su área administrativa. Aplicar no las añadirá ni cargará sus filas:",
  dataOnboardingParentForm: "Formulario de registro",
  dataOnboardingForms: "Formularios",
  dataOnboardingMapping: "Columna a pregunta",
  dataOnboardingKeyColumns: "Columnas clave",
  dataOnboardingValueMaps: "Correspondencias de valores",
  dataOnboardingDropped: "Columnas no cargadas",
  dataOnboardingNotes: "Notas",
  dataOnboardingQuestion: "Pregunta",
  dataOnboardingName: "Nombre",
  dataOnboardingType: "Tipo",
  dataOnboardingRequired: "Obligatorio",
  dataOnboardingOptions: "Opciones",
  dataOnboardingColumn: "Columna",
  dataOnboardingRaw: "Valor en el archivo",
  dataOnboardingReason: "Motivo",
  dataOnboardingApply: "Aplicar",
  dataOnboardingApplying:
    "Aplicando la propuesta: añadiendo unidades, creando formularios y cargando registros.",
  dataOnboardingReport: "Informe de incorporación",
  dataOnboardingLoaded: "Registros cargados",
  dataOnboardingIssues: "Filas omitidas y respuestas descartadas",
  dataOnboardingNoIssues: "Todas las filas se cargaron.",
  dataOnboardingSheet: "Hoja",
  dataOnboardingRow: "Fila",
  dataOnboardingSkipped: "Fila omitida",
  dataOnboardingDroppedAnswer: "Respuesta descartada",
  dataOnboardingBlocked: "Bloqueado",
  dataOnboardingBlockedNote:
    "Los formularios bloqueados no se aplican. Aplicar carga los demás formularios.",
  dataOnboardingNotApplied: "Formularios no aplicados",
  dataOnboardingApplyFailed: "No se pudo aplicar la propuesta.",
  dataOnboardingDownloadReport: "Descargar el informe",
  dataOnboardingDownloadFailed: "No se pudo descargar el informe.",
  dataOnboardingHistory: "Incorporaciones de datos",
  dataOnboardingFile: "Archivo",
  dataOnboardingStatus: "Estado",
  dataOnboardingCreatedBy: "Iniciada por",
  dataOnboardingCreated: "Iniciada",
  dataOnboardingUpdated: "Última actualización",
  dataOnboardingDropColumn: "Quitar",
  dataOnboardingKeepColumn: "Mantener",
  dataOnboardingReviseHint:
    "Describa cualquier otro cambio, por ejemplo: tratar Estado como una pregunta de sí/no.",
  dataOnboardingRevise: "Revisar",
  dataOnboardingRevisionFailed: "No se pudo revisar la propuesta.",
  dataOnboardingUseExisting: "Usar la unidad existente",
  dataOnboardingAddNew: "Añadir como nueva unidad",
  dataOnboardingChooseParent: "Elegir el padre",
  dataOnboardingLocationColumns:
    "Columnas de ubicación, nivel superior primero",
  dataOnboardingFirstLevel: "Nivel de la primera columna",
  dataOnboardingLocationColumn: "Columna de ubicación",
  dataOnboardingDropForm: "Quitar este formulario",
  formBuilderImportModalTitle: "Importar un formulario",
  formBuilderImportFormatLabel: "Formato",
  formBuilderImportFormatJson: "JSON (nativo)",
  formBuilderImportFormatXlsform: "XLSForm (.xlsx)",
  formBuilderImportDraggerText:
    "Haga clic o arrastre aquí un archivo de formulario",
  formBuilderImportInvalidFile: "Solo se admiten archivos .json",
  formBuilderImportInvalidFileXlsform: "Solo se admiten archivos .xlsx o .xls",
  formBuilderImportPreflightError: "No se pudo validar el archivo",
  formBuilderImportErrorsTitle: "Errores de validación",
  formBuilderImportWarningsTitle: "Advertencias",
  formBuilderImportFormLabel: "Formulario",
  formBuilderImportQuestionsLabel: "Preguntas",
  formBuilderImportGroupsLabel: "Grupos",
  formBuilderImportFormTypeLabel: "Tipo de formulario",
  formBuilderImportFormTypeRegistration: "Registro",
  formBuilderImportFormTypeMonitoring: "Seguimiento",
  formBuilderImportFormTypeRequired: "Seleccione un tipo de formulario",

  // Common UI words
  dateFromPlaceholder: "Desde",
  dateToPlaceholder: "Hasta",
  viewDetails: "Ver detalles",

  // Platform console
  platformConsole: "Consola de la plataforma",
  consoleTenants: "Espacios",
  consoleOperators: "Operadores",
  // FB-018 Form Library console
  consoleFormLibrary: "Biblioteca de formularios",
  consoleFLDescription:
    "Gestione el catálogo compartido de plantillas de formularios reutilizables.",
  consoleFLNameCol: "Plantilla",
  consoleFLCategoriesCol: "Categorías",
  consoleFLUsedCol: "Usado",
  consoleFLMonitoringCol: "Formularios de seguimiento",
  consoleFLActionsCol: "Acciones",
  consoleFLManageCategories: "Gestionar categorías",
  consoleFLPromoteButton: "Promover desde un espacio",
  consoleFLPromoteTitle: "Promover un formulario a la biblioteca",
  consoleFLEmpty: "Aún no hay plantillas",
  consoleFLDeleteButton: "Eliminar",
  consoleFLDeleteConfirm:
    "¿Quitar esta plantilla de la biblioteca? Las copias existentes no se ven afectadas.",
  consoleFLDeleteSuccess: "Plantilla eliminada de la biblioteca",
  consoleFLDeleteError: "No se pudo quitar la plantilla",
  consoleFLWorkspaceLabel: "Espacio de trabajo",
  consoleFLWorkspacePlaceholder: "Seleccione un espacio de trabajo",
  consoleFLWorkspaceRequired: "Seleccione un espacio de trabajo",
  consoleFLSourceLabel: "Formulario de origen",
  consoleFLSourcePlaceholder: "Seleccione un formulario de registro publicado",
  consoleFLSourceRequired: "Seleccione un formulario de origen",
  consoleFLCategoriesLabel: "Categorías",
  consoleFLCategoriesPlaceholder: "Asigne una o varias categorías",
  consoleFLPromoteSuccess: "Formulario promovido a la biblioteca",
  consoleFLPromoteError: "No se pudo promover el formulario",
  consoleFLPromotedFrom: "Promovido desde",
  consoleFLNewTemplate: "Nueva plantilla",
  consoleFLFromWorkspace: "Seleccionar desde un espacio existente",
  consoleFLFromScratch: "Desde cero (Creador de formularios)",
  consoleFLEditButton: "Editar en el creador",
  consoleFLAddMonitoring: "Añadir un formulario de seguimiento",
  consoleFLBack: "Volver a la biblioteca",
  consoleFLCancel: "Cancelar",
  consoleFLPreviewHeading: "Vista previa del formulario",
  consoleFLPreviewEmpty:
    "Seleccione un formulario de origen para la vista previa",
  consoleFLCategoryPlaceholder: "Nombre de la nueva categoría",
  consoleFLCategoryAdd: "Añadir",
  consoleFLCategoryEmpty: "Aún no hay categorías",
  consoleFLCategoryDeleteConfirm: "¿Eliminar esta categoría?",
  consoleFLCategoryError: "La operación sobre la categoría falló",
  closeButton: "Cerrar",
  consoleSearchTenants: "Buscar un subdominio o un nombre",
  consoleStateAll: "Todos",
  consoleStateActive: "Activo",
  consoleStateSuspended: "Suspendido",
  consoleStateDeleted: "Eliminado",
  consoleResultCount: "Resultados: {from} – {to} de {total} espacios",
  consoleTotalWorkspaces: "Espacios",
  consoleTotalUsers: "Usuarios",
  consoleTotalForms: "Formularios",
  consoleTotalDashboards: "Paneles",
  consoleTotalDatapoints: "Puntos de datos",
  consoleTotalDevices: "Dispositivos",
  consoleTotalsRow: "Total",
  consoleInspect: "Inspeccionar",
  consoleInspectFailed: "No se pudo abrir este espacio",
  consoleSuspend: "Suspender",
  consoleRestore: "Restaurar",
  consoleRename: "Renombrar",
  consoleDelete: "Eliminar",
  consoleFeatures: "Funcionalidades",
  consoleUsers: "Usuarios",
  consoleDeactivate: "Desactivar",
  consoleReactivate: "Reactivar",
  consoleInviteOperator: "Invitar a un operador",
  consoleRevoke: "Revocar",
  consoleLogo: "Logotipo",
  consoleUploadLogo: "Subir el logotipo",
  consoleRemoveLogo: "Eliminar el logotipo",
  consoleLogoUpdated: "Logotipo actualizado correctamente",
  consoleLogoRemoved: "Logotipo eliminado correctamente",
  brandingPanelTitle: "Marca del espacio",
  brandingPanelDescription:
    "Personalice el logotipo de su espacio que se muestra en la navegación y el inicio de sesión.",
  brandingPanelButton: "Gestionar la marca",
  brandingModalTitle: "Marca del espacio",
  brandingLogoLabel: "Logotipo del espacio de trabajo",
  brandingLogoHint: "Formatos admitidos: PNG, JPG, JPEG, SVG hasta 2 MB.",
  brandingUploadSuccess: "Marca actualizada correctamente",
  brandingUploadError: "No se pudo actualizar la marca",
  brandingRemoveSuccess: "Logotipo eliminado correctamente",
  brandingRemoveError: "No se pudo eliminar el logotipo",
  brandingRemoveBtn: "Eliminar el logotipo",
  brandingUploadBtn: "Subir el logotipo",
  brandingCurrentLogo: "Logotipo actual",
  brandingNoLogo: "Sin logotipo personalizado (logotipo de Akvo por defecto)",

  // Onboarding Tour
  tourWelcomeTitle: "Bienvenido a AIMS",
  tourWelcomeSubtitle:
    "¿Qué le gustaría hacer primero? Le guiamos en menos de un minuto.",
  tourGoalRecommended: "Recomendado",
  tourGoalSetupTitle: "Configurar una recopilación de datos",
  tourGoalSetupDesc: "Cree un formulario y entréguelo a su equipo de campo",
  tourGoalReviewTitle: "Revisar y aprobar datos",
  tourGoalReviewDesc: "Compruebe los envíos pendientes",
  tourGoalExploreTitle: "Explorar datos y paneles",
  tourGoalExploreDesc: "Explore, visualice y descargue los resultados",
  tourBtnShowMeHow: "Muéstreme cómo",
  tourBtnSkip: "Omitir",
  tourBtnBack: "Atrás",
  tourBtnNext: "Siguiente",
  tourStepOf: "PASO {current} DE {total}",
  tourCopyAppLink: "Copiar el enlace de la aplicación",
  tourLinkCopied: "Enlace de descarga de la aplicación copiado al portapapeles",
  tourLinkCopyError: "No se pudo copiar el enlace",
  tourSetupStep1Title: "Crear un formulario",
  tourSetupStep1Desc:
    "Añada secciones y preguntas, y luego publique, o evite la página en blanco partiendo de una plantilla lista para usar de la Biblioteca de formularios. Su equipo de campo podrá rellenarlo en cuanto se publique.",
  tourSetupStep2Title: "Entregar la aplicación a su equipo de campo",
  tourSetupStep2Desc:
    "Su equipo de campo recopila los datos sin conexión en la aplicación móvil. Comparta el enlace de descarga con ellos.",
  tourSetupStep3Title: "Siga la llegada de los envíos",
  tourSetupStep3Desc:
    "Los nuevos envíos del campo aparecen aquí. Filtre por formulario o añada uno usted mismo desde la web.",
  tourSetupFinalBtn: "Crear su primer formulario",
  tourReviewStep1Title: "Sus aprobaciones pendientes",
  tourReviewStep1Desc:
    "Los envíos que esperan su decisión llegan aquí. También puede ver lo que sus aprobadores subordinados aún tienen que revisar.",
  tourReviewStep2Title: "Revisar los envíos",
  tourReviewStep2Desc:
    "Abra Gestionar datos para explorar y filtrar los envíos. Las aprobaciones y los borradores también están en Datos.",
  tourReviewFinalBtn: "Revisar las aprobaciones pendientes",
  tourExploreStep1Title: "Explorar sus datos",
  tourExploreStep1Desc:
    "Abra Gestionar datos para explorar, filtrar y revisar los envíos por formulario y por ubicación.",
  tourExploreStep2Title: "Visualizar en un panel",
  tourExploreStep2Desc:
    "Cree un panel a partir de sus datos, publíquelo y luego manténgalo privado o compártalo públicamente.",
  tourExploreStep3Title: "Descargar sus datos",
  tourExploreStep3Desc:
    "Exporte los envíos desde Gestionar datos. Las exportaciones grandes se ejecutan en segundo plano y le esperan aquí.",
  tourExploreFinalBtn: "Crear un panel",
  tourExploreViewDataBtn: "Explorar los datos",
  tourGetHelpTitle: "Obtener ayuda en cualquier momento",
  tourGetHelpDesc:
    "¿Preguntas? Use nuestro asistente de IA en cualquier momento en la parte inferior derecha, o consulte nuestra documentación.",

  // --- Auto-added translations (previously fell back to English) ---
  actionColumn: "Acción",
  addAdmDesc: (
    <Fragment>
      Esta página le permite añadir administración a la plataforma {appName}.
    </Fragment>
  ),
  addAdministration: "Añadir administración",
  addAttachment: "Añadir adjunto",
  addAttachmentDesc: "Añadir un nuevo adjunto al lote",
  addAttributeDesc: (
    <Fragment>
      Esta página le permite añadir atributo a la plataforma {appName}.
    </Fragment>
  ),
  addAttributes: "Añadir atributo",
  addEntity: "Añadir nuevo",
  addEntityData: "Añadir nuevo",
  addEntityDesc: (
    <Fragment>
      Esta página le permite añadir entidad a la plataforma {appName}.
    </Fragment>
  ),
  addEntityTypeDesc: (
    <Fragment>
      Esta página le permite añadir tipo de entidad a la plataforma {appName}.
    </Fragment>
  ),
  addLevel: "Añadir nivel",
  addNewButton: "Añadir nuevo",
  addOptionButton: "Añadir opción",
  addOrgDesc: (
    <Fragment>
      Esta página le permite añadir organizaciones a la plataforma {appName}.
    </Fragment>
  ),
  addRole: "Añadir rol",
  addRoleDescription: (id) => (
    <Fragment>
      Esta página le permite {id ? "editar" : "añadir"} roles a la plataforma{" "}
      {appName} .
    </Fragment>
  ),
  addUserDescription: (
    <Fragment>
      Esta página le permite añadir usuarios a la plataforma {appName}. Solo
      podrá añadir usuarios para las regiones bajo su jurisdicción.
      <br />
      Una vez que haya añadido el usuario, este será notificado por correo
      electrónico para establecer su contraseña y acceder a la plataforma
    </Fragment>
  ),
  // Home Page
  admConfirmDelete: "¿Está seguro de que desea eliminar esta administración?",
  admErrDeleteTitle: "No se puede eliminar la administración",
  admErrSaveTitle: "No se puede guardar la administración",
  admFieldRequired: "La administración es obligatoria",
  AdministrationDataDownload: "Descarga de datos de administración",
  AdministrationDataUpload: "Carga de datos de administración",
  AdministrationDownloadPageHint:
    "Desmarque Rellenado previamente si solo desea una plantilla de carga",
  administrationField: "Administración",
  administrationLabel: "Administración",
  administrationUploadFailedHint:
    "No se cambió nada. Le hemos enviado por correo electrónico un archivo con las filas que necesitan corrección.",
  administrationUploadFailedTitle: "No se pudo importar su archivo",
  administrationUploadSuccessTitle:
    "Los datos de administración se han cargado correctamente",
  admLevel: "Nivel de administración",
  admName: "Nombre de administración",
  admNameRequired: "El nombre de administración es obligatorio",
  admPanelText: (
    <Fragment>
      Aquí es donde :
      <ul>
        <li>Añadir nueva administración</li>
        <li>Modificar administración existente</li>
        <li>Eliminar administración existente</li>
        <li>Carga masiva de administración</li>
      </ul>
    </Fragment>
  ),
  admParent: "Administración superior",
  admSuccessAdded: "Administración añadida",
  admSuccessDeleted: "Administración eliminada",
  admSuccessUpdated: "Administración actualizada",
  admTabTitle: "Lista administrativa",
  allData: "Todos los datos",
  allEntities: "Todas las entidades",
  approvalsTab1: "Mis pendientes",
  approvalsTab2: "Aprobaciones de subordinados",
  approvalsTab3: "Aprobado",
  approveNoteRequired:
    "Proporcione notas o comentarios para rechazar o aprobar el envío",
  approversDescription: (
    <Fragment>
      Aquí es donde puede ver los aprobadores de cada formulario enviado en
      diferentes áreas administrativas:
    </Fragment>
  ),
  // Misc
  attrConfirmDelete: "¿Está seguro de que desea eliminar este atributo?",
  attrErrDeleteTitle: "No se puede eliminar el atributo",
  attrName: "Nombre del atributo",
  attrNameRequired: "El nombre del atributo es obligatorio",
  attrSuccessAdded: "Atributo añadido",
  attrSuccessDeleted: "Atributo eliminado",
  attrSuccessUpdated: "Atributo actualizado",
  attrTabTitle: "Atributos",
  attrType: "Tipo de atributo",
  attrTypeRequired: "El tipo de atributo es obligatorio",
  backManageData: "Volver a Gestionar datos",
  backToAdmLabel: "Volver a la lista administrativa",
  backToCenterLabel: "Volver al centro de control",
  batchAttachments: "Adjuntos",
  batchFilesHint:
    "Cargue un archivo con una de las siguientes extensiones: .xlsx, .xls, .csv, .ods, .pdf, .docx, .doc",
  batchFileTypeError:
    "Tipo de archivo adjunto no válido. Cargue un archivo válido.",
  batchHintDesc:
    "La operación de fusionar conjuntos de datos no se puede deshacer, y creará un nuevo lote que requerirá la aprobación de su administrador",
  // Upload Detail
  batchHintText: "Está a punto de crear un archivo CSV de lote",
  batchName: "Nombre del lote",
  batchNoApproverMessage:
    "No se pueden crear datos de lote, porque todavía no hay aprobador.",
  batchSelectedDatasets: "Conjuntos de datos seleccionados del lote",
  browseComputer: "Explorar su equipo",
  bulkUpload: "Carga masiva",
  bulkUploadAttr: "Atributos",
  bulkUploadAttrPlaceholder: "Seleccionar atributos...",
  bulkUploadButton: "Carga masiva",
  bulkUploadCheckboxPrefilled: "Lista administrativa rellenada previamente",
  bulkUploadNoApproverMessage:
    "No se pueden subir datos, porque todavía no hay aprobador.",
  cancelButton: "Cancelar",
  channelCol: "Canal",
  checkboxSelectAll: "Seleccionar todo {{name}}",
  codeField: "Código",
  codeFieldRequired: "El código es obligatorio",
  codeLabel: "Código",
  confirmDeleteEntity: "¿Está seguro de que desea eliminar esta entidad?",
  confirmDeleteEntityData: "¿Está seguro de que desea eliminar estos datos?",
  createDraftMonitoring: "Crear borrador de datos de seguimiento",
  createNewBatch: "Crear un nuevo lote",
  dataAdministrationDownloadText: (
    <Fragment>
      Aquí es donde :
      <ul>
        <li>Descargar datos de administración</li>
      </ul>
    </Fragment>
  ),
  dataAdministrationUploadText: (
    <Fragment>
      Aquí es donde :
      <ul>
        <li>Carga masiva de datos de administración</li>
      </ul>
    </Fragment>
  ),
  dataEntitiesDownloadText: (
    <Fragment>
      Aquí es donde :
      <ul>
        <li>Descargar datos de entidades</li>
      </ul>
    </Fragment>
  ),
  dataEntitiesUploadText: (
    <Fragment>
      Aquí es donde :
      <ul>
        <li>Carga masiva de datos de entidades</li>
      </ul>
    </Fragment>
  ),
  dataExportFail: "La descarga de datos falló",
  dataExportSuccess: "Datos descargados correctamente",
  datapointCol: "Punto de datos",
  dataUploadText: (
    <Fragment>
      Aquí es donde :
      <ul>
        <li>Descargar plantilla de carga</li>
        <li>Carga masiva de nuevos datos</li>
        <li>Actualización masiva de datos existentes</li>
      </ul>
    </Fragment>
  ),
  dataUploadTitle: "Carga de datos",
  deleteAttachmentDesc: "¿Está seguro de que desea eliminar este adjunto?",
  deleteAttachmentError: "No se puede eliminar el adjunto",
  deleteAttachmentSuccess: "Adjunto eliminado correctamente",
  deleteAttachmentTitle: "Eliminar adjunto",
  deleteDraftContent: "¿Está seguro de que desea eliminar {{draftName}}?",
  deleteDraftError: "No se puede eliminar el borrador",
  deleteDraftSuccess: "Borrador eliminado correctamente",
  deleteDraftTitle: "Eliminar borrador",
  deleteOrganisationDesc: ({ count = 0 }) => (
    <span>
      Hay <b>{count} Usuarios</b> asociados con esta organización. Reasigne o
      elimine a estos usuarios antes de eliminar la organización para prevenir
      resultados inesperados
    </span>
  ),
  deleteOrganisationTitle: "Está a punto de eliminar la organización",
  // Tour
  deleteText: "Eliminar",
  deleteUserDesc: (
    <Fragment>
      El usuario ya no podrá acceder a la plataforma {appName} como
      Encuestador/Administrador, etc.
    </Fragment>
  ),
  deleteUserHint:
    "Eliminar este usuario no eliminará la(s) asociación(es) de datos",
  deleteUserTitle: "Está a punto de eliminar al usuario",
  download: "Descargar",
  downloadAppsLinkText: "o descargue usando los enlaces de abajo:",
  downloadAppsQRText: (
    <Fragment>
      Descargue la <b>aplicación {apkName}</b> usando los códigos QR de abajo
    </Fragment>
  ),
  downloadData: "Descargar datos",
  downloadHere: "descargar aquí",
  downloadReport: "Descargar informe",
  downloadReportError: "No se pudo descargar el informe",
  downloadReportSuccess: "Informe descargado correctamente",
  downloadTitle: "Descargas",
  // Add user modal notification
  draftCreatedByCol: "Creado por",
  draftFormDescription: (
    <p>
      Por favor, complete el formulario web de abajo con las respuestas
      pertinentes. Puede guardar sus respuestas y continuar más tarde, o si ha
      completado el formulario, puede enviarlo.
    </p>
  ),
  draftFormPublishConfirmContent:
    "¿Está seguro de que desea publicar este borrador? Esta acción no se puede deshacer.",
  draftFormPublishConfirmTitle: "Publicar borrador",
  draftFormPublishError: "No se pudo publicar el borrador",
  draftFormPublishSuccess: "Borrador publicado correctamente",
  draftFormSaveError: "No se pudo guardar el borrador",
  draftFormSaveSuccess: "Borrador guardado correctamente",
  draftUpdatedByPrefix: "por",
  dropFile: "Suelte su archivo aquí",
  editAdmDesc: (
    <Fragment>
      Esta página le permite editar la administración de la plataforma {appName}
      .
    </Fragment>
  ),
  editAdministration: "Editar administración",
  editAndPublishDraft: "Editar y publicar borrador",
  editAttachment: "Editar adjunto",
  editAttachmentDesc: "Reemplazar el adjunto existente por uno nuevo",
  editAttributeDesc: (
    <Fragment>
      Esta página le permite editar el atributo de la plataforma {appName}.
    </Fragment>
  ),
  editAttributes: "Editar atributo",
  editButton: "Editar",
  editEntity: "Editar entidad",
  editEntityData: "Editar datos",
  editEntityDesc: (
    <Fragment>
      Esta página le permite editar la entidad de la plataforma {appName}.
    </Fragment>
  ),
  editEntityTypeDesc: (
    <Fragment>
      Esta página le permite editar el tipo de entidad de la plataforma{" "}
      {appName}.
    </Fragment>
  ),
  editOrgDesc: (
    <Fragment>
      Esta página le permite editar las organizaciones de la plataforma{" "}
      {appName}.
    </Fragment>
  ),
  editProfile: "Editar perfil",
  editRole: "Editar rol",
  editText: "Editar",
  endOfListLabel: "Fin de la lista",
  EntitiesDataDownload: "Descarga de datos de entidades",
  EntitiesDataUpload: "Carga de datos de entidades",
  EntitiesDownloadPageHint:
    "Desmarque Precargado si solo desea una plantilla de carga",
  entitiesUploadSuccessTitle:
    "Los datos de entidades se han cargado correctamente",
  entityIsRequired: "La entidad es obligatoria",
  entityTabTitle: "Entidades",
  entityText: "Entidad",
  entityType: "Tipo de entidad",
  entityTypes: "Tipos de entidad",
  errAddOrg: "No se pudo añadir la organización",
  errDeleteCascadeText1:
    "Está asociado a otros recursos o tiene restricciones en cascada.",
  errDeleteCascadeText2:
    "Por favor, revise y resuelva las dependencias antes de intentar eliminar.",
  errDeleteEntityDataTitle: "No se pudieron eliminar los datos",
  errDeleteEntityTitle: "No se pudo eliminar la entidad",
  errorEntityData: (entity) =>
    `La administración seleccionada no tiene entidades ${entity}`,
  errorEntityNotExists: (entity) =>
    `Lamentablemente, las entidades ${entity} aún no están disponibles. Por favor, póngase en contacto con el administrador para añadirlas`,
  errorMonitoringRequiresRegistration: (monitoring, registration) =>
    `"${monitoring}" requiere que se seleccione su formulario de registro principal "${registration}"`,
  errorURL: (
    <Fragment>
      Por favor, verifique la URL de nuevo o permítanos llevarle de vuelta a la
      página de inicio de {appName}{" "}
    </Fragment>
  ),
  errSaveEntityDataTitle: "No se pudieron guardar los datos",
  errUpdateOrg: "No se pudo actualizar la organización",
  existingApproverDescription:
    "Por favor, actualice la configuración en gestionar árbol de validación o elimine estos formularios para el usuario actual",
  existingApproverTitle: "Hay aprobadores existentes para:",
  export2ExcelError: "No se pudieron exportar los datos a Excel",
  export2ExcelSuccess: "Datos exportados a Excel correctamente",
  exportEntityError: "No se pudieron exportar las entidades",
  exportPanelText: (
    <Fragment>
      <p>
        Esta página muestra su lista de solicitudes de exportación de datos.
        <br />
        Para las exportaciones que ya están generadas, haga clic en el botón
        Descargar para descargar los datos.
      </p>
    </Fragment>
  ),
  // Webform
  failed: "Fallido",
  fetchingForm: "Obteniendo formulario..",
  // Forgot Password
  fileUploadFail: "No se pudo cargar el archivo",
  fileUploadSuccess: "Archivo cargado correctamente",
  finish: "Finalizar",
  formAccess: "Acceso al formulario",
  formBuilderActivateVersionDesc:
    "Esto reemplazará el esquema activo actual. El editor se recargará.",
  formBuilderActivateVersionTitle: (v) => (
    <Fragment>{`¿Activar la versión ${v}?`}</Fragment>
  ),
  formBuilderArchiveConfirmDesc: (count) =>
    count > 0
      ? `Se eliminará de la recolección de datos (web y móvil) y ` +
        `se moverá a la pestaña Archivados. Este formulario tiene ${count} ` +
        `envío(s): se conservan. Puede restaurarlo más tarde.`
      : `Se eliminará de la recolección de datos (web y móvil) y ` +
        `se moverá a la pestaña Archivados. Puede restaurarlo más tarde.`,
  formBuilderDeleteDisabledTooltip:
    "Los formularios con envíos no se pueden eliminar; manténgalo archivado o restáurelo.",
  formBuilderDescription: (
    <Fragment>
      Aquí es donde puede crear y gestionar sus formularios. Puede :
      <ul>
        <li>Crear nuevos formularios con varios tipos de preguntas</li>
        <li>Modificar formularios existentes con control de versiones</li>
        <li>Eliminar formularios que ya no se necesitan</li>
      </ul>
    </Fragment>
  ),
  formBuilderImportCloseButton: "Cerrar",
  formBuilderImportConfirmButton: "Importar",
  formBuilderImportDraggerHint: (mb) =>
    `Solo archivos de exportación de formulario .json, hasta ${mb} MB`,
  formBuilderImportDraggerHintXlsform: (mb) =>
    `Solo archivos .xlsx o .xls, hasta ${mb} MB`,
  formBuilderImportFailed: "Error de importación",
  formBuilderImportFileTooLarge: (mb) =>
    `El archivo supera el límite de ${mb} MB`,
  formBuilderImportInProgress: "Importando formulario…",
  formBuilderImportModeCopy: "Importar como nueva copia",
  formBuilderImportModeUpdate: "Actualizar formulario existente",
  formBuilderImportNameMismatchWarning:
    "El nombre del archivo difiere del nombre del formulario existente; " +
    "asegúrese de que está actualizando el formulario correcto.",
  formBuilderImportOpenEditor: "Abrir en el editor",
  formBuilderImportParentLabel: "Formulario de registro principal",
  formBuilderImportParentPlaceholder: "Seleccione un formulario de registro",
  formBuilderImportParentRequired:
    "Un formulario de seguimiento requiere un formulario de registro principal.",
  formBuilderImportRetryButton: "Probar otro archivo",
  formBuilderImportSkippedCount: (count) =>
    `Se omitirá(n) ${count} fila(s) no admitida(s)`,
  formBuilderImportSuccess: "Formulario importado",
  formBuilderImportUpdateDesc: (count) =>
    `Ya existe un formulario con el mismo ID en este entorno` +
    (count > 0 ? ` y tiene ${count} envío(s)` : "") +
    `. Actualizarlo cambia su estructura en el lugar; los envíos se conservan.`,
  formBuilderImportUpdateTitle: (name) =>
    `¿Actualizar el formulario existente "${name}"?`,
  formBuilderImportXlsformNoticeDesc: (
    <div style={{ textAlign: "left", fontSize: 13, lineHeight: 1.5 }}>
      <p style={{ margin: "4px 0 8px 0", textAlign: "left" }}>
        Su XLSForm se importó correctamente, pero Kobo y AIMS no funcionan de
        forma idéntica y es posible que alguna lógica del formulario necesite
        ajustes manuales para coincidir completamente con el original. Por
        favor, revise las advertencias a continuación y pruebe el formulario
        antes de publicarlo.
      </p>
      <p
        style={{
          margin: "8px 0 4px 0",
          fontWeight: 600,
          textAlign: "left",
        }}
      >
        Aspectos comunes a comprobar:
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
          Campos calculados: es posible que las fórmulas deban volver a
          verificarse
        </li>
        <li style={{ marginBottom: 4 }}>
          Conteos de repetición dinámicos: los grupos repetibles controlados por
          una variable pueden necesitar configuración manual
        </li>
        <li style={{ marginBottom: 4 }}>
          Relevancia de grupo / lógica de omisión: la visibilidad condicional de
          grupos debe comprobarse dos veces
        </li>
        <li style={{ marginBottom: 4 }}>
          Preguntas de seguimiento de &quot;Otro&quot;: estas no se convierten
          automáticamente; añádalas manualmente si es necesario
        </li>
      </ul>
      <p style={{ margin: "8px 0 0 0", textAlign: "left" }}>
        Recomendamos previsualizar el formulario completo y probar un envío
        antes de que entre en funcionamiento.
      </p>
    </div>
  ),
  formBuilderImportXlsformNoticeTitle:
    "Esta importación necesita una revisión rápida",
  formBuilderMonitoringFor: (name) =>
    `Creando formulario de seguimiento para: ${name}`,
  formBuilderParentFormError:
    "Formulario principal no encontrado o no publicado. No se puede crear el formulario de seguimiento.",
  formBuilderPreviewingBanner: (v) => (
    <Fragment>{`Previsualizando la instantánea v${v}: no es el estado guardado.`}</Fragment>
  ),
  formBuilderPublishedInfo:
    "Editar un formulario publicado crea una nueva instantánea de versión. Haga clic en Publicar para activarla.",
  formBuilderSnapshotPending: (v) => (
    <Fragment>
      {`Cambios guardados como instantánea v${v}. Haga clic en Publicar para activar.`}
    </Fragment>
  ),
  formBuilderVersionActivated: (n) => (
    <Fragment>{`La versión ${n} ya está activa. Recargando el editor…`}</Fragment>
  ),
  formColumn: "Formulario",
  formDescription: (
    <p>
      Por favor, complete el formulario web a continuación con las respuestas
      pertinentes. Deberá responder todas las preguntas obligatorias antes de
      poder enviar.
      <br />
      Una vez que haya enviado un formulario web, no olvide añadirlo como parte
      de un lote y enviarlo para su aprobación.
    </p>
  ),
  // Draft Webform
  formSuccessSubTitle:
    "Tenga en cuenta que estos datos NO se han enviado para su aprobación. Si está listo para enviar los envíos para su aprobación, cree un lote y envíelo al aprobador",
  formSuccessSubTitleForAdmin:
    "Tenga en cuenta que los datos enviados por el rol de SUPER ADMIN no pasarán por el flujo de aprobación y se registrarán como datos aprobados",
  formSuccessTitle: "Gracias por el envío",
  generating: "Generando",
  helloText: "Hola",
  // User Management
  informUser: "Informar al usuario sobre los cambios",
  // Data Uploads
  initialRegistration: "Registro inicial",
  invalidInviteDesc:
    "Lorem, ipsum dolor sit amet consectetur adipisicing elit. Autem provident voluptatum cum numquam, quidem vitae, qui quam beatae exercitationem ullam perferendis! Nobis in aut fuga voluptate harum, tempore distinctio optio.",
  // Register
  isSuperAdminLabel: "¿Es superadministrador?",
  lastLoginLabel: "Último inicio de sesión",
  lastResponseCol: "Última respuesta",
  lastUpdatedCol: "Última actualización",
  latestData: "Datos más recientes",
  levelDeleteTitle: "¿Eliminar el nivel más profundo?",
  levelField: "Nivel",
  levelFieldRequired: "El nivel es obligatorio",
  levelFrozenHint:
    "Ya no se pueden añadir ni eliminar niveles porque ya existen " +
    "unidades administrativas. El cambio de nombre sigue disponible.",
  levelLabel: "Nivel",
  loadingText: "Cargando...",
  loadMoreLable: "Cargar más",
  manageAdministrativeList: "Gestionar lista administrativa",
  manageAttributes: "Gestionar atributos",
  manageAttributeText: (
    <Fragment>
      Aquí es donde gestiona los atributos según sus campos. Puede :
      <ul>
        <li>Añadir un nuevo atributo</li>
        <li>Modificar un atributo existente</li>
        <li>Eliminar un atributo existente</li>
      </ul>
    </Fragment>
  ),
  manageDataTab1: "Datos de registro",
  manageDataTab2: "Datos de seguimiento",
  manageDataTab3: "Resumen de seguimiento",
  manageDataTabList: "Lista de puntos de datos",
  manageDataTabMap: "Vista de mapa",
  manageDraftText: (
    <Fragment>
      Aquí es donde puede gestionar sus borradores. Puede:
      <ul>
        <li>Ver sus borradores guardados</li>
        <li>Editar borradores existentes</li>
        <li>Eliminar borradores existentes</li>
      </ul>
    </Fragment>
  ),
  manageDraftTitle: "Gestionar borradores",
  manageEntities: "Gestionar entidades",
  manageEntitiesText: (
    <Fragment>
      Aquí es donde gestiona las entidades según sus campos. Puede :
      <ul>
        <li>Añadir una nueva entidad</li>
        <li>Modificar una entidad existente</li>
        <li>Eliminar una entidad existente</li>
      </ul>
    </Fragment>
  ),
  manageEntityTypes: "Gestionar tipos de entidad",
  manageEntityTypesText: (
    <Fragment>
      Aquí es donde gestiona los tipos de entidad según sus campos. Puede :
      <ul>
        <li>Añadir un nuevo tipo de entidad</li>
        <li>Modificar un tipo de entidad existente</li>
        <li>Eliminar un tipo de entidad existente</li>
      </ul>
    </Fragment>
  ),
  manageLevels: "Gestionar niveles",
  manageLevelText:
    "Defina los niveles de su jerarquía administrativa, desde el nivel " +
    "superior hacia abajo. Los niveles pueden renombrarse en cualquier " +
    "momento, pero solo pueden añadirse o eliminarse mientras no existan " +
    "unidades administrativas por debajo de su nivel superior.",
  manageRoles: "Gestionar roles",
  manageRolesTitle: "Gestionar roles",
  manageUserText: (
    <Fragment>
      Aquí es donde gestiona los usuarios según sus roles, regiones y acceso a
      cuestionarios . Puede :
      <ul>
        <li>Añadir un nuevo usuario</li>
        <li>Modificar un usuario existente</li>
        <li>Eliminar un usuario existente</li>
      </ul>
    </Fragment>
  ),
  mobileAddText: "Añadir asignación",
  mobileAdmRequired: "La administración es obligatoria: una o varias",
  mobileAppText: "Aplicación móvil",
  mobileButtonAdd: "Añadir nuevo recopilador de datos",
  mobileButtonSave: "Guardar",
  mobileConfirmDelete: "¿Está seguro de que desea eliminar esta asignación?",
  mobileEditText: "Editar asignación",
  mobileErrDelete: "No se puede eliminar la asignación",
  mobileFormsRequired: "El formulario es obligatorio: uno o varios",
  mobileLabelAdm: "Administraciones",
  mobileLabelForms: "Formularios",
  mobileLabelName: "Nombre",
  mobileLevelRequired: "El nivel es obligatorio",
  mobileNameRequired: "El nombre es obligatorio",
  mobilePanelAddDesc: (
    <Fragment>
      Esta página le permite añadir recopiladores de datos móviles a la
      plataforma {appName} .
    </Fragment>
  ),
  mobilePanelEditDesc: (
    <Fragment>
      Esta página le permite editar recopiladores de datos móviles en la
      plataforma {appName} .
    </Fragment>
  ),
  mobilePanelText: (
    <Fragment>
      Aquí es donde usted :
      <ul>
        <li>Añade un nuevo recopilador de datos móviles</li>
        <li>Modifica un recopilador de datos móviles existente</li>
        <li>Elimina un recopilador de datos móviles existente</li>
      </ul>
    </Fragment>
  ),
  mobilePanelTitle: "Recopiladores de datos móviles",
  mobileSelectForms: "Seleccionar formularios...",
  mobileSuccessAdded: "Asignación móvil añadida",
  mobileSuccessUpdated: "Actualización de asignación móvil",
  monitoringDataDescription: (
    <Fragment>
      Aquí es donde usted :
      <ul>
        <li>
          Obtiene la lista de formularios que se recopilaron para este punto de
          datos (nuevo y actualización)
        </li>
        <li>Edita los datos de seguimiento</li>
      </ul>
    </Fragment>
  ),
  monitoringDataTitle: "Datos de seguimiento",
  moreCount: "+{{count}} más",
  moreItems: "Más elementos",
  nameCol: "Nombre",
  nameField: "Nombre",
  nameFieldRequired: "El nombre es obligatorio",
  nameLabel: "Nombre",
  next: "Siguiente",
  notAssigned: "Sin asignar",
  notesFeedback: "Notas y comentarios",
  // Export Data
  noText: "No",
  notifyError: "Se produjo un error",
  optionsField: "Opciones",
  organisationDeleteFail: "No se pudo eliminar la organización",
  organisationsLoadFail: "No se pudieron cargar las organizaciones",
  orgPanelButton: "Gestionar organización",
  orgPanelText: (
    <Fragment>
      Aquí es donde usted :
      <ul>
        <li>Añade una nueva organización</li>
        <li>Modifica una organización existente</li>
        <li>Elimina una organización existente</li>
      </ul>
    </Fragment>
  ),
  orgPanelTitle: "Gestionar organización",
  orgTabTitle: "Organizaciones",
  panelApprovalsDesc: (
    <Fragment>
      Aquí es donde usted :
      <ul>
        <li>
          Ve las aprobaciones de datos pendientes que esperan su aprobación{" "}
        </li>
        <li>Ve las aprobaciones pendientes de sus aprobadores subordinados</li>
        <li>Asigna aprobadores subordinados</li>
      </ul>
    </Fragment>
  ),
  // Upload Data
  passwordCriteriaError: "Criterios de contraseña incorrectos",
  passwordMatchError: "¡Las dos contraseñas que ha introducido no coinciden!",
  // Log in
  passwordRule1: "Carácter en minúscula",
  passwordRule2: "Números",
  passwordRule3: "Carácter especial ( -._!`'#%&,:;<>=@{}~$()*+/?[]^|] )",
  passwordRule4: "Carácter en mayúscula",
  passwordRule5: "Sin espacios en blanco",
  passwordRule6: "Mínimo 8 caracteres",
  passwordUpdateSuccess: "Contraseña actualizada correctamente",
  prev: "Anterior",
  profileDes:
    "Esta página muestra la configuración actual de su usuario. También muestra las actividades más importantes para la configuración actual de su usuario",
  profileLabel: "Perfil",
  questionCol: "Pregunta",
  questionnairesLabel: "Cuestionarios",
  questionnaireText: "Cuestionario",
  recentActivityCol: "Actividad reciente",
  regionCol: "Región",
  registrationView: "Registro",
  rejectText: "Rechazar",
  requiredError: "{{field}} es obligatorio",
  responseCol: "Respuesta",
  roleAccess: "Acceso del rol",
  roleAccessRequired: "El acceso del rol es obligatorio",
  roleAdmLevel: "Nivel de administración",
  roleAdmLevelPlaceholder: "Seleccione un nivel de administración...",
  roleAdmLevelRequired: "El nivel de administración es obligatorio",
  roleConfirmDelete: "¿Está seguro de que desea eliminar {roleName}?",
  roleDeleteTitle: "Está a punto de eliminar el rol",
  roleDescription: "Descripción del rol",
  roleErrorAdd: "No se pudo añadir el rol",
  roleErrorUpdate: "No se pudo actualizar el rol",
  roleFeatures: "Funciones del rol",
  roleLabel: "Rol",
  roleName: "Nombre del rol",
  roleNameRequired: "El nombre del rol es obligatorio",
  rolesLabel: "Rol(es)",
  rolesRequired: "Seleccione al menos un rol",
  roleSuccessAdded: "Rol añadido",
  roleSuccessUpdated: "Rol actualizado",
  roleTotalUsers: "Total de usuarios",
  saveButton: "Guardar",
  saveEditButton: "Guardar cambios",
  searchEntity: "Introduzca un nombre...",
  searchEntityType: "Introduzca un nombre...",
  searchNameOrCode: "Introduzca un nombre o código...",
  searchPlaceholder: "Buscar...",
  selectChildForms: "Seleccione formularios de seguimiento",
  selectEntity: "Seleccione una entidad...",
  selectForm: "Seleccione un formulario",
  selectFormPlaceholder: "Seleccionar formulario",
  selectIndicatorPlaceholder: "Seleccionar indicador",
  selectLevel: "Seleccione un nivel...",
  selectMonitoringFormPlaceholder: "Seleccionar formulario de seguimiento",
  selectOne: "Seleccione uno...",
  selectQuestionPlaceholder: "Seleccionar pregunta",
  selectRole: "Seleccione un rol...",
  selectRowsToDownload: "Seleccione las filas que desea descargar",
  selectText: "Seleccionar...",
  selectType: "Seleccione un tipo...",
  selectViewMode: "Seleccionar vista",
  sendNewRequest: "Notificar al aprobador",
  settingsDescriptionPanel:
    "Esta página permite al Superadministrador mantener las listas maestras críticas del sistema.",
  // Approvals
  showAllQuestionsSwitch: "Mostrar todas las preguntas",
  showPendingUsers: "Mostrar usuarios pendientes",
  submissionComment: "Comentario del envío",
  submissionDateCol: "Fecha de envío",
  submissionsText: "Envíos",
  successAddedEntity: "Entidad añadida",
  successAddedOrg: "Organización añadida",
  successDataUpdated: "Datos actualizados",
  successDeletedEntity: "Entidad eliminada",
  successEntityDataAdded: "Datos de la entidad añadidos",
  successEntityDataDeleted: "Datos de la entidad eliminados",
  successEntityDataUpdated: "Datos de la entidad actualizados",
  successUpdatedEntity: "Entidad actualizada",
  successUpdatedOrg: "Organización actualizada",
  templateDownloadAdministrationHint: "Si todavía no tiene una plantilla, ",
  templateDownloadEntityHint: "Si todavía no tiene una plantilla de entidad, ",
  templateDownloadHint: "Si todavía no tiene una plantilla, descargue",
  templateFetchFail: "No se pudo obtener la plantilla",
  totalMonitoring: "Total de seguimiento",
  tourApprovals: "Placeat impedit iure quaerat neque sit quasi",
  tourApprovers: "Magni provident aliquam harum cupiditate iste",
  tourControlCenter: "Lorem ipsum dolor sit, amet consectetur adipisicing elit",
  tourDataUploads: "Velit amet omnis dolores. Ad eveniet ex beatae dolorum",
  tourDataUploadsPanel:
    "Velit amet omnis dolores. Ad eveniet ex beatae dolorum",
  //downloads
  tourExports: "Velit amet omnis dolores. Ad eveniet ex beatae dolorum",
  tourManageData: "Lorem ipsum dolor sit, amet consectetur adipisicing elit",
  tourUserManagement: "Magni provident aliquam harum cupiditate iste",
  updateDataButton: "Actualizar datos",
  updateDataError: "No se pudieron actualizar los datos",
  updateExisting: "Actualizar datos existentes",
  uploadAnotherFileLabel: "Subir otro archivo",
  uploadAttachmentsComment: "Añada un comentario para el adjunto",
  uploadAttachmentsError: "No se pudieron subir los adjuntos",
  uploadAttachmentsRequired: "Suba al menos un archivo adjunto",
  uploadAttachmentsSuccess: "Adjuntos subidos correctamente",
  uploadDataLabel: "Suba sus datos",
  uploading: "Subiendo..",
  uploadMasterDataLabel: "Suba sus datos",
  uploadNotReadyHint:
    "Defina primero sus niveles administrativos: dé nombre al nivel superior y añada al menos un nivel por debajo. Puede hacerlo en Datos maestros → Niveles.",
  uploadsTab1: "Envío pendiente",
  uploadsTab2: "Aprobación pendiente",
  uploadsTab3: "Aprobado",
  uploadTab1: "Resumen de datos",
  uploadTab2: "Datos sin procesar",
  uploadText: "Subir",
  uploadThankyouText: (
    <Fragment>
      Gracias por subir el archivo de datos. Tenga en cuenta que los datos serán
      validados por el sistema . Se le notificará por correo electrónico si los
      datos no superan las pruebas de validación . También se adjuntarán los
      errores de validación que deben corregirse. Si no hay errores de
      validación , los datos se enviarán para su verificación, aprobación y
      certificación
    </Fragment>
  ),
  userAssociations: "Este usuario tiene las siguientes asociaciones de datos",
  userCol: "Usuario",
  userDeleteFail: "No se pudo eliminar el usuario",
  userFirstName: "Nombre",
  userLastName: "Apellido",
  userOrganisation: "Organización",
  userPhoneNumber: "Número de teléfono",
  usersLoadFail: "No se pudieron cargar los usuarios",
  viewAttachment: "Ver adjunto",
  viewFullContext: "Ver contexto completo",
  viewText: "Ver",
  webformText: "Formulario web",
  yesText: "Sí",
};

export default es;
