import React, { useState, useRef, useEffect, useCallback } from 'react';
import { View, StyleSheet } from 'react-native';
import { Button, Input, Text } from '@rneui/themed';
import { Formik, ErrorMessage } from 'formik';
import * as Yup from 'yup';
import Icon from 'react-native-vector-icons/Ionicons';
import { useSQLiteContext } from 'expo-sqlite';

import { BaseLayout } from '../components';
import { UserState, UIState, AuthState } from '../store';
import { api, cascades, i18n } from '../lib';
import { crudForms, crudUsers, crudConfig } from '../database/crud';

const AddUser = ({ navigation }) => {
  const [loading, setLoading] = useState(false);
  const [userCount, setUserCount] = useState(0);
  const db = useSQLiteContext();

  const formRef = useRef();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const rightComponent = userCount ? null : false;

  const goToUsers = () => {
    navigation.navigate('Users');
  };

  const getUsersCount = useCallback(async () => {
    const rows = await crudUsers.getAllUsers(db);
    setUserCount(rows.length);
  }, [db]);

  const handleActiveUser = async (data = {}) => {
    const activeUser = await crudUsers.getActiveUser(db);
    if (activeUser?.id) {
      await crudUsers.toggleActive(db, activeUser);
    }
    const newUserId = await crudUsers.addNew(db, {
      name: data?.name || 'Data collector',
      active: 1,
      token: data?.syncToken,
      password: data?.passcode,
    });
    UserState.update((s) => {
      s.id = newUserId;
      s.name = data?.name;
      s.email = data?.email;
    });
    return newUserId;
  };

  const handleGetAllForms = async (formsUrl, userID) => {
    formsUrl.forEach(async (form) => {
      // Fetch form detail
      const formRes = await api.get(form.url);
      await crudForms.addForm(db, {
        ...form,
        userId: userID,
        formJSON: formRes?.data,
      });

      // download cascades files
      if (formRes?.data?.cascades?.length) {
        formRes.data.cascades.forEach((cascadeFile) => {
          const downloadUrl = api.getConfig().baseURL + cascadeFile;
          cascades.download(downloadUrl, cascadeFile);
        });
      }
    });
  };

  const submitData = async ({ name }) => {
    setLoading(true);
    try {
      const { length: exist } = await crudUsers.checkPasscode(db, name);
      if (exist) {
        formRef.current.setErrors({ name: trans.errorUserExist });
        setLoading(false);
      } else {
        const { data: apiData } = await api.post(
          '/auth',
          { code: name },
          { headers: { 'Content-Type': 'multipart/form-data' } },
        );
        // save session
        const bearerToken = apiData.syncToken;

        api.setToken(bearerToken);
        AuthState.update((s) => {
          s.token = bearerToken;
        });

        await crudConfig.updateConfig(db, { authenticationCode: name });

        const userID = await handleActiveUser({ ...apiData, passcode: name });

        await handleGetAllForms(apiData.formsUrl, userID);

        setLoading(false);

        setTimeout(() => {
          navigation.navigate('Home', { newForms: true });
        }, 500);
      }
    } catch {
      setLoading(false);
    }
  };
  const initialValues = {
    name: null,
  };
  const addSchema = Yup.object().shape({
    name: Yup.string().required(trans.errorUserNameRequired),
  });

  useEffect(() => {
    getUsersCount();
  }, [getUsersCount]);

  return (
    <BaseLayout
      title={trans.addUserPageTitle}
      leftComponent={
        <Button type="clear" onPress={goToUsers} testID="arrow-back-button">
          <Icon name="arrow-back" size={18} />
        </Button>
      }
      rightComponent={rightComponent}
    >
      <Formik
        initialValues={initialValues}
        validationSchema={addSchema}
        innerRef={formRef}
        onSubmit={async (values) => {
          try {
            await submitData(values);
          } finally {
            formRef.current.setSubmitting(false);
          }
        }}
      >
        {({ setFieldValue, values, handleSubmit, isSubmitting }) => (
          <BaseLayout.Content>
            <View style={styles.inputContainer}>
              <Text style={styles.label}>
                {`${trans.addUserPasscode} `}
                <Text style={styles.asterisk}>*</Text>
              </Text>
              <Input
                placeholder={trans.addUserPasscode}
                onChangeText={(value) => setFieldValue('name', value)}
                errorMessage={<ErrorMessage name="name" />}
                value={values.name}
                name="name"
                testID="input-name"
                containerStyle={styles.input}
              />
            </View>

            <View style={styles.buttonContainer}>
              <Button
                onPress={handleSubmit}
                loading={loading}
                disabled={isSubmitting}
                testID="button-save"
                buttonStyle={styles.button}
              >
                {loading ? trans.buttonSaving : trans.buttonSave}
              </Button>
            </View>
          </BaseLayout.Content>
        )}
      </Formik>
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  inputContainer: {
    marginBottom: 16,
  },
  label: {
    fontSize: 16,
    marginBottom: 8,
  },
  asterisk: {
    color: '#ff0000',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 4,
    padding: 8,
  },
  buttonContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    paddingHorizontal: 16,
  },
  button: {
    backgroundColor: '#007bff',
  },
});

export default AddUser;
