import { StyleSheet } from 'react-native';

/**
 * Styles shared by the FormDataDetails presentational components.
 * The list-row trio (listItem / listItemContent / listItemTitle) is also used by
 * the page's default answer branch, so it lives here rather than in the page.
 */
export default StyleSheet.create({
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
    backgroundColor: 'white',
    borderWidth: 1,
    borderTopColor: 'transparent',
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: 'silver',
  },
  image: {
    width: '100%',
    height: 200,
    aspectRatio: 1,
  },
  missingText: {
    color: '#b91c1c',
    marginBottom: 8,
  },
  buttonRow: {
    flexDirection: 'column',
    gap: 8,
  },
  repairButton: {
    // Even split so neither label truncates; "De la galerie" / "Reprendre la
    // photo" is the longest pair and fits at this width.
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
    color: 'dodgerblue',
    fontSize: 14,
  },
  listItem: {
    flexDirection: 'row',
    padding: 16,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
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
