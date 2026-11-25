import { accuracyLevels } from '../../lib/loc';

// Define quality options inline to avoid importing expo-image-manipulator at module load time
const imageQualityOptions = [
  { label: 'Low', value: 'low' },
  { label: 'Medium', value: 'medium' },
  { label: 'High', value: 'high' },
  { label: 'Original', value: 'original' },
];

// `group` names the section a field sits in (a `ui-text` key), `unit` suffixes its value,
// `levelKind` shows it as a LevelIcon chip, and a page's `note` is a `ui-text` key.
export const config = [
  {
    id: 1,
    name: 'Advanced Settings',
    icon: 'settings-outline',
    note: 'settingsSensitiveNote',
    translations: [
      {
        language: 'fr',
        name: 'Paramètres avancés',
      },
    ],
    fields: [
      {
        id: 11,
        type: 'text',
        label: 'Server URL',
        name: 'serverURL',
        group: 'settingsSectionServer',
        description: null,
        key: 'BuildParamsState.serverURL',
        editable: false,
        translations: [
          {
            language: 'fr',
            name: 'URL du serveur',
          },
        ],
      },
      {
        id: 14,
        type: 'text',
        name: 'authenticationCode',
        label: 'Passcode',
        group: 'settingsSectionServer',
        description: null,
        key: 'AuthState.authenticationCode',
        editable: false,
        translations: [
          {
            language: 'fr',
            name: "Code d'accès",
          },
        ],
      },
      {
        id: 31,
        type: 'number',
        name: 'dataSyncInterval',
        label: 'Sync Interval',
        group: 'settingsSectionSync',
        unit: 's',
        description: {
          name: 'How often submissions are sent',
          translations: [
            {
              language: 'fr',
              name: "Fréquence d'envoi des soumissions",
            },
          ],
        },
        key: 'BuildParamsState.dataSyncInterval',
        editable: true,
        translations: [
          {
            language: 'fr',
            name: 'Intervalle de synchronisation',
          },
        ],
      },
      {
        id: 32,
        type: 'switch',
        label: 'Sync Wi-Fi',
        name: 'syncWifiOnly',
        group: 'settingsSectionSync',
        description: {
          name: 'Only sync when connected to Wi-Fi',
          translations: [
            {
              language: 'fr',
              name: 'Synchroniser uniquement en Wi-Fi',
            },
          ],
        },
        key: 'UserState.syncWifiOnly',
        editable: true,
        translations: [
          {
            language: 'fr',
            name: 'Synchronisation Wi-Fi',
          },
        ],
      },
    ],
  },
  {
    id: 2,
    name: 'Geolocation Settings',
    icon: 'map-outline',
    translations: [
      {
        language: 'fr',
        name: 'Paramètres de géolocalisation',
      },
    ],
    fields: [
      {
        id: 41,
        type: 'number',
        name: 'gpsThreshold',
        label: 'GPS threshold',
        group: 'settingsSectionLocation',
        unit: 'm',
        description: {
          name: 'GPS threshold in meters',
          translations: [
            {
              language: 'fr',
              name: 'Seuil GPS en mètres',
            },
          ],
        },
        key: 'BuildParamsState.gpsThreshold',
        editable: true,
        translations: [
          {
            language: 'fr',
            name: 'Seuil GPS',
          },
        ],
      },
      {
        id: 42,
        type: 'dropdown',
        name: 'gpsAccuracyLevel',
        label: 'Accuracy level',
        group: 'settingsSectionLocation',
        levelKind: 'accuracy',
        description: {
          name: 'The level of location manager accuracy',
          translations: [
            {
              language: 'fr',
              name: 'Le niveau de précision du gestionnaire de localisation.',
            },
          ],
        },
        key: 'BuildParamsState.gpsAccuracyLevel',
        editable: true,
        translations: [
          {
            language: 'fr',
            name: 'Niveau de précision',
          },
        ],
        options: accuracyLevels.sort((a, b) => b.value - a.value),
      },
      {
        id: 43,
        type: 'number',
        name: 'geoLocationTimeout',
        label: 'Geolocation timeout',
        group: 'settingsSectionLocation',
        unit: 's',
        description: {
          name: 'Timeout for taking points on geolocation questions in seconds',
          translations: [
            {
              language: 'fr',
              name: "Délai d'expiration pour prendre des points sur les questions de géolocalisation en secondes",
            },
          ],
        },
        key: 'BuildParamsState.geoLocationTimeout',
        editable: true,
        translations: [
          {
            language: 'fr',
            name: "Délai d'expiration de la géolocalisation",
          },
        ],
      },
    ],
  },
  {
    id: 3,
    name: 'Image Quality',
    icon: 'camera-outline',
    translations: [
      {
        language: 'fr',
        name: "Qualité de l'image",
      },
    ],
    fields: [
      {
        id: 51,
        type: 'dropdown',
        name: 'imageQuality',
        label: 'Compression Level',
        group: 'settingsSectionPhotos',
        levelKind: 'imageQuality',
        description: {
          name: 'Higher compression = smaller files, faster sync',
          translations: [
            {
              language: 'fr',
              name: 'Compression plus élevée = fichiers plus petits, synchronisation plus rapide',
            },
          ],
        },
        key: 'BuildParamsState.imageQuality',
        editable: true,
        translations: [
          {
            language: 'fr',
            name: 'Niveau de compression',
          },
        ],
        options: imageQualityOptions,
      },
      {
        id: 52,
        type: 'switch',
        name: 'saveToGallery',
        label: 'Save photos to gallery',
        group: 'settingsSectionPhotos',
        description: {
          name: 'Keep a copy in the device gallery so a lost photo can be recovered',
          translations: [
            {
              language: 'fr',
              name: "Conserver une copie dans la galerie de l'appareil pour pouvoir récupérer une photo perdue",
            },
          ],
        },
        key: 'BuildParamsState.saveToGallery',
        editable: true,
        translations: [
          {
            language: 'fr',
            name: 'Enregistrer les photos dans la galerie',
          },
        ],
      },
    ],
  },
];

// Also read by the in-form language menu (form/support/SaveDropdownMenu.js).
export const langConfig = {
  type: 'dropdown',
  name: 'lang',
  label: 'Language',
  description: 'Application language',
  options: [
    {
      label: 'English',
      value: 'en',
    },
    {
      label: 'Français',
      value: 'fr',
    },
  ],
};
