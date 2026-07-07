import { StyleSheet } from 'react-native';

const styles = StyleSheet.create({
  formContainer: {
    flex: 1,
  },
  questionGroupContainer: {
    marginBottom: 20,
  },
  fieldGroupHeader: {
    borderColor: 'grey',
    borderTopWidth: 0.5,
    borderBottomWidth: 0.5,
    display: 'flex',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    minHeight: 48,
  },
  fieldGroupName: {
    paddingLeft: 20,
    fontWeight: 'bold',
    fontSize: 14,
  },
  fieldGroupDescContainer: {
    backgroundColor: '#e5e7eb',
  },
  fieldGroupDescription: {
    fontSize: 14,
  },
  fieldGroupCopy: {
    paddingVertical: 12,
    paddingHorizontal: 22,
    backgroundColor: '#e5e7eb',
    borderWidth: 0.5,
    borderColor: 'grey',
    height: '100%',
  },
  questionContainer: {
    paddingHorizontal: 10,
    paddingVertical: 10,
  },
  validationErrorText: {
    paddingHorizontal: 10,
    marginTop: -15,
    color: 'red',
    fontStyle: 'italic',
  },
  fieldLabelContainer: {
    flex: 1,
    flexDirection: 'row',
  },
  fieldRequiredIcon: {
    color: 'red',
    paddingLeft: 10,
  },
  fieldLabel: {
    display: 'flex',
    flexDirection: 'column',
    paddingHorizontal: 10,
    marginBottom: 8,
    fontWeight: 600,
    fontSize: 14,
  },
  inputFieldContainer: {
    paddingHorizontal: 10,
    borderColor: 'grey',
    borderWidth: 0.5,
    borderRadius: 5,
    borderBottomWidth: 0.5,
  },
  inputFieldDisabled: {
    backgroundColor: '#e5e7eb',
    opacity: 0.5,
  },
  textAreaContainer: {
    paddingHorizontal: 10,
    borderColor: 'grey',
    borderWidth: 0.5,
    borderRadius: 5,
    borderBottomWidth: 0.5,
    minHeight: 120,
    alignItems: 'flex-start',
    paddingTop: 10,
  },
  radioFieldContainer: {
    backgroundColor: 'transparent',
    paddingVertical: 5,
    marginBottom: 0,
  },
  autoFieldContainer: {
    paddingHorizontal: 10,
    borderColor: 'grey',
    borderWidth: 0.5,
    borderRadius: 5,
    borderBottomWidth: 0.5,
    backgroundColor: '#f2f2f2',
  },
  radioFieldText: {
    fontWeight: 'normal',
  },
  optionContainer: {
    marginBottom: 25,
  },
  optionSelectedList: {
    backgroundColor: '#f2f2f2',
    padding: 10,
    marginLeft: 10,
    marginTop: 5,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  multipleOptionContainer: {
    marginBottom: 25,
  },
  dropdownField: {
    marginHorizontal: 10,
    paddingHorizontal: 10,
    paddingVertical: 2,
    borderColor: 'grey',
    borderWidth: 0.5,
    borderRadius: 5,
  },
  dropdownFieldDisabled: {
    backgroundColor: '#e5e7eb',
    opacity: 0.5,
  },
  dropdownSelectedList: {
    marginLeft: 10,
    marginRight: 0,
  },
  formNavigationButton: {
    borderTopColor: 'grey',
    borderTopWidth: 0.5,
    borderBottomWidth: 0,
  },
  formNavigationIcon: {
    paddingTop: 9,
    paddingBottom: 10,
  },
  formNavigationIconSubmit: {
    marginTop: -20,
    marginBottom: -20,
    paddingTop: 9,
    paddingBottom: 10,
    paddingRight: 15,
    marginRight: 0,
    marginLeft: 0,
  },
  formNavigationTitle: {
    paddingTop: 9,
    paddingBottom: 10,
    color: 'grey',
    fontWeight: 'normal',
    fontSize: 14,
    marginRight: -10,
    marginLeft: -10,
  },
  formNavigationSubmit: {
    paddingTop: 12,
    paddingBottom: 13,
    paddingRight: 10,
    color: '#ffffff',
    fontWeight: 'normal',
    fontSize: 14,
  },
  formNavigationGroupCount: {
    paddingTop: 13,
    paddingBottom: 10,
    color: 'grey',
    fontWeight: 'normal',
    fontSize: 14,
    marginRight: -10,
    marginLeft: -10,
  },
  formNavigationBgLight: {
    backgroundColor: '#f9fafb',
  },
  formNavigationBgPrimary: {
    backgroundColor: '#2089dc',
  },
  inputGeoContainer: {
    paddingHorizontal: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    marginBottom: 18,
  },
  questionGroupListContainer: {
    paddingTop: 24,
    flex: 1,
    width: '100%',
  },
  divider: {
    paddingHorizontal: 20,
    marginVertical: 7,
  },
  questionGroupListFormTitle: {
    paddingHorizontal: 20,
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  questionGroupListDataPointName: {
    paddingHorizontal: 20,
    fontSize: 16,
    marginBottom: 4,
  },
  questionGroupListItemWrapper: {
    display: 'flex',
    flexDirection: 'row',
    width: '100%',
    paddingVertical: 5,
    alignItems: 'center',
    paddingHorizontal: 10,
  },
  questionGroupListItemActive: {
    backgroundColor: '#E9E9E9',
  },
  questionGroupListItemIcon: {
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  questionGroupListItemName: {
    marginLeft: 10,
  },
  questionGroupListItemNameActive: {
    fontWeight: 'bold',
  },
  cascadeContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    marginBottom: 25,
  },
  cascadeValues: {
    opacity: 0,
    marginBottom: -16,
  },
  geoButtonGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  errorText: {
    color: 'red',
    fontStyle: 'italic',
  },
  repeatSectionContainer: {
    marginVertical: 10,
  },
  repeatDivider: {
    backgroundColor: '#dddddd',
    height: 1.5,
    marginVertical: 10,
  },
  repeatSectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 8,
    backgroundColor: '#f7f7f7',
    borderRadius: 5,
    marginBottom: 10,
  },
  repeatSectionTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#444444',
  },
  repeatSectionRemove: {
    padding: 5,
  },
});

export default styles;
