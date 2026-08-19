import { accuracyLevels } from '../../lib/loc';

// Define quality options inline to avoid importing expo-image-manipulator at module load time
const imageQualityOptions = [
  { label: 'Low', value: 'low' },
  { label: 'Medium', value: 'medium' },
  { label: 'High', value: 'high' },
  { label: 'Original', value: 'original' },
];

export const config = [
  {
    id: 1,
    name: 'Advanced',
    translations: [
      {
        language: 'fr',
        name: 'Avancée',
      },
    ],
    description: {
      name: 'Server URL, Auth Code, Sync Interval, Sync Wifi',
      translations: [
        {
          language: 'fr',
          name: "URL du serveur, code d'authentification, intervalle de synchronisation, synchronisation Wifi",
        },
      ],
    },
    fields: [
      {
        id: 11,
        type: 'text',
        label: 'Server URL',
        name: 'serverURL',
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
        label: 'Sync interval',
        description: {
          name: 'Sync interval in seconds',
          translations: [
            {
              language: 'fr',
              name: 'Intervalle de synchronisation en secondes',
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
        label: 'Sync Wifi',
        name: 'syncWifiOnly',
        description: {
          name: 'Sync Wifi only',
          translations: [
            {
              language: 'fr',
              name: 'Synchroniser le Wi-Fi uniquement',
            },
          ],
        },
        key: 'UserState.syncWifiOnly',
        editable: true,
        translations: [
          {
            language: 'fr',
            name: 'Synchroniser le Wi-Fi uniquement',
          },
        ],
      },
    ],
  },
  {
    id: 2,
    name: 'Geolocation',
    translations: [
      {
        language: 'fr',
        name: 'Géolocalisation',
      },
    ],
    description: {
      name: 'GPS threshold, Accuracy Level, Geolocation timeout',
      translations: [
        {
          language: 'fr',
          name: "Seuil GPS, Niveau de précision, Délai d'expiration de géolocalisation",
        },
      ],
    },
    fields: [
      {
        id: 41,
        type: 'number',
        name: 'gpsThreshold',
        label: 'GPS threshold',
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
        label: 'Geolocation Timeout',
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
    translations: [
      {
        language: 'fr',
        name: "Qualité de l'image",
      },
    ],
    description: {
      name: 'Image compression settings for sync',
      translations: [
        {
          language: 'fr',
          name: "Paramètres de compression d'image pour la synchronisation",
        },
      ],
    },
    fields: [
      {
        id: 51,
        type: 'dropdown',
        name: 'imageQuality',
        label: 'Compression Level',
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
      label: 'French',
      value: 'fr',
    },
  ],
};
