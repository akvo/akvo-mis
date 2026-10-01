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
import useTheme from '../lib/theme';

const AddUser = ({ navigation }) => {
  const theme = useTheme();
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
    await formsUrl.reduce(async (prev, form) => {
      await prev;
      const formRes = await api.get(form.url);
      await crudForms.upsertForm(db, {
        ...form,
        userId: userID,
        formJSON: formRes?.data,
      });
      if (formRes?.data?.cascades?.length) {
        await Promise.allSettled(
          formRes.data.cascades.map((cascadeFile) => {
            const downloadUrl = api.getConfig().baseURL + cascadeFile;
            return cascades.download(downloadUrl, cascadeFile);
          }),
        );
      }
    }, Promise.resolve());
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
          <Icon name="arrow-back" size={18} color={theme.topNav.icon} />
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
              <Text style={[styles.label, { color: theme.text.primary }]}>
                {`${trans.addUserPasscode} `}
                <Text style={{ color: theme.status.error }}>*</Text>
              </Text>
              <Input
                placeholder={trans.addUserPasscode}
                onChangeText={(value) => setFieldValue('name', value)}
                errorMessage={<ErrorMessage name="name" />}
                value={values.name}
                name="name"
                testID="input-name"
                containerStyle={[styles.input, { borderColor: theme.border.divider }]}
              />
            </View>

            <View style={styles.buttonContainer}>
              <Button
                onPress={handleSubmit}
                loading={loading}
                disabled={isSubmitting}
                testID="button-save"
                buttonStyle={{ backgroundColor: theme.buttonPrimary.bg }}
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
  input: {
    borderWidth: 1,
    borderRadius: 4,
    padding: 8,
  },
  buttonContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    paddingHorizontal: 16,
  },
});

export default AddUser;
