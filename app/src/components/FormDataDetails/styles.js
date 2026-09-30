import { StyleSheet } from 'react-native';

/**
 * Styles shared by the FormDataDetails presentational components.
 * Accepts a theme object for dark-mode support.
 */
const getStyles = (theme) =>
  StyleSheet.create({
    title: {
      fontWeight: '700',
      fontSize: 14,
      marginBottom: 4,
    },
    containerImage: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      padding: 16,
      backgroundColor: theme ? theme.bg.surfaceElevated1 : '#FFFFFF',
      borderWidth: 1,
      borderTopColor: 'transparent',
      borderLeftColor: 'transparent',
      borderRightColor: 'transparent',
      borderBottomColor: theme ? theme.border.divider : '#C0C0C0',
    },
    image: {
      width: '100%',
      height: 200,
      aspectRatio: 1,
    },
    missingText: {
      color: theme ? theme.status.error : '#b91c1c',
      marginBottom: 8,
    },
    buttonRow: {
      flexDirection: 'column',
      gap: 8,
    },
    repairButton: {
      flex: 1,
    },
    processingContainer: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: 12,
      gap: 8,
    },
    processingText: {
      color: theme ? theme.buttonGhost.color : 'dodgerblue',
      fontSize: 14,
    },
    listItem: {
      flexDirection: 'row',
      padding: 16,
      backgroundColor: theme ? theme.bg.surfaceElevated1 : '#FFFFFF',
      borderBottomWidth: 1,
      borderBottomColor: theme ? theme.border.listDivider : '#e0e0e0',
    },
    listItemContent: {
      flex: 1,
    },
    listItemTitle: {
      fontSize: 16,
      fontWeight: 'bold',
      marginBottom: 4,
    },
  });

export default getStyles;
