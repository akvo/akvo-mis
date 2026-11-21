import React, { Fragment } from "react";
import { appName, apkName } from "../app-name";

// French UI strings. Only the keys that differ from English; the
// assembler (../ui.js) fills the rest from English.
const fr = {
  // Sidebar Menu Labels
  menuUsers: "Utilisateurs",
  menuControlCenter: "Centre de contrôle",
  menuManagePlatformUsers: "Gérer les utilisateurs de la plateforme",
  menuValidationTree: "Arbre de validation",
  menuManageMobileUsers: "Gérer les utilisateurs mobiles",
  menuManageRoles: "Gérer les rôles",
  menuMasterData: "Données de référence",
  menuAdministrativeList: "Liste administrative",
  menuLevels: "Niveaux",
  menuAttributes: "Attributs",
  menuEntities: "Entités",
  menuEntityTypes: "Types d'entités",
  menuOrganisations: "Organisations",
  menuData: "Données",
  menuManageData: "Gérer les données",
  menuPendingSubmissions: "Soumissions",
  menuApprovals: "Approbations",
  menuDownloads: "Téléchargements",
  menuManageDraft: "Gérer les brouillons",
  menuDownloadApps: "Télécharger l'application",
  menuDocumentation: "Documentation",
  menuProductTour: "Faire une visite guidée",
  menuFormBuilder: "Générateur de formulaires",
  // FB-018 Form Library
  formLibraryTitle: "Bibliothèque de formulaires",
  formLibraryDescription:
    "Parcourez des modèles de formulaires prêts à l'emploi et créez un nouveau formulaire à partir de l'un d'eux en un clic.",
  formLibrarySearchPlaceholder: "Rechercher des modèles",
  formLibraryAllCategories: "Toutes les catégories",
  formLibraryUncategorized: "Sans catégorie",
  formLibraryUsedCount: "Utilisé",
  formLibraryMonitoringLabel: "formulaire(s) de suivi",
  formLibraryPreviewButton: "Aperçu",
  formLibraryUseButton: "Utiliser ce formulaire",
  formLibraryViewOnly: "Lecture seule",
  formLibraryEmptyText: "Aucun modèle disponible",
  formLibraryPreviewTitle: "Aperçu du modèle",
  formLibraryRegistrationTab: "Enregistrement",
  formLibraryMonitoringTab: "Suivi",
  formLibraryUseSuccess:
    "Modèle copié dans votre espace de travail en tant que nouveau brouillon.",
  formLibraryUseError: "Échec de l'utilisation de ce modèle",
  menuDashboards: "Tableaux de bord",
  menuSettings: "Paramètres",

  // Dashboards
  dashboardListTitle: "Mes tableaux de bord",
  dashboardListSubtitle:
    "Créez et gérez vos tableaux de bord de données personnalisés.",
  dashboardNew: "Nouveau tableau de bord",
  dashboardEmptyTitle: "Aucun tableau de bord pour le moment",
  dashboardEmptyDesc:
    "Créez votre premier tableau de bord personnalisé pour visualiser les données de vos formulaires.",
  dashboardCreateTitle: "Créer un tableau de bord",
  dashboardCreateHint:
    "Donnez-lui un nom, puis choisissez le formulaire d'enregistrement dont ce tableau de bord affichera les données.",
  dashboardCreateBtn: "Créer le tableau de bord",
  dashboardNameLabel: "Nom du tableau de bord",
  dashboardNameRequired: "Veuillez saisir un nom de tableau de bord",
  dashboardFormLabel: "Source de données",
  dashboardFormExtra:
    "Ce tableau de bord affichera les données de ce formulaire et de ses formulaires de suivi. Cela ne pourra pas être modifié ultérieurement.",
  dashboardFormRequired: "Veuillez sélectionner un formulaire d'enregistrement",
  dashboardFormPlaceholder: "Sélectionnez un formulaire d'enregistrement",
  dashboardNoForms: "Aucun formulaire d'enregistrement publié disponible.",
  dashboardGoFormBuilder:
    "Accédez au Générateur de formulaires pour créer et publier un formulaire.",
  dashboardForbidden:
    "Vous n'avez plus l'autorisation d'effectuer cette action.",
  dashboardCreated: "Tableau de bord créé",
  dashboardAiApplyWarning:
    "Tableau de bord créé, mais certains widgets d'IA n'ont pas pu être appliqués.",
  dashboardDeleted: "Tableau de bord supprimé",
  dashboardDuplicated: "Tableau de bord dupliqué",
  dashboardDeleteConfirm: "Supprimer ce tableau de bord ?",
  dashboardSlugConflict:
    "Un tableau de bord avec un nom similaire existe déjà. Veuillez choisir un nom différent.",
  dashboardSaved: "Tableau de bord enregistré",
  dashboardPublished: "Tableau de bord publié",

  // Viewer and preview
  dashboardViewEmpty: "Ce tableau de bord n'a pas encore de widgets.",
  dashboardNotFound: "Le tableau de bord est vide",
  dashboardNotFoundHint:
    "Ce tableau de bord n'a pas encore été publié ou a peut-être été supprimé.",
  dashboardEdit: "Modifier le tableau de bord",
  dashboardPreview: "Aperçu",
  dashboardBackToEditing: "Retour à l'édition",
  dashboardWidgetError: "Impossible de charger ce widget",
  dashboardWidgetRetry: "Réessayer",
  dashboardWidgetNoData: "Aucune donnée disponible",
  dashboardWidgetNoDataFiltered:
    "Aucune donnée trouvée pour les filtres actuels",
  dashboardWidgetQuestionGone: "La question de ce widget n'existe plus.",
  dashboardWidgetFormGone: "Le formulaire de ce widget n'existe plus.",

  // Export
  dashboardExport: "Exporter",
  dashboardExportPng: "Image PNG",
  dashboardExportPdf: "Document PDF",
  dashboardExportFailed: "Impossible d'exporter ce tableau de bord",
  dashboardFilterPeriod: "Date",
  dashboardFilterAllLocations: "Tous les emplacements",
  dashboardFilterLocation: "Emplacement",
  dashboardExportFiltered: "Filtré par",
  dashboardFilters: "Filtres",
  dashboardFiltersActive: "actif(s)",
  dashboardFiltersApply: "Appliquer",
  dashboardFiltersClear: "Tout effacer",
  dashboardFiltersHowTo:
    "Cochez des options pour n'afficher que celles-ci. Les données sans réponse à une question filtrée sont masquées.",
  dashboardFiltersMatch: "Afficher les données correspondant à",
  dashboardFiltersMatchAll: "Tous les filtres",
  dashboardFiltersMatchAny: "Au moins un filtre",
  dashboardFiltersRemove: "Retirer le filtre",
  dashboardFiltersMore: "autres filtres",
  dashboardFiltersTooMany:
    "Trop d'options cochées : {max} au plus en tout. Décochez-en.",
  dashboardFilterQuestions: "Questions de filtre",
  dashboardFilterChoose: "Choisir des questions…",
  dashboardFilterScope: "Réponses de",
  dashboardFilterSearch: "Rechercher par question, nom ou groupe",
  dashboardFilterNoMatch: "Aucune question ne correspond",
  dashboardFilterSelected: "sélectionnée(s)",
  dashboardFilterAllForms: "Tous les formulaires",
  dashboardFilterSuggested: "Utilisées dans vos widgets",
  dashboardFilterRemove: "Retirer",
  dashboardFilterCovers: "Couvre :",
  dashboardFilterOnlyOn: "seulement dans",
  dashboardDateQuestion: "Date à filtrer",
  dashboardDateSubmission: "Date de soumission",
  dashboardDateSaved: "Question de date enregistrée",
  dashboardFilterGone: "(n'est plus dans le formulaire)",

  // Visibility
  dashboardVisibilityTitle: "Tableau de bord public",
  dashboardVisibilityHintOn:
    "Tout le monde peut l'ouvrir sans se connecter, et il est listé dans le menu Tableau de bord pour chaque visiteur. Prend effet immédiatement — pas besoin d'enregistrer.",
  dashboardVisibilityHintDraft:
    "Publiez d'abord ce tableau de bord. Seul un tableau de bord publié peut être rendu public.",
  dashboardMakePublicTitle: "Rendre ce tableau de bord public ?",
  dashboardMakePublicBody:
    "Toute personne disposant du lien pourra ouvrir ce tableau de bord sans se connecter, et il sera répertorié dans le menu Tableaux de bord pour chaque visiteur de cet espace.",
  dashboardMakePublicRawData:
    "Ce tableau de bord comprend un tableau et une carte. Les visiteurs publics verront les lignes de soumission individuelles et l'emplacement de chaque point enregistré, pas seulement les totaux.",
  dashboardMakePublicOk: "Rendre public",
  dashboardMadePublic: "Le tableau de bord est maintenant public",
  dashboardMadePrivate: "Le tableau de bord est maintenant privé",
  dashboardVisibilityPublic: "Public",
  dashboardVisibilityPrivate: "Privé",

  // Embedded dashboards
  dashboardKindLabel: "Quel est ce tableau de bord ?",
  dashboardKindWidgets: "Le construire ici",
  dashboardKindWidgetsHint:
    "Composez des graphiques et des tableaux à partir de vos propres données de formulaire.",
  dashboardKindEmbed: "Intégrer un tableau de bord externe",
  dashboardKindEmbedHint:
    "Afficher un rapport publié par Power BI, Tableau, Looker Studio ou un autre outil.",
  dashboardEmbedLabel: "Code d'intégration",
  dashboardEmbedPlaceholder:
    "Collez le code d'intégration depuis la boîte de dialogue Partager de votre outil de rapport",
  dashboardEmbedRequired: "Veuillez coller le code d'intégration",
  dashboardEmbedHint:
    "Collé exactement comme indiqué, la taille provient du snippet : donnez-lui une largeur et une hauteur pour l'afficher à cette taille, centré.",
  dashboardEmbedBadge: "Externe",
  dashboardEmbedUnavailable:
    "Le contenu externe de ce tableau de bord ne peut pas être affiché car les tableaux de bord intégrés ne sont pas disponibles ici.",
  preview: "Aperçu",
  publish: "Publier",
  published: "Publié",
  draft: "Brouillon",

  // Error messages
  error: "Erreur",
  errorPageNA: "Oups, cette page n'est pas disponible",
  errorAuth: "Vous n'êtes pas autorisé à accéder à cette page",
  errorUnknown: "Une erreur inconnue s'est produite",
  errorVerifyCreds:
    "Veuillez vérifier vos identifiants pour la ressource demandée",
  backHome: "Retour à la page d'accueil",
  errorDataLoad: "Impossible de charger les données",
  errorUserLoad: "Échec du chargement des données utilisateur",
  errorFileList: "Impossible de récupérer la liste des fichiers",
  errorSomething: "Une erreur s'est produite",
  errorMandatoryFields: "Veuillez répondre à toutes les questions obligatoires",
  errorFileUpload: "Impossible de téléverser le fichier",

  // Header Links
  controlCenter: "Centre de contrôle",
  myProfile: "Mon profil",
  settings: "Paramètres système",
  signOut: "Se déconnecter",
  dashboards: "Tableaux de bord",
  reports: "Rapports",
  newsEvents: "Actualités et événements",
  login: "Connexion",

  // Log in / Auth
  loginTitle: "Content de vous revoir",
  loginAccountDetails: "Veuillez saisir les informations de votre compte",
  loginTroublePrefix:
    "Vous avez des difficultés à accéder à la plateforme ? Veuillez",
  loginContactLink: "nous contacter",
  userEmail: "Adresse e-mail",
  loginEmailPlaceholder: "E-mail",
  loginPasswordLabel: "Mot de passe",
  loginPasswordPlaceholder: "Mot de passe",
  usernameRequired: "Veuillez saisir votre nom d'utilisateur",
  passwordRequired: "Veuillez saisir votre mot de passe",
  recoverPassword: "Récupérer le mot de passe",
  createAccount: "Créer un compte",
  loginNotActivated: "Ce compte n'a pas encore été activé",
  loginResendActivation: "Renvoyer l'e-mail d'activation",
  contactAdmin: "Veuillez contacter l'administrateur",
  formAssignmentError:
    "Vous n'avez aucun formulaire attribué, veuillez contacter l'administrateur",
  forgotTitle: "Réinitialiser votre mot de passe",
  forgotDesc:
    "Saisissez l'e-mail associé à votre compte et nous vous enverrons un e-mail avec les instructions pour réinitialiser votre mot de passe",
  instructionsMailed: "Instructions envoyées avec succès",
  sendInstructions: "Envoyer les instructions",
  loginLoadingTex: (
    <Fragment>
      Vérification
      <br />
      <small>Veuillez patienter..</small>
    </Fragment>
  ),
  welcomeShort: (
    <Fragment>
      Bienvenue sur la plateforme <b>{appName}</b>
    </Fragment>
  ),
  resetHint: (
    <Fragment>
      Veuillez définir votre mot de passe pour la plateforme.
      <br />
      Votre mot de passe doit comporter :
    </Fragment>
  ),
  invalidInviteTitle: "Code d'invitation non valide",
  // Activation / vérification de l'e-mail
  activateVerifiedTitle: "E-mail vérifié",
  activateVerifiedDesc:
    "Votre compte est actif. Il reste une étape rapide : parlez-nous de votre projet.",
  activateContinueSetup: "Continuer la configuration →",
  activateVerifying: "Vérification de votre e-mail…",
  activateCheckInboxTitle: "Consultez votre boîte de réception",
  activateCheckInboxDesc:
    "Si ce compte doit encore être activé, un nouveau lien est en route.",
  activateErrorTitle: "Nous n'avons pas pu vérifier votre lien",
  activateErrorDesc:
    "Un problème est survenu lors de la connexion au serveur. Votre lien est probablement valide ; réessayez dans un instant.",
  activateTryAgain: "Réessayer",
  activateExpiredTitle: "Ce lien a expiré",
  activateExpiredDesc:
    "Les liens d'activation sont valables 7 jours. Demandez-en un nouveau et nous vous l'enverrons par e-mail immédiatement.",
  activateEmailPlaceholder: "vous@organisation.org",
  backToLogin: "Retour à la connexion",
  couldNotSendEmail: "Impossible d'envoyer l'e-mail",
  // Configuration / configuration du projet
  configureStep1: "Inscription",
  configureStep2: "Vérifier l'e-mail",
  configureStep3: "Configurer le projet",
  configureStep4: "Tableau de bord",
  configureTitle: "Configurez votre projet",
  configureSubtitle:
    "Ceci nomme votre hiérarchie administrative. Vous pourrez ajouter des niveaux plus profonds ensuite ; ces deux noms de niveau supérieur se définissent une seule fois ici.",
  configureFirstName: "Prénom",
  configureFirstNamePlaceholder: "Jeanne",
  configureLastName: "Nom",
  configureLastNamePlaceholder: "Dupont",
  configureRequired: "Obligatoire",
  configureTopLevelName: "Nom du niveau supérieur",
  configureTopLevelExtra:
    "L'étiquette de votre niveau administratif le plus élevé, p. ex. Pays, National ou Région. Pas un lieu, mais un niveau.",
  configureTopLevelRequired: "Donnez un nom à votre niveau supérieur.",
  configureTopLevelPlaceholder: "Pays",
  configureTopUnitName: "Nom de l'unité supérieure",
  configureTopUnitExtra:
    "Votre unique unité supérieure à ce niveau, p. ex. Kenya. Tout ce que vous importerez ensuite se place sous elle.",
  configureTopUnitRequired: "Donnez un nom à votre unité supérieure.",
  configureTopUnitPlaceholder: "Kenya",
  configureLogoLabel: "Logo de l'espace de travail",
  configureLogoExtra:
    "Facultatif. PNG, JPG ou JPEG jusqu'à 2 Mo. Affiché dans la navigation supérieure et la page de connexion.",
  configureUploadLogo: "Téléverser le logo",
  configureLogoUploadError: "Impossible de téléverser le logo",
  configurePreview: "Aperçu : voici la hiérarchie que vous créez :",
  configureLevel0Tag: "Niveau 0",
  configureTopUnitHint: "└ unité supérieure",
  configureFinish: "Terminer la configuration",
  configureSaveError: "Impossible d'enregistrer votre espace de travail",
  configureDoneTitle: "Tout est prêt",
  configureWelcome: "Bienvenue",
  configureReadyWith: "Votre espace de travail est prêt avec",
  configureAtTop: "au sommet. Ensuite, ajoutez les niveaux en dessous.",
  configureContinue: "Continuer vers la gestion des niveaux →",

  // Reports
  noTemplate: "Aucun modèle trouvé",
  chooseTemplate: "Choisir un modèle",
  backBtn: "Retour",
  printBtn: "Imprimer",

  // Events
  upcomingEventText: "Événements à venir",
  eventTitle: "Actualités et événements",
  latestUpdateText: "Dernières mises à jour",

  // Charts
  showEmpty: "Afficher les valeurs vides",
  noInformationAvailable: "Aucune information disponible",

  // User Management
  manageDataValidationSetup: "Arbre de validation",
  manageUsers: "Gérer les utilisateurs",
  addUser: "Ajouter un utilisateur",
  addNewUser: "Ajouter un nouvel utilisateur",
  editUser: "Modifier l'utilisateur",
  updateUser: "Mettre à jour l'utilisateur",
  manageRoleText: (
    <Fragment>
      C&apos;est ici que vous gérez les rôles selon leurs champs. Vous pouvez :
      <ul>
        <li>Ajouter un nouveau rôle</li>
        <li>Modifier un rôle existant</li>
        <li>Supprimer un rôle existant</li>
      </ul>
    </Fragment>
  ),

  // Organisation Management
  manageOrganisations: "Gérer les organisations",
  addOrganisation: "Ajouter une organisation",
  editOrganisation: "Modifier l'organisation",
  updateOrganisation: "Mettre à jour l'organisation",

  // Validations
  valFirstName: "Le prénom est requis",
  valLastName: "Le nom de famille est requis",
  valEmail: "Veuillez entrer une adresse e-mail valide",
  valPhone: "Le numéro de téléphone est requis",
  valRole: "Veuillez sélectionner un rôle",
  valOrganization: "Veuillez sélectionner une organisation",
  valOrgName: "Le nom de l'organisation est requis",
  valOrgAttributes: "Veuillez sélectionner des attributs",

  // Control Center
  manageDataTitle: "Gérer les données",
  manageDataButton: "Gérer les données",
  newSubmissionBtn: "Ajouter une nouvelle soumission",
  finishSubmissionBtn: "Terminer et aller à Gérer les données",
  finishSubmissionBatchBtn: "Terminer et aller au lot",
  noFormText: "Aucune donnée",
  noFormSelectedText: "Aucun formulaire sélectionné",
  ccDescriptionPanel:
    "Accès instantané à toutes les pages d'administration et aux panneaux de synthèse pour l'approbation des données.",
  manageDataText: (
    <Fragment>
      C&apos;est ici que vous pouvez :
      <ul>
        <li>Ajouter de nouvelles données via des formulaires web</li>
        <li>Importer des données en masse via des tableurs</li>
        <li>Télécharger des données</li>
      </ul>
    </Fragment>
  ),

  // Form Builder
  formBuilderCreateTitle: "Créer un formulaire",
  formBuilderEditTitle: "Modifier le formulaire",
  formBuilderDraftRestored:
    "Nous avons récupéré votre travail précédent — vérifiez-le avant d'enregistrer.",
  formBuilderBackToSaved: "Retour à l'état enregistré",
  formBuilderSaveSuccess: "Formulaire enregistré",
  formBuilderSaveError: "Échec de l'enregistrement du formulaire",
  formBuilderCreateSuccess: "Formulaire créé avec succès",
  formBuilderCreateError: "Échec de la création du formulaire",
  formBuilderPublishSuccess: "Formulaire publié",
  formBuilderPublishError: "Échec de la publication du formulaire",
  formBuilderUnpublishSuccess: "Formulaire dépublié",
  formBuilderUnpublishError: "Échec de la dépublication du formulaire",
  formBuilderActivateError: "Échec de l'activation de la version",
  formBuilderPreviewError: "Échec du chargement de la version",
  formBuilderVersionHistoryTitle: "Historique des versions",
  formBuilderVersionsButton: "Versions",
  formBuilderRefreshButton: "Actualiser",
  formBuilderVersionHistoryEmpty: "Aucune version publiée pour le moment",
  formBuilderNameCol: "Nom",
  formBuilderTypeCol: "Type",
  formBuilderStatusCol: "Statut",
  formBuilderLastUpdatedCol: "Dernière mise à jour",
  formBuilderVersionCol: "Version",
  formBuilderPublishedAtCol: "Publié le",
  formBuilderPublishedByCol: "Publié par",
  formBuilderActionsCol: "Actions",
  formBuilderActiveTag: "Actif",
  formBuilderPreviewButton: "Aperçu",
  formBuilderActivateButton: "Activer",
  formBuilderSetActiveButton: "Définir comme actif",
  formBuilderPublishButton: "Publier",
  formBuilderUnpublishTitle: "Dépublier ce formulaire ?",
  formBuilderUnpublishDesc:
    "Le formulaire ne sera plus disponible pour la collecte de données.",
  formBuilderUnpublishButton: "Dépublier",
  formBuilderStatusPublished: "Publié",
  formBuilderStatusDraft: "Brouillon",
  formBuilderResetDraft: "Charger depuis le serveur",
  formBuilderCreateMonitoringButton: "Créer un formulaire de suivi",
  formBuilderCreateButton: "Créer un nouveau formulaire",
  formBuilderRegistrationType: "Enregistrement",
  formBuilderMonitoringType: "Suivi",
  formBuilderTabActive: "Actif",
  formBuilderTabArchived: "Archivé",
  formBuilderSearchPlaceholder: "Rechercher par nom",
  formBuilderFilterStatusAll: "Tous les statuts",
  formBuilderFilterTypeAll: "Tous les types",
  formBuilderArchivedAtCol: "Archivé",
  formBuilderDuplicateButton: "Dupliquer",
  formBuilderArchiveButton: "Archiver",
  formBuilderRestoreButton: "Restaurer",
  formBuilderDeleteButton: "Supprimer définitivement",
  formBuilderPublishConfirmTitle: "Publier ce formulaire ?",
  formBuilderPublishConfirmDesc:
    "Il sera disponible pour la collecte de données.",
  formBuilderArchiveConfirmTitle: "Archiver ce formulaire ?",
  formBuilderRestoreConfirmTitle: "Restaurer ce formulaire ?",
  formBuilderRestoreConfirmDesc:
    "Il reviendra sous forme de brouillon ; republiez-le pour reprendre la collecte de données.",
  formBuilderDeleteConfirmTitle: "Supprimer définitivement ce formulaire ?",
  formBuilderDeleteConfirmDesc: "Cette action est irréversible.",
  formBuilderArchiveSuccess: "Formulaire archivé",
  formBuilderArchiveError: "Échec de l'archivage du formulaire",
  formBuilderRestoreSuccess: "Formulaire restauré",
  formBuilderRestoreError: "Échec de la restauration du formulaire",
  formBuilderDuplicateSuccess: "Formulaire dupliqué",
  formBuilderDuplicateError: "Échec de la duplication du formulaire",
  formBuilderDeleteSuccess: "Formulaire définitivement supprimé",
  formBuilderDeleteError: "Échec de la suppression du formulaire",
  formBuilderStatusArchived: "Archivé",
  formBuilderEmptyText: "Aucun formulaire trouvé",
  formBuilderExportButton: "Exporter",
  formBuilderExportError: "Échec de l'exportation du formulaire",
  formBuilderExportXlsformButton: "Exporter XLSForm",
  formBuilderExportXlsformError: "Échec de l'exportation XLSForm",
  formBuilderExportXlsformWarningTitle: "Avertissements d'exportation XLSForm",
  formBuilderExportCascadeCsvButton: "Exporter le CSV Cascade",
  formBuilderExportCascadeCsvError: "Échec de l'exportation du CSV Cascade",
  formBuilderImportButton: "Importer un formulaire",
  formBuilderDataOnboardingButton: "Créer depuis un tableur",
  dataOnboardingUploadHint:
    "Cliquez ou déposez ici un fichier CSV ou xlsx (10 Mo et 50 000 lignes au plus)",
  dataOnboardingDrafting:
    "Rédaction de la proposition. Un gros fichier peut prendre quelques minutes.",
  dataOnboardingFailed: "La proposition n'a pas pu être rédigée.",
  dataOnboardingUnits: "Unités administratives à ajouter",
  dataOnboardingNoUnits: "Aucune unité à ajouter",
  dataOnboardingUnitsOutside:
    "Ces unités sont hors de votre zone administrative. L'application ne les ajoutera pas et ne chargera pas leurs lignes :",
  dataOnboardingParentForm: "Formulaire d'enregistrement",
  dataOnboardingForms: "Formulaires",
  dataOnboardingMapping: "Colonne vers question",
  dataOnboardingKeyColumns: "Colonnes clés",
  dataOnboardingValueMaps: "Correspondances de valeurs",
  dataOnboardingDropped: "Colonnes non chargées",
  dataOnboardingNotes: "Notes",
  dataOnboardingQuestion: "Question",
  dataOnboardingName: "Nom",
  dataOnboardingType: "Type",
  dataOnboardingRequired: "Obligatoire",
  dataOnboardingOptions: "Options",
  dataOnboardingColumn: "Colonne",
  dataOnboardingRaw: "Valeur dans le fichier",
  dataOnboardingReason: "Raison",
  dataOnboardingApply: "Appliquer",
  dataOnboardingApplying:
    "Application de la proposition : ajout des unités, création des formulaires et chargement des enregistrements.",
  dataOnboardingReport: "Rapport d'intégration",
  dataOnboardingLoaded: "Enregistrements chargés",
  dataOnboardingIssues: "Lignes ignorées et réponses abandonnées",
  dataOnboardingNoIssues: "Toutes les lignes ont été chargées.",
  dataOnboardingSheet: "Feuille",
  dataOnboardingRow: "Ligne",
  dataOnboardingSkipped: "Ligne ignorée",
  dataOnboardingDroppedAnswer: "Réponse abandonnée",
  dataOnboardingBlocked: "Bloqué",
  dataOnboardingBlockedNote:
    "Les formulaires bloqués ne sont pas appliqués. L'application charge les autres formulaires.",
  dataOnboardingNotApplied: "Formulaires non appliqués",
  dataOnboardingApplyFailed: "La proposition n'a pas pu être appliquée.",
  dataOnboardingDownloadReport: "Télécharger le rapport",
  dataOnboardingDownloadFailed: "Le rapport n'a pas pu être téléchargé.",
  dataOnboardingHistory: "Intégrations de données",
  dataOnboardingFile: "Fichier",
  dataOnboardingStatus: "Statut",
  dataOnboardingCreatedBy: "Commencée par",
  dataOnboardingCreated: "Commencée",
  dataOnboardingUpdated: "Dernière mise à jour",
  dataOnboardingDropColumn: "Retirer",
  dataOnboardingKeepColumn: "Garder",
  dataOnboardingReviseHint:
    "Décrivez toute autre modification, par exemple : traiter Statut comme une question oui/non.",
  dataOnboardingRevise: "Réviser",
  dataOnboardingRevisionFailed: "La proposition n'a pas pu être révisée.",
  dataOnboardingUseExisting: "Utiliser l'unité existante",
  dataOnboardingAddNew: "Ajouter comme nouvelle unité",
  dataOnboardingChooseParent: "Choisir le parent",
  dataOnboardingLocationColumns:
    "Colonnes de localisation, niveau supérieur d'abord",
  dataOnboardingFirstLevel: "Niveau de la première colonne",
  dataOnboardingLocationColumn: "Colonne de localisation",
  dataOnboardingDropForm: "Retirer ce formulaire",
  formBuilderImportModalTitle: "Importer un formulaire",
  formBuilderImportFormatLabel: "Format",
  formBuilderImportFormatJson: "JSON (Natif)",
  formBuilderImportFormatXlsform: "XLSForm (.xlsx)",
  formBuilderImportDraggerText:
    "Cliquez ou glissez un fichier de formulaire ici",
  formBuilderImportInvalidFile: "Seuls les fichiers .json sont pris en charge",
  formBuilderImportInvalidFileXlsform:
    "Seuls les fichiers .xlsx ou .xls sont pris en charge",
  formBuilderImportPreflightError: "Échec de la validation du fichier",
  formBuilderImportErrorsTitle: "Erreurs de validation",
  formBuilderImportWarningsTitle: "Avertissements",
  formBuilderImportFormLabel: "Formulaire",
  formBuilderImportQuestionsLabel: "Questions",
  formBuilderImportGroupsLabel: "Groupes",
  formBuilderImportFormTypeLabel: "Type de formulaire",
  formBuilderImportFormTypeRegistration: "Enregistrement",
  formBuilderImportFormTypeMonitoring: "Suivi",
  formBuilderImportFormTypeRequired:
    "Veuillez sélectionner un type de formulaire",

  // Common UI words
  dateFromPlaceholder: "De",
  dateToPlaceholder: "À",
  viewDetails: "Voir les détails",

  // Platform console
  platformConsole: "Console de plateforme",
  consoleTenants: "Espaces",
  consoleOperators: "Opérateurs",
  // FB-018 Form Library console
  consoleFormLibrary: "Bibliothèque de formulaires",
  consoleFLDescription:
    "Gérez le catalogue partagé de modèles de formulaires réutilisables.",
  consoleFLNameCol: "Modèle",
  consoleFLCategoriesCol: "Catégories",
  consoleFLUsedCol: "Utilisé",
  consoleFLMonitoringCol: "Formulaires de suivi",
  consoleFLActionsCol: "Actions",
  consoleFLManageCategories: "Gérer les catégories",
  consoleFLPromoteButton: "Promouvoir depuis un espace",
  consoleFLPromoteTitle: "Promouvoir un formulaire vers la bibliothèque",
  consoleFLEmpty: "Aucun modèle pour l'instant",
  consoleFLDeleteButton: "Supprimer",
  consoleFLDeleteConfirm:
    "Retirer ce modèle de la bibliothèque ? Les copies existantes ne sont pas affectées.",
  consoleFLDeleteSuccess: "Modèle retiré de la bibliothèque",
  consoleFLDeleteError: "Échec du retrait du modèle",
  consoleFLWorkspaceLabel: "Espace de travail",
  consoleFLWorkspacePlaceholder: "Sélectionnez un espace de travail",
  consoleFLWorkspaceRequired: "Veuillez sélectionner un espace de travail",
  consoleFLSourceLabel: "Formulaire source",
  consoleFLSourcePlaceholder:
    "Sélectionnez un formulaire d'enregistrement publié",
  consoleFLSourceRequired: "Veuillez sélectionner un formulaire source",
  consoleFLCategoriesLabel: "Catégories",
  consoleFLCategoriesPlaceholder: "Attribuez une ou plusieurs catégories",
  consoleFLPromoteSuccess: "Formulaire promu vers la bibliothèque",
  consoleFLPromoteError: "Échec de la promotion du formulaire",
  consoleFLPromotedFrom: "Promu depuis",
  consoleFLNewTemplate: "Nouveau modèle",
  consoleFLFromWorkspace: "Sélectionner depuis un espace existant",
  consoleFLFromScratch: "À partir de zéro (Générateur de formulaires)",
  consoleFLEditButton: "Modifier dans le générateur",
  consoleFLAddMonitoring: "Ajouter un formulaire de suivi",
  consoleFLBack: "Retour à la bibliothèque",
  consoleFLCancel: "Annuler",
  consoleFLPreviewHeading: "Aperçu du formulaire",
  consoleFLPreviewEmpty: "Sélectionnez un formulaire source pour l'aperçu",
  consoleFLCategoryPlaceholder: "Nom de la nouvelle catégorie",
  consoleFLCategoryAdd: "Ajouter",
  consoleFLCategoryEmpty: "Aucune catégorie pour l'instant",
  consoleFLCategoryDeleteConfirm: "Supprimer cette catégorie ?",
  consoleFLCategoryError: "L'opération sur la catégorie a échoué",
  closeButton: "Fermer",
  consoleSearchTenants: "Rechercher un sous-domaine ou un nom",
  consoleStateAll: "Tous",
  consoleStateActive: "Actif",
  consoleStateSuspended: "Suspendu",
  consoleStateDeleted: "Supprimé",
  consoleResultCount: "Résultats : {from} – {to} sur {total} espaces",
  consoleTotalWorkspaces: "Espaces",
  consoleTotalUsers: "Utilisateurs",
  consoleTotalForms: "Formulaires",
  consoleTotalDashboards: "Tableaux de bord",
  consoleTotalDatapoints: "Points de données",
  consoleTotalDevices: "Appareils",
  consoleTotalsRow: "Total",
  consoleInspect: "Inspecter",
  consoleInspectFailed: "Impossible d'ouvrir cet espace",
  consoleSuspend: "Suspendre",
  consoleRestore: "Restaurer",
  consoleRename: "Renommer",
  consoleDelete: "Supprimer",
  consoleFeatures: "Fonctionnalités",
  consoleUsers: "Utilisateurs",
  consoleDeactivate: "Désactiver",
  consoleReactivate: "Réactiver",
  consoleInviteOperator: "Inviter un opérateur",
  consoleRevoke: "Révoquer",
  consoleLogo: "Logo",
  consoleUploadLogo: "Téléverser le logo",
  consoleRemoveLogo: "Supprimer le logo",
  consoleLogoUpdated: "Logo mis à jour avec succès",
  consoleLogoRemoved: "Logo supprimé avec succès",
  brandingPanelTitle: "Image de marque de l'espace",
  brandingPanelDescription:
    "Personnalisez le logo de votre espace affiché dans la navigation et la connexion.",
  brandingPanelButton: "Gérer l'image de marque",
  brandingModalTitle: "Image de marque de l'espace",
  brandingLogoLabel: "Logo de l'espace de travail",
  brandingLogoHint: "Formats supportés : PNG, JPG, JPEG, SVG jusqu'à 2 Mo.",
  brandingUploadSuccess: "Image de marque mise à jour avec succès",
  brandingUploadError: "Impossible de mettre à jour l'image de marque",
  brandingRemoveSuccess: "Logo supprimé avec succès",
  brandingRemoveError: "Impossible de supprimer le logo",
  brandingRemoveBtn: "Supprimer le logo",
  brandingUploadBtn: "Téléverser le logo",
  brandingCurrentLogo: "Logo actuel",
  brandingNoLogo: "Aucun logo personnalisé (logo Akvo par défaut)",

  // Onboarding Tour
  tourWelcomeTitle: "Bienvenue sur Akvo MIS",
  tourWelcomeSubtitle:
    "Que souhaitez-vous faire en premier ? Nous vous guidons en moins d'une minute.",
  tourGoalRecommended: "Recommandé",
  tourGoalSetupTitle: "Mettre en place une collecte de données",
  tourGoalSetupDesc:
    "Créez un formulaire et transmettez-le à votre équipe de terrain",
  tourGoalReviewTitle: "Examiner et approuver les données",
  tourGoalReviewDesc: "Vérifiez les soumissions en attente",
  tourGoalExploreTitle: "Explorer les données et les tableaux de bord",
  tourGoalExploreDesc: "Parcourez, visualisez et téléchargez les résultats",
  tourBtnShowMeHow: "Montrez-moi comment",
  tourBtnSkip: "Passer",
  tourBtnBack: "Retour",
  tourBtnNext: "Suivant",
  tourStepOf: "ÉTAPE {current} SUR {total}",
  tourCopyAppLink: "Copier le lien de l'application",
  tourLinkCopied:
    "Lien de téléchargement de l'application copié dans le presse-papiers",
  tourLinkCopyError: "Impossible de copier le lien",
  tourSetupStep1Title: "Créer un formulaire",
  tourSetupStep1Desc:
    "Ajoutez des sections et des questions, puis publiez — ou évitez la page blanche en partant d'un modèle prêt à l'emploi dans la Bibliothèque de formulaires. Votre équipe de terrain pourra le remplir dès sa publication.",
  tourSetupStep2Title: "Transmettre l'application à votre équipe de terrain",
  tourSetupStep2Desc:
    "Votre équipe de terrain collecte les données hors ligne dans l'application mobile. Partagez le lien de téléchargement avec elle.",
  tourSetupStep3Title: "Suivre l'arrivée des soumissions",
  tourSetupStep3Desc:
    "Les nouvelles soumissions du terrain apparaissent ici. Filtrez par formulaire ou ajoutez-en une vous-même depuis le web.",
  tourSetupFinalBtn: "Créer votre premier formulaire",
  tourReviewStep1Title: "Vos approbations en attente",
  tourReviewStep1Desc:
    "Les soumissions en attente de votre décision arrivent ici. Vous pouvez aussi voir ce que vos approbateurs subordonnés doivent encore examiner.",
  tourReviewStep2Title: "Examiner les soumissions",
  tourReviewStep2Desc:
    "Ouvrez Gérer les données pour parcourir et filtrer les soumissions. Les approbations et les brouillons se trouvent également sous Données.",
  tourReviewFinalBtn: "Examiner les approbations en attente",
  tourExploreStep1Title: "Parcourir vos données",
  tourExploreStep1Desc:
    "Ouvrez Gérer les données pour parcourir, filtrer et examiner les soumissions par formulaire et par lieu.",
  tourExploreStep2Title: "Visualiser dans un tableau de bord",
  tourExploreStep2Desc:
    "Créez un tableau de bord à partir de vos données, publiez-le, puis gardez-le privé ou partagez-le publiquement.",
  tourExploreStep3Title: "Télécharger vos données",
  tourExploreStep3Desc:
    "Exportez les soumissions depuis Gérer les données. Les exports volumineux s'exécutent en arrière-plan et vous attendent ici.",
  tourExploreFinalBtn: "Créer un tableau de bord",
  tourExploreViewDataBtn: "Parcourir les données",
  tourGetHelpTitle: "Obtenir de l'aide à tout moment",
  tourGetHelpDesc:
    "Des questions ? Utilisez notre assistant IA à tout moment en bas à droite, ou consultez notre documentation.",

  // --- Auto-added translations (previously fell back to English) ---
  actionColumn: "Action",
  addAdmDesc: (
    <Fragment>
      Cette page vous permet d&apos;ajouter une administration à la plateforme{" "}
      {appName}.
    </Fragment>
  ),
  addAdministration: "Ajouter une administration",
  addAttachment: "Ajouter une pièce jointe",
  addAttachmentDesc: "Ajouter une nouvelle pièce jointe au lot",
  addAttributeDesc: (
    <Fragment>
      Cette page vous permet d&apos;ajouter un attribut à la plateforme{" "}
      {appName}.
    </Fragment>
  ),
  addAttributes: "Ajouter un attribut",
  addEntity: "Ajouter",
  addEntityData: "Ajouter",
  addEntityDesc: (
    <Fragment>
      Cette page vous permet d&apos;ajouter une entité à la plateforme {appName}
      .
    </Fragment>
  ),
  addEntityTypeDesc: (
    <Fragment>
      Cette page vous permet d&apos;ajouter un type d&apos;entité à la
      plateforme {appName}.
    </Fragment>
  ),
  addLevel: "Ajouter un niveau",
  addNewButton: "Ajouter",
  addOptionButton: "Ajouter une option",
  addOrgDesc: (
    <Fragment>
      Cette page vous permet d&apos;ajouter des organisations à la plateforme{" "}
      {appName}.
    </Fragment>
  ),
  addRole: "Ajouter un rôle",
  addRoleDescription: (id) => (
    <Fragment>
      Cette page vous permet d&apos;{id ? "modifier" : "ajouter"} des rôles sur
      la plateforme {appName} .
    </Fragment>
  ),
  addUserDescription: (
    <Fragment>
      Cette page vous permet d&apos;ajouter des utilisateurs à la plateforme{" "}
      {appName}. Vous pourrez uniquement ajouter des utilisateurs pour les
      régions relevant de votre juridiction.
      <br />
      Une fois l&apos;utilisateur ajouté, celui-ci sera notifié par e-mail afin
      de définir son mot de passe et d&apos;accéder à la plateforme
    </Fragment>
  ),
  // Home Page
  admConfirmDelete: "Êtes-vous sûr de vouloir supprimer cette administration ?",
  admErrDeleteTitle: "Impossible de supprimer l'administration",
  admErrSaveTitle: "Impossible d'enregistrer l'administration",
  admFieldRequired: "L'administration est obligatoire",
  AdministrationDataDownload: "Téléchargement des données d'administration",
  AdministrationDataUpload: "Importation des données d'administration",
  AdministrationDownloadPageHint:
    "Décochez Pré-rempli si vous souhaitez uniquement un modèle d'importation",
  administrationField: "Administration",
  administrationLabel: "Administration",
  administrationUploadFailedHint:
    "Rien n'a été modifié. Nous vous avons envoyé par e-mail un fichier répertoriant les lignes à corriger.",
  administrationUploadFailedTitle: "Votre fichier n'a pas pu être importé",
  administrationUploadSuccessTitle:
    "Les données d'administration ont été importées avec succès",
  admLevel: "Niveau d'administration",
  admName: "Nom de l'administration",
  admNameRequired: "Le nom de l'administration est obligatoire",
  admPanelText: (
    <Fragment>
      C&apos;est ici que vous :
      <ul>
        <li>Ajouter une nouvelle administration</li>
        <li>Modifier une administration existante</li>
        <li>Supprimer une administration existante</li>
        <li>Importer en masse une administration</li>
      </ul>
    </Fragment>
  ),
  admParent: "Administration parente",
  admSuccessAdded: "Administration ajoutée",
  admSuccessDeleted: "Administration supprimée",
  admSuccessUpdated: "Administration mise à jour",
  admTabTitle: "Liste administrative",
  allData: "Toutes les données",
  allEntities: "Toutes les entités",
  approvalsTab1: "Mes approbations en attente",
  approvalsTab2: "Approbations des subordonnés",
  approvalsTab3: "Approuvé",
  approveNoteRequired:
    "Veuillez fournir des notes ou des commentaires pour refuser ou approuver la soumission",
  approversDescription: (
    <Fragment>
      C&apos;est ici que vous pouvez voir les approbateurs de chaque formulaire
      soumis dans différentes zones administratives :
    </Fragment>
  ),
  // Misc
  attrConfirmDelete: "Êtes-vous sûr de vouloir supprimer cet attribut ?",
  attrErrDeleteTitle: "Impossible de supprimer l'attribut",
  attrName: "Nom de l'attribut",
  attrNameRequired: "Le nom de l'attribut est obligatoire",
  attrSuccessAdded: "Attribut ajouté",
  attrSuccessDeleted: "Attribut supprimé",
  attrSuccessUpdated: "Attribut mis à jour",
  attrTabTitle: "Attributs",
  attrType: "Type d'attribut",
  attrTypeRequired: "Le type d'attribut est obligatoire",
  backManageData: "Retour à Gérer les données",
  backToAdmLabel: "Retour à la liste administrative",
  backToCenterLabel: "Retour au centre de contrôle",
  batchAttachments: "Pièces jointes",
  batchFilesHint:
    "Veuillez importer un fichier avec l'une des extensions suivantes : .xlsx, .xls, .csv, .ods, .pdf, .docx, .doc",
  batchFileTypeError:
    "Type de fichier de pièce jointe non valide. Veuillez importer un fichier valide.",
  batchHintDesc:
    "L'opération de fusion des jeux de données ne peut pas être annulée, et créera un nouveau lot qui nécessitera l'approbation de votre administrateur",
  // Upload Detail
  batchHintText: "Vous êtes sur le point de créer un fichier CSV de lot",
  batchName: "Nom du lot",
  batchNoApproverMessage:
    "Impossible de créer des données de lot, car il n'y a pas encore d'approbateur.",
  batchSelectedDatasets: "Jeux de données sélectionnés du lot",
  browseComputer: "Parcourir votre ordinateur",
  bulkUpload: "Importation en masse",
  bulkUploadAttr: "Attributs",
  bulkUploadAttrPlaceholder: "Sélectionner des attributs...",
  bulkUploadButton: "Importation en masse",
  bulkUploadCheckboxPrefilled: "Liste administrative pré-remplie",
  bulkUploadNoApproverMessage:
    "Impossible de téléverser des données, car il n'y a pas encore d'approbateur.",
  cancelButton: "Annuler",
  channelCol: "Canal",
  checkboxSelectAll: "Tout sélectionner {{name}}",
  codeField: "Code",
  codeFieldRequired: "Le code est obligatoire",
  codeLabel: "Code",
  confirmDeleteEntity: "Êtes-vous sûr de vouloir supprimer cette entité ?",
  confirmDeleteEntityData: "Êtes-vous sûr de vouloir supprimer ces données ?",
  createDraftMonitoring: "Créer un brouillon de données de suivi",
  createNewBatch: "Créer un nouveau lot",
  dataAdministrationDownloadText: (
    <Fragment>
      C&apos;est ici que vous :
      <ul>
        <li>Télécharger les données d&apos;administration</li>
      </ul>
    </Fragment>
  ),
  dataAdministrationUploadText: (
    <Fragment>
      C&apos;est ici que vous :
      <ul>
        <li>Importer en masse les données d&apos;administration</li>
      </ul>
    </Fragment>
  ),
  dataEntitiesDownloadText: (
    <Fragment>
      C&apos;est ici que vous :
      <ul>
        <li>Télécharger les données des entités</li>
      </ul>
    </Fragment>
  ),
  dataEntitiesUploadText: (
    <Fragment>
      C&apos;est ici que vous :
      <ul>
        <li>Importer en masse les données des entités</li>
      </ul>
    </Fragment>
  ),
  dataExportFail: "Le téléchargement des données a échoué",
  dataExportSuccess: "Données téléchargées avec succès",
  datapointCol: "Point de données",
  dataUploadText: (
    <Fragment>
      C&apos;est ici que vous :
      <ul>
        <li>Télécharger le modèle d&apos;importation</li>
        <li>Importer en masse de nouvelles données</li>
        <li>Mettre à jour en masse les données existantes</li>
      </ul>
    </Fragment>
  ),
  dataUploadTitle: "Importation de données",
  deleteAttachmentDesc:
    "Êtes-vous sûr de vouloir supprimer cette pièce jointe ?",
  deleteAttachmentError: "Impossible de supprimer la pièce jointe",
  deleteAttachmentSuccess: "Pièce jointe supprimée avec succès",
  deleteAttachmentTitle: "Supprimer la pièce jointe",
  deleteDraftContent: "Êtes-vous sûr de vouloir supprimer {{draftName}} ?",
  deleteDraftError: "Impossible de supprimer le brouillon",
  deleteDraftSuccess: "Brouillon supprimé avec succès",
  deleteDraftTitle: "Supprimer le brouillon",
  deleteOrganisationDesc: ({ count = 0 }) => (
    <span>
      Il y a <b>{count} Utilisateurs</b> associés à cette organisation. Veuillez
      réaffecter ou supprimer ce(s) utilisateur(s) avant de supprimer
      l&apos;organisation afin d&apos;éviter des résultats inattendus
    </span>
  ),
  deleteOrganisationTitle: "Vous êtes sur le point de supprimer l'organisation",
  // Tour
  deleteText: "Supprimer",
  deleteUserDesc: (
    <Fragment>
      L&apos;utilisateur ne pourra plus accéder à la plateforme {appName} en
      tant qu&apos;enquêteur/administrateur, etc.
    </Fragment>
  ),
  deleteUserHint:
    "La suppression de cet utilisateur ne supprimera pas la ou les associations de données",
  deleteUserTitle: "Vous êtes sur le point de supprimer l'utilisateur",
  download: "Télécharger",
  downloadAppsLinkText: "ou téléchargez à l'aide des liens ci-dessous :",
  downloadAppsQRText: (
    <Fragment>
      Téléchargez l&apos;<b>application {apkName}</b> à l&apos;aide des codes QR
      ci-dessous
    </Fragment>
  ),
  downloadData: "Télécharger les données",
  downloadHere: "télécharger ici",
  downloadReport: "Télécharger le rapport",
  downloadReportError: "Impossible de télécharger le rapport",
  downloadReportSuccess: "Rapport téléchargé avec succès",
  downloadTitle: "Téléchargements",
  // Add user modal notification
  draftCreatedByCol: "Créé par",
  draftFormDescription: (
    <p>
      Veuillez remplir le formulaire web ci-dessous avec les réponses
      pertinentes. Vous pouvez enregistrer vos réponses et continuer plus tard,
      ou si vous avez terminé le formulaire, vous pouvez le soumettre.
    </p>
  ),
  draftFormPublishConfirmContent:
    "Êtes-vous sûr de vouloir publier ce brouillon ? Cette action est irréversible.",
  draftFormPublishConfirmTitle: "Publier le brouillon",
  draftFormPublishError: "Impossible de publier le brouillon",
  draftFormPublishSuccess: "Brouillon publié avec succès",
  draftFormSaveError: "Impossible d'enregistrer le brouillon",
  draftFormSaveSuccess: "Brouillon enregistré avec succès",
  draftUpdatedByPrefix: "par",
  dropFile: "Déposez votre fichier ici",
  editAdmDesc: (
    <Fragment>
      Cette page vous permet de modifier l&apos;administration de la plateforme{" "}
      {appName}.
    </Fragment>
  ),
  editAdministration: "Modifier l'administration",
  editAndPublishDraft: "Modifier et publier le brouillon",
  editAttachment: "Modifier la pièce jointe",
  editAttachmentDesc: "Remplacer la pièce jointe existante par une nouvelle",
  editAttributeDesc: (
    <Fragment>
      Cette page vous permet de modifier l&apos;attribut de la plateforme{" "}
      {appName}.
    </Fragment>
  ),
  editAttributes: "Modifier l'attribut",
  editButton: "Modifier",
  editEntity: "Modifier l'entité",
  editEntityData: "Modifier les données",
  editEntityDesc: (
    <Fragment>
      Cette page vous permet de modifier l&apos;entité de la plateforme{" "}
      {appName}.
    </Fragment>
  ),
  editEntityTypeDesc: (
    <Fragment>
      Cette page vous permet de modifier le type d&apos;entité de la plateforme{" "}
      {appName}.
    </Fragment>
  ),
  editOrgDesc: (
    <Fragment>
      Cette page vous permet de modifier les organisations de la plateforme{" "}
      {appName}.
    </Fragment>
  ),
  editProfile: "Modifier le profil",
  editRole: "Modifier le rôle",
  editText: "Modifier",
  endOfListLabel: "Fin de la liste",
  EntitiesDataDownload: "Téléchargement des données d'entités",
  EntitiesDataUpload: "Importation des données d'entités",
  EntitiesDownloadPageHint:
    "Décochez Prérempli si vous ne voulez qu'un modèle d'importation",
  entitiesUploadSuccessTitle:
    "Les données d'entités ont été importées avec succès",
  entityIsRequired: "L'entité est obligatoire",
  entityTabTitle: "Entités",
  entityText: "Entité",
  entityType: "Type d'entité",
  entityTypes: "Types d'entité",
  errAddOrg: "Impossible d'ajouter l'organisation",
  errDeleteCascadeText1:
    "Il est associé à d'autres ressources ou comporte des restrictions en cascade.",
  errDeleteCascadeText2:
    "Veuillez examiner et résoudre les dépendances avant de tenter la suppression.",
  errDeleteEntityDataTitle: "Impossible de supprimer les données",
  errDeleteEntityTitle: "Impossible de supprimer l'entité",
  errorEntityData: (entity) =>
    `L'administration sélectionnée n'a pas d'entités ${entity}`,
  errorEntityNotExists: (entity) =>
    `Malheureusement, les entités ${entity} ne sont pas encore disponibles. Veuillez contacter l'administrateur pour les ajouter`,
  errorMonitoringRequiresRegistration: (monitoring, registration) =>
    `"${monitoring}" nécessite que son formulaire d'enregistrement parent "${registration}" soit sélectionné`,
  errorURL: (
    <Fragment>
      Veuillez vérifier à nouveau l&apos;URL ou laissez-nous vous ramener à la
      page d&apos;accueil de {appName}{" "}
    </Fragment>
  ),
  errSaveEntityDataTitle: "Impossible d'enregistrer les données",
  errUpdateOrg: "Impossible de mettre à jour l'organisation",
  existingApproverDescription:
    "Veuillez mettre à jour la configuration dans gérer l'arbre de validation ou retirer ces formulaires pour l'utilisateur actuel",
  existingApproverTitle: "Il existe des approbateurs pour :",
  export2ExcelError: "Impossible d'exporter les données vers Excel",
  export2ExcelSuccess: "Données exportées vers Excel avec succès",
  exportEntityError: "Impossible d'exporter les entités",
  exportPanelText: (
    <Fragment>
      <p>
        Cette page affiche votre liste de demandes d&apos;exportation de
        données.
        <br />
        Pour les exportations déjà générées, veuillez cliquer sur le bouton
        Télécharger pour télécharger les données.
      </p>
    </Fragment>
  ),
  // Webform
  failed: "Échec",
  fetchingForm: "Récupération du formulaire..",
  // Forgot Password
  fileUploadFail: "Impossible d'importer le fichier",
  fileUploadSuccess: "Fichier importé avec succès",
  finish: "Terminer",
  formAccess: "Accès au formulaire",
  formBuilderActivateVersionDesc:
    "Cela remplacera le schéma actif actuel. L'éditeur va se recharger.",
  formBuilderActivateVersionTitle: (v) => (
    <Fragment>{`Activer la version ${v} ?`}</Fragment>
  ),
  formBuilderArchiveConfirmDesc: (count) =>
    count > 0
      ? `Il sera retiré de la collecte de données (web et mobile) et ` +
        `déplacé vers l'onglet Archivés. Ce formulaire comporte ${count} ` +
        `soumission(s) — elles sont conservées. Vous pourrez le restaurer plus tard.`
      : `Il sera retiré de la collecte de données (web et mobile) et ` +
        `déplacé vers l'onglet Archivés. Vous pourrez le restaurer plus tard.`,
  formBuilderDeleteDisabledTooltip:
    "Les formulaires comportant des soumissions ne peuvent pas être supprimés — gardez-le archivé ou restaurez-le.",
  formBuilderDescription: (
    <Fragment>
      C&apos;est ici que vous pouvez créer et gérer vos formulaires. Vous pouvez
      :
      <ul>
        <li>Créer de nouveaux formulaires avec divers types de questions</li>
        <li>Modifier les formulaires existants avec contrôle de version</li>
        <li>Supprimer les formulaires qui ne sont plus nécessaires</li>
      </ul>
    </Fragment>
  ),
  formBuilderImportCloseButton: "Fermer",
  formBuilderImportConfirmButton: "Importer",
  formBuilderImportDraggerHint: (mb) =>
    `Uniquement les fichiers d'exportation de formulaire .json, jusqu'à ${mb} Mo`,
  formBuilderImportDraggerHintXlsform: (mb) =>
    `Uniquement les fichiers .xlsx ou .xls, jusqu'à ${mb} Mo`,
  formBuilderImportFailed: "Échec de l'importation",
  formBuilderImportFileTooLarge: (mb) =>
    `Le fichier dépasse la limite de ${mb} Mo`,
  formBuilderImportInProgress: "Importation du formulaire…",
  formBuilderImportModeCopy: "Importer comme nouvelle copie",
  formBuilderImportModeUpdate: "Mettre à jour le formulaire existant",
  formBuilderImportNameMismatchWarning:
    "Le nom dans le fichier diffère du nom du formulaire existant — " +
    "assurez-vous de mettre à jour le bon formulaire.",
  formBuilderImportOpenEditor: "Ouvrir dans l'éditeur",
  formBuilderImportParentLabel: "Formulaire d'enregistrement parent",
  formBuilderImportParentPlaceholder:
    "Sélectionnez un formulaire d'enregistrement",
  formBuilderImportParentRequired:
    "Un formulaire de suivi nécessite un formulaire d'enregistrement parent.",
  formBuilderImportRetryButton: "Essayer un autre fichier",
  formBuilderImportSkippedCount: (count) =>
    `${count} ligne(s) non prise(s) en charge seront ignorées`,
  formBuilderImportSuccess: "Formulaire importé",
  formBuilderImportUpdateDesc: (count) =>
    `Un formulaire avec le même ID existe déjà dans cet environnement` +
    (count > 0 ? ` et comporte ${count} soumission(s)` : "") +
    `. La mise à jour modifie sa structure sur place ; les soumissions sont conservées.`,
  formBuilderImportUpdateTitle: (name) =>
    `Mettre à jour le formulaire existant "${name}" ?`,
  formBuilderImportXlsformNoticeDesc: (
    <div style={{ textAlign: "left", fontSize: 13, lineHeight: 1.5 }}>
      <p style={{ margin: "4px 0 8px 0", textAlign: "left" }}>
        Votre XLSForm a été importé avec succès, mais Kobo et Akvo MIS ne
        fonctionnent pas de manière identique et une partie de la logique du
        formulaire peut nécessiter un ajustement manuel pour correspondre
        pleinement à votre original. Veuillez examiner les avertissements
        ci-dessous et tester le formulaire avant de le publier.
      </p>
      <p
        style={{
          margin: "8px 0 4px 0",
          fontWeight: 600,
          textAlign: "left",
        }}
      >
        Éléments courants à vérifier :
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
          Champs calculés – les formules peuvent devoir être revérifiées
        </li>
        <li style={{ marginBottom: 4 }}>
          Comptes de répétition dynamiques – les groupes répétables pilotés par
          une variable peuvent nécessiter une configuration manuelle
        </li>
        <li style={{ marginBottom: 4 }}>
          Pertinence de groupe / logique de saut – la visibilité conditionnelle
          des groupes doit être revérifiée
        </li>
        <li style={{ marginBottom: 4 }}>
          Questions de suivi &quot;Autre&quot; – elles ne sont pas converties
          automatiquement ; ajoutez-les manuellement si nécessaire
        </li>
      </ul>
      <p style={{ margin: "8px 0 0 0", textAlign: "left" }}>
        Nous recommandons de prévisualiser le formulaire complet et de tester
        une soumission avant sa mise en service.
      </p>
    </div>
  ),
  formBuilderImportXlsformNoticeTitle:
    "Cette importation nécessite une vérification rapide",
  formBuilderMonitoringFor: (name) =>
    `Création du formulaire de suivi pour : ${name}`,
  formBuilderParentFormError:
    "Formulaire parent introuvable ou non publié. Impossible de créer le formulaire de suivi.",
  formBuilderPreviewingBanner: (v) => (
    <Fragment>{`Prévisualisation de l'instantané v${v} — ce n'est pas l'état enregistré.`}</Fragment>
  ),
  formBuilderPublishedInfo:
    "Modifier un formulaire publié crée un nouvel instantané de version. Cliquez sur Publier pour l'activer.",
  formBuilderSnapshotPending: (v) => (
    <Fragment>
      {`Modifications enregistrées comme instantané v${v}. Cliquez sur Publier pour activer.`}
    </Fragment>
  ),
  formBuilderVersionActivated: (n) => (
    <Fragment>{`La version ${n} est maintenant active. Rechargement de l'éditeur…`}</Fragment>
  ),
  formColumn: "Formulaire",
  formDescription: (
    <p>
      Veuillez remplir le formulaire web ci-dessous avec les réponses
      pertinentes. Vous devrez répondre à toutes les questions obligatoires
      avant de pouvoir soumettre.
      <br />
      Une fois que vous avez soumis un formulaire web, n&apos;oubliez pas de
      l&apos;ajouter dans un lot et de l&apos;envoyer pour approbation.
    </p>
  ),
  // Draft Webform
  formSuccessSubTitle:
    "Veuillez noter que ces données n'ont PAS été envoyées pour approbation. Si vous êtes prêt à envoyer les soumissions pour approbation, veuillez créer un lot et l'envoyer à l'approbateur",
  formSuccessSubTitleForAdmin:
    "Veuillez noter que les données soumises par le rôle SUPER ADMIN ne passeront pas par le flux d'approbation et seront enregistrées comme données approuvées",
  formSuccessTitle: "Merci pour votre soumission",
  generating: "Génération",
  helloText: "Bonjour",
  // User Management
  informUser: "Informer l'utilisateur des modifications",
  // Data Uploads
  initialRegistration: "Enregistrement initial",
  invalidInviteDesc:
    "Lorem, ipsum dolor sit amet consectetur adipisicing elit. Autem provident voluptatum cum numquam, quidem vitae, qui quam beatae exercitationem ullam perferendis! Nobis in aut fuga voluptate harum, tempore distinctio optio.",
  // Register
  isSuperAdminLabel: "Est superadministrateur ?",
  lastLoginLabel: "Dernière connexion",
  lastResponseCol: "Dernière réponse",
  lastUpdatedCol: "Dernière mise à jour",
  latestData: "Données les plus récentes",
  levelDeleteTitle: "Supprimer le niveau le plus profond ?",
  levelField: "Niveau",
  levelFieldRequired: "Le niveau est obligatoire",
  levelFrozenHint:
    "Les niveaux ne peuvent plus être ajoutés ni supprimés car des " +
    "unités administratives existent déjà. Le renommage reste possible.",
  levelLabel: "Niveau",
  loadingText: "Chargement...",
  loadMoreLable: "Charger plus",
  manageAdministrativeList: "Gérer la liste administrative",
  manageAttributes: "Gérer les attributs",
  manageAttributeText: (
    <Fragment>
      C&apos;est ici que vous gérez les attributs en fonction de leurs champs.
      Vous pouvez :
      <ul>
        <li>Ajouter un nouvel attribut</li>
        <li>Modifier un attribut existant</li>
        <li>Supprimer un attribut existant</li>
      </ul>
    </Fragment>
  ),
  manageDataTab1: "Données d'enregistrement",
  manageDataTab2: "Données de suivi",
  manageDataTab3: "Aperçu du suivi",
  manageDataTabList: "Liste des points de données",
  manageDataTabMap: "Vue cartographique",
  manageDraftText: (
    <Fragment>
      C&apos;est ici que vous pouvez gérer vos brouillons. Vous pouvez :
      <ul>
        <li>Consulter vos brouillons enregistrés</li>
        <li>Modifier les brouillons existants</li>
        <li>Supprimer les brouillons existants</li>
      </ul>
    </Fragment>
  ),
  manageDraftTitle: "Gérer les brouillons",
  manageEntities: "Gérer les entités",
  manageEntitiesText: (
    <Fragment>
      C&apos;est ici que vous gérez les entités en fonction de leurs champs.
      Vous pouvez :
      <ul>
        <li>Ajouter une nouvelle entité</li>
        <li>Modifier une entité existante</li>
        <li>Supprimer une entité existante</li>
      </ul>
    </Fragment>
  ),
  manageEntityTypes: "Gérer les types d'entité",
  manageEntityTypesText: (
    <Fragment>
      C&apos;est ici que vous gérez les types d&apos;entité en fonction de leurs
      champs. Vous pouvez :
      <ul>
        <li>Ajouter un nouveau type d&apos;entité</li>
        <li>Modifier un type d&apos;entité existant</li>
        <li>Supprimer un type d&apos;entité existant</li>
      </ul>
    </Fragment>
  ),
  manageLevels: "Gérer les niveaux",
  manageLevelText:
    "Définissez les niveaux de votre hiérarchie administrative, du niveau " +
    "supérieur vers le bas. Les niveaux peuvent être renommés à tout moment, " +
    "mais ils ne peuvent être ajoutés ou supprimés que tant qu'aucune unité " +
    "administrative n'existe sous votre niveau supérieur.",
  manageRoles: "Gérer les rôles",
  manageRolesTitle: "Gérer les rôles",
  manageUserText: (
    <Fragment>
      C&apos;est ici que vous gérez les utilisateurs en fonction de leurs rôles,
      régions et accès aux questionnaires . Vous pouvez :
      <ul>
        <li>Ajouter un nouvel utilisateur</li>
        <li>Modifier un utilisateur existant</li>
        <li>Supprimer un utilisateur existant</li>
      </ul>
    </Fragment>
  ),
  mobileAddText: "Ajouter une affectation",
  mobileAdmRequired: "L'administration est obligatoire : une ou plusieurs",
  mobileAppText: "Application mobile",
  mobileButtonAdd: "Ajouter un nouveau collecteur de données",
  mobileButtonSave: "Enregistrer",
  mobileConfirmDelete: "Êtes-vous sûr de vouloir supprimer cette affectation ?",
  mobileEditText: "Modifier l'affectation",
  mobileErrDelete: "Impossible de supprimer l'affectation",
  mobileFormsRequired: "Le formulaire est obligatoire : un ou plusieurs",
  mobileLabelAdm: "Administrations",
  mobileLabelForms: "Formulaires",
  mobileLabelName: "Nom",
  mobileLevelRequired: "Le niveau est obligatoire",
  mobileNameRequired: "Le nom est obligatoire",
  mobilePanelAddDesc: (
    <Fragment>
      Cette page vous permet d&apos;ajouter des collecteurs de données mobiles à
      la plateforme {appName} .
    </Fragment>
  ),
  mobilePanelEditDesc: (
    <Fragment>
      Cette page vous permet de modifier les collecteurs de données mobiles sur
      la plateforme {appName} .
    </Fragment>
  ),
  mobilePanelText: (
    <Fragment>
      C&apos;est ici que vous :
      <ul>
        <li>Ajoutez un nouveau collecteur de données mobiles</li>
        <li>Modifiez un collecteur de données mobiles existant</li>
        <li>Supprimez un collecteur de données mobiles existant</li>
      </ul>
    </Fragment>
  ),
  mobilePanelTitle: "Collecteurs de données mobiles",
  mobileSelectForms: "Sélectionner des formulaires...",
  mobileSuccessAdded: "Affectation mobile ajoutée",
  mobileSuccessUpdated: "Mise à jour de l'affectation mobile",
  monitoringDataDescription: (
    <Fragment>
      C&apos;est ici que vous :
      <ul>
        <li>
          Obtenez la liste des formulaires qui ont été collectés pour ce point
          de données (nouveau et mise à jour)
        </li>
        <li>Modifiez les données de suivi</li>
      </ul>
    </Fragment>
  ),
  monitoringDataTitle: "Données de suivi",
  moreCount: "+{{count}} de plus",
  moreItems: "Plus d'éléments",
  nameCol: "Nom",
  nameField: "Nom",
  nameFieldRequired: "Le nom est obligatoire",
  nameLabel: "Nom",
  next: "Suivant",
  notAssigned: "Non attribué",
  notesFeedback: "Notes et commentaires",
  // Export Data
  noText: "Non",
  notifyError: "Une erreur s'est produite",
  optionsField: "Options",
  organisationDeleteFail: "Impossible de supprimer l'organisation",
  organisationsLoadFail: "Impossible de charger les organisations",
  orgPanelButton: "Gérer l'organisation",
  orgPanelText: (
    <Fragment>
      C&apos;est ici que vous :
      <ul>
        <li>Ajoutez une nouvelle organisation</li>
        <li>Modifiez une organisation existante</li>
        <li>Supprimez une organisation existante</li>
      </ul>
    </Fragment>
  ),
  orgPanelTitle: "Gérer l'organisation",
  orgTabTitle: "Organisations",
  panelApprovalsDesc: (
    <Fragment>
      C&apos;est ici que vous :
      <ul>
        <li>
          Consultez les approbations de données en attente de votre approbation{" "}
        </li>
        <li>
          Consultez les approbations en attente de vos approbateurs subordonnés
        </li>
        <li>Attribuez des approbateurs subordonnés</li>
      </ul>
    </Fragment>
  ),
  // Upload Data
  passwordCriteriaError: "Critères de mot de passe incorrects",
  passwordMatchError:
    "Les deux mots de passe que vous avez saisis ne correspondent pas !",
  // Log in
  passwordRule1: "Caractère minuscule",
  passwordRule2: "Chiffres",
  passwordRule3: "Caractère spécial ( -._!`'#%&,:;<>=@{}~$()*+/?[]^|] )",
  passwordRule4: "Caractère majuscule",
  passwordRule5: "Aucun espace blanc",
  passwordRule6: "Minimum 8 caractères",
  passwordUpdateSuccess: "Mot de passe mis à jour avec succès",
  prev: "Précédent",
  profileDes:
    "Cette page affiche la configuration actuelle de votre utilisateur. Elle affiche également les activités les plus importantes pour la configuration actuelle de votre utilisateur",
  profileLabel: "Profil",
  questionCol: "Question",
  questionnairesLabel: "Questionnaires",
  questionnaireText: "Questionnaire",
  recentActivityCol: "Activité récente",
  regionCol: "Région",
  registrationView: "Enregistrement",
  rejectText: "Rejeter",
  requiredError: "{{field}} est obligatoire",
  responseCol: "Réponse",
  roleAccess: "Accès du rôle",
  roleAccessRequired: "L'accès du rôle est obligatoire",
  roleAdmLevel: "Niveau d'administration",
  roleAdmLevelPlaceholder: "Sélectionnez un niveau d'administration...",
  roleAdmLevelRequired: "Le niveau d'administration est obligatoire",
  roleConfirmDelete: "Êtes-vous sûr de vouloir supprimer {roleName} ?",
  roleDeleteTitle: "Vous êtes sur le point de supprimer le rôle",
  roleDescription: "Description du rôle",
  roleErrorAdd: "Le rôle n'a pas pu être ajouté",
  roleErrorUpdate: "Le rôle n'a pas pu être mis à jour",
  roleFeatures: "Fonctionnalités du rôle",
  roleLabel: "Rôle",
  roleName: "Nom du rôle",
  roleNameRequired: "Le nom du rôle est obligatoire",
  rolesLabel: "Rôle(s)",
  rolesRequired: "Veuillez sélectionner au moins un rôle",
  roleSuccessAdded: "Rôle ajouté",
  roleSuccessUpdated: "Rôle mis à jour",
  roleTotalUsers: "Total des utilisateurs",
  saveButton: "Enregistrer",
  saveEditButton: "Enregistrer les modifications",
  searchEntity: "Saisissez un nom...",
  searchEntityType: "Saisissez un nom...",
  searchNameOrCode: "Saisissez un nom ou un code...",
  searchPlaceholder: "Rechercher...",
  selectChildForms: "Sélectionnez les formulaires de suivi",
  selectEntity: "Sélectionnez une entité...",
  selectForm: "Veuillez sélectionner un formulaire",
  selectFormPlaceholder: "Sélectionner un formulaire",
  selectIndicatorPlaceholder: "Sélectionner un indicateur",
  selectLevel: "Sélectionnez un niveau...",
  selectMonitoringFormPlaceholder: "Sélectionner un formulaire de suivi",
  selectOne: "Sélectionnez-en un...",
  selectQuestionPlaceholder: "Sélectionner une question",
  selectRole: "Sélectionnez un rôle...",
  selectRowsToDownload: "Veuillez sélectionner les lignes à télécharger",
  selectText: "Sélectionner...",
  selectType: "Sélectionnez un type...",
  selectViewMode: "Sélectionner une vue",
  sendNewRequest: "Notifier l'approbateur",
  settingsDescriptionPanel:
    "Cette page permet au Super administrateur de gérer les listes maîtres critiques du système.",
  // Approvals
  showAllQuestionsSwitch: "Afficher toutes les questions",
  showPendingUsers: "Afficher les utilisateurs en attente",
  submissionComment: "Commentaire de la soumission",
  submissionDateCol: "Date de soumission",
  submissionsText: "Soumissions",
  successAddedEntity: "Entité ajoutée",
  successAddedOrg: "Organisation ajoutée",
  successDataUpdated: "Données mises à jour",
  successDeletedEntity: "Entité supprimée",
  successEntityDataAdded: "Données de l'entité ajoutées",
  successEntityDataDeleted: "Données de l'entité supprimées",
  successEntityDataUpdated: "Données de l'entité mises à jour",
  successUpdatedEntity: "Entité mise à jour",
  successUpdatedOrg: "Organisation mise à jour",
  templateDownloadAdministrationHint:
    "Si vous n'avez pas encore de modèle, veuillez ",
  templateDownloadEntityHint:
    "Si vous n'avez pas encore de modèle d'entité, veuillez ",
  templateDownloadHint:
    "Si vous n'avez pas encore de modèle, veuillez télécharger",
  templateFetchFail: "Impossible de récupérer le modèle",
  totalMonitoring: "Total du suivi",
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
  updateDataButton: "Mettre à jour les données",
  updateDataError: "Impossible de mettre à jour les données",
  updateExisting: "Mettre à jour les données existantes",
  uploadAnotherFileLabel: "Importer un autre fichier",
  uploadAttachmentsComment: "Ajoutez un commentaire pour la pièce jointe",
  uploadAttachmentsError: "Impossible d'importer les pièces jointes",
  uploadAttachmentsRequired: "Veuillez importer au moins un fichier joint",
  uploadAttachmentsSuccess: "Pièces jointes importées avec succès",
  uploadDataLabel: "Importez vos données",
  uploading: "Importation..",
  uploadMasterDataLabel: "Importez vos données",
  uploadNotReadyHint:
    "Définissez d'abord vos niveaux administratifs : nommez le niveau supérieur et ajoutez au moins un niveau en dessous. Vous pouvez le faire dans Données maîtres → Niveaux.",
  uploadsTab1: "Soumission en attente",
  uploadsTab2: "Approbation en attente",
  uploadsTab3: "Approuvé",
  uploadTab1: "Résumé des données",
  uploadTab2: "Données brutes",
  uploadText: "Importer",
  uploadThankyouText: (
    <Fragment>
      Merci d&apos;avoir importé le fichier de données. Veuillez noter que les
      données seront validées par le système . Vous serez notifié par e-mail si
      les données échouent aux tests de validation . Les erreurs de validation à
      corriger seront également jointes. S&apos;il n&apos;y a aucune erreur de
      validation , les données seront transmises pour vérification, approbation
      et certification
    </Fragment>
  ),
  userAssociations: "Cet utilisateur a les association(s) de données suivantes",
  userCol: "Utilisateur",
  userDeleteFail: "Impossible de supprimer l'utilisateur",
  userFirstName: "Prénom",
  userLastName: "Nom de famille",
  userOrganisation: "Organisation",
  userPhoneNumber: "Numéro de téléphone",
  usersLoadFail: "Impossible de charger les utilisateurs",
  viewAttachment: "Voir la pièce jointe",
  viewFullContext: "Voir le contexte complet",
  viewText: "Voir",
  webformText: "Formulaire web",
  yesText: "Oui",
};

export default fr;
