import React from 'react';
import * as ImagePicker from 'expo-image-picker';
import { PermissionsAndroid } from 'react-native';
import { renderHook, render, fireEvent, waitFor, act } from '@testing-library/react-native';
import * as MediaLibrary from 'expo-media-library';
import TypeImage from '../TypeImage';
import { FormState, BuildParamsState } from '../../../store';

jest.mock('react-native/Libraries/PermissionsAndroid/PermissionsAndroid', () => ({
  PERMISSIONS: {
    READ_EXTERNAL_STORAGE: 'android.permission.READ_EXTERNAL_STORAGE',
    CAMERA: 'android.permission.CAMERA',
  },
  RESULTS: {
    GRANTED: 'granted',
    DENIED: 'denied',
  },
  check: jest.fn().mockResolvedValue(true),
  request: jest.fn().mockResolvedValue('granted'),
}));

jest.mock('expo-image-picker', () => ({
  launchImageLibraryAsync: jest.fn(() =>
    Promise.resolve({ assets: [{ uri: 'file://example.jpg', base64: 'dummybase64' }] }),
  ),
  launchCameraAsync: jest.fn(() =>
    Promise.resolve({ assets: [{ uri: 'file://captured.jpeg', base64: 'dummyCamerabase64' }] }),
  ),
}));
jest.mock('expo-font');
jest.mock('expo-asset');

jest.mock('expo-media-library', () => ({
  requestPermissionsAsync: jest.fn(() => Promise.resolve({ granted: true })),
  createAssetAsync: jest.fn(() => Promise.resolve({ id: 'asset-1' })),
  getAlbumAsync: jest.fn(() => Promise.resolve(null)),
  createAlbumAsync: jest.fn(() => Promise.resolve({ id: 'album-1' })),
  addAssetsToAlbumAsync: jest.fn(() => Promise.resolve(true)),
}));

describe('TypeImage component', () => {
  beforeAll(() => {
    FormState.update((s) => {
      s.lang = 'en';
    });
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render correctly by default', () => {
    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { getByTestId, queryByText, queryByTestId } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
      />,
    );
    const questionText = queryByText('Latrine photo');
    expect(questionText).toBeDefined();

    const buttonUseCamera = getByTestId('btn-use-camera');
    expect(buttonUseCamera).toBeDefined();

    const imagePreview = queryByTestId('image-preview');
    expect(imagePreview).toBeNull();
  });

  it('should render correctly when useGallery is true', () => {
    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { getByTestId, queryByText, queryByTestId } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
        useGallery
      />,
    );
    const questionText = queryByText('Latrine photo');
    expect(questionText).toBeDefined();

    const buttonUseCamera = getByTestId('btn-use-camera');
    expect(buttonUseCamera).toBeDefined();

    const buttonFromGallery = getByTestId('btn-from-gallery');
    expect(buttonFromGallery).toBeDefined();

    const imagePreview = queryByTestId('image-preview');
    expect(imagePreview).toBeNull();
  });

  it('should not ask read storage permission when get image from gallery', async () => {
    const fieldID = 'imageField';
    const { result } = renderHook(() => FormState.useState((s) => s.currentValues));
    const mockValues = result.current;
    const mockOnChange = jest.fn();
    const { getByTestId, queryByTestId, rerender } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
        useGallery
      />,
    );

    const buttonFromGallery = getByTestId('btn-from-gallery');
    act(() => {
      fireEvent.press(buttonFromGallery);
      FormState.update((s) => {
        s.currentValues = { [fieldID]: 'file://example.jpg' };
      });
    });
    rerender(
      <TypeImage
        onChange={mockOnChange}
        value={result.current?.[fieldID]}
        keyform={1}
        id={fieldID}
        label="Latrine photo"
        useGallery
      />,
    );

    await waitFor(() => {
      expect(PermissionsAndroid.request).not.toHaveBeenCalled();
      expect(mockOnChange).toHaveBeenCalledWith(fieldID, 'file://example.jpg');
      const imagePreview = queryByTestId('image-preview');
      expect(imagePreview).toBeDefined();
      expect(imagePreview.props.source.uri).toBe('file://example.jpg');
    });
  });

  it('should be cancelable when the image set from the gallery', async () => {
    ImagePicker.launchImageLibraryAsync.mockImplementation(() =>
      Promise.resolve({ canceled: true }),
    );

    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { getByTestId, queryByTestId } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
        useGallery
      />,
    );

    const buttonFromGallery = getByTestId('btn-from-gallery');
    fireEvent.press(buttonFromGallery);

    await act(async () => {
      await ImagePicker.launchImageLibraryAsync();
    });

    await waitFor(() => {
      expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalled();
      const imagePreview = queryByTestId('image-preview');
      expect(imagePreview).toBeNull();
    });
  });

  it('should ask camera permission when Use Camera button clicked', async () => {
    PermissionsAndroid.check.mockResolvedValueOnce(false);
    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { getByTestId } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
      />,
    );

    const buttonUseCamera = getByTestId('btn-use-camera');
    fireEvent.press(buttonUseCamera);
    await act(async () => {
      await PermissionsAndroid.request();
    });

    const mockPermissionAndroindRequest = {
      buttonNegative: 'Cancel',
      buttonNeutral: 'Ask Me Later',
      buttonPositive: 'OK',
      message: 'App needs access to your camera',
      title: 'You need to give storage permission to download and save the file',
    };

    await waitFor(() => {
      expect(PermissionsAndroid.request).toHaveBeenCalledWith(
        PermissionsAndroid.PERMISSIONS.CAMERA,
        mockPermissionAndroindRequest,
      );
    });
  });

  it('should not ask camera permission when its granted ', async () => {
    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { getByTestId, queryByTestId, rerender } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
      />,
    );

    const buttonUseCamera = getByTestId('btn-use-camera');

    act(() => {
      fireEvent.press(buttonUseCamera);
    });

    rerender(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value="file://captured.jpeg"
        id={fieldID}
        label="Latrine photo"
      />,
    );

    await waitFor(() => {
      expect(PermissionsAndroid.request).not.toHaveBeenCalled();
      expect(PermissionsAndroid.check).toHaveBeenCalledWith(PermissionsAndroid.PERMISSIONS.CAMERA);
      expect(PermissionsAndroid.check).toBeTruthy();
      expect(mockOnChange).toHaveBeenCalledWith(fieldID, 'file://captured.jpeg');

      const imagePreview = queryByTestId('image-preview');
      expect(imagePreview).toBeDefined();
      expect(imagePreview.props.source.uri).toBe('file://captured.jpeg');
    });
  });

  it('should not trigger onChange when camera permission was denied', async () => {
    PermissionsAndroid.check.mockResolvedValueOnce(false);
    PermissionsAndroid.request.mockImplementation(() =>
      Promise.resolve(PermissionsAndroid.RESULTS.DENIED),
    );

    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { getByTestId } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
      />,
    );

    const buttonUseCamera = getByTestId('btn-use-camera');
    fireEvent.press(buttonUseCamera);

    let accessStatus = null;
    await act(async () => {
      accessStatus = await PermissionsAndroid.request();
    });

    const mockPermissionAndroindRequest = {
      buttonNegative: 'Cancel',
      buttonNeutral: 'Ask Me Later',
      buttonPositive: 'OK',
      message: 'App needs access to your camera',
      title: 'You need to give storage permission to download and save the file',
    };

    await waitFor(() => {
      expect(PermissionsAndroid.request).toHaveBeenCalledWith(
        PermissionsAndroid.PERMISSIONS.CAMERA,
        mockPermissionAndroindRequest,
      );
      expect(accessStatus).toEqual(PermissionsAndroid.RESULTS.DENIED);
      expect(mockOnChange).not.toHaveBeenCalled();
    });
  });

  it('should be cancelable when capturing image from camera', async () => {
    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { getByTestId, queryByTestId } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
      />,
    );

    const buttonUseCamera = getByTestId('btn-use-camera');
    fireEvent.press(buttonUseCamera);

    ImagePicker.launchCameraAsync.mockImplementation(() => Promise.resolve({ canceled: true }));

    await act(async () => {
      await ImagePicker.launchCameraAsync();
    });

    await waitFor(() => {
      expect(ImagePicker.launchCameraAsync).toHaveBeenCalled();
      const imagePreview = queryByTestId('image-preview');
      expect(imagePreview).toBeNull();
    });
  });

  it('should be able to remove image', () => {
    const fieldID = 'imageField';
    const mockValues = { [fieldID]: '/images/initial.jpg' };
    const mockOnChange = jest.fn();
    const { getByTestId, queryByTestId, rerender } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
      />,
    );
    const imagePreview = queryByTestId('image-preview');
    expect(imagePreview).toBeDefined();

    const buttonRemove = getByTestId('btn-remove');
    expect(buttonRemove).toBeDefined();
    fireEvent.press(buttonRemove);

    rerender(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={null}
        id={fieldID}
        label="Latrine photo"
      />,
    );

    expect(queryByTestId('image-preview')).toBeNull();
  });

  it('should not show required sign if required param is false and requiredSign is not defined', () => {
    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { queryByTestId } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
        required={false}
      />,
    );

    const requiredIcon = queryByTestId('field-required-icon');
    expect(requiredIcon).toBeFalsy();
  });

  it('should not show required sign if required param is false but requiredSign is defined', () => {
    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { queryByTestId } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
        required={false}
        requiredSign="*"
      />,
    );

    const requiredIcon = queryByTestId('field-required-icon');
    expect(requiredIcon).toBeFalsy();
  });

  it('should show required sign if required param is true and requiredSign defined', () => {
    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { queryByTestId } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
        required
        requiredSign="*"
      />,
    );

    const requiredIcon = queryByTestId('field-required-icon');
    expect(requiredIcon).toBeTruthy();
  });

  it('should show required sign with custom requiredSign', () => {
    const fieldID = 'imageField';
    const mockValues = { [fieldID]: null };
    const mockOnChange = jest.fn();
    const { getByText } = render(
      <TypeImage
        onChange={mockOnChange}
        keyform={1}
        value={mockValues[fieldID]}
        id={fieldID}
        label="Latrine photo"
        required
        requiredSign="**"
      />,
    );

    const requiredIcon = getByText('**');
    expect(requiredIcon).toBeTruthy();
  });

  describe('save to gallery', () => {
    const fieldID = 'imageField';

    const renderField = (onChange = jest.fn()) =>
      render(
        <TypeImage onChange={onChange} keyform={1} value={null} id={fieldID} label="Site photo" />,
      );

    const capturePhoto = async (getByTestId) => {
      fireEvent.press(getByTestId('btn-use-camera'));
      await waitFor(() => {
        expect(ImagePicker.launchCameraAsync).toHaveBeenCalled();
      });
    };

    // T26 — the setting is off by default, so the library is never touched
    it('never calls the media library when saveToGallery is off', async () => {
      act(() => {
        BuildParamsState.update((s) => {
          s.saveToGallery = 0;
        });
      });
      const { getByTestId } = renderField();

      await capturePhoto(getByTestId);

      expect(MediaLibrary.requestPermissionsAsync).not.toHaveBeenCalled();
      expect(MediaLibrary.createAssetAsync).not.toHaveBeenCalled();
    });

    it('requests write-only permission and files the asset under the apkName album', async () => {
      act(() => {
        BuildParamsState.update((s) => {
          s.saveToGallery = 1;
          s.apkName = 'Akvo MIS';
        });
      });
      const { getByTestId } = renderField();

      await capturePhoto(getByTestId);

      await waitFor(() => {
        expect(MediaLibrary.requestPermissionsAsync).toHaveBeenCalledWith(true);
        expect(MediaLibrary.createAlbumAsync).toHaveBeenCalledWith(
          'Akvo MIS',
          expect.anything(),
          false,
        );
      });
    });

    it('adds to the existing album rather than creating a duplicate', async () => {
      act(() => {
        BuildParamsState.update((s) => {
          s.saveToGallery = 1;
        });
      });
      MediaLibrary.getAlbumAsync.mockResolvedValueOnce({ id: 'album-1' });
      const { getByTestId } = renderField();

      await capturePhoto(getByTestId);

      await waitFor(() => {
        expect(MediaLibrary.addAssetsToAlbumAsync).toHaveBeenCalled();
      });
      expect(MediaLibrary.createAlbumAsync).not.toHaveBeenCalled();
    });

    // T27 — a denied permission must not cost the enumerator their answer
    it('still sets the answer when permission is denied', async () => {
      act(() => {
        BuildParamsState.update((s) => {
          s.saveToGallery = 1;
        });
      });
      MediaLibrary.requestPermissionsAsync.mockResolvedValueOnce({ granted: false });
      const mockOnChange = jest.fn();
      const { getByTestId } = renderField(mockOnChange);

      await capturePhoto(getByTestId);

      await waitFor(() => {
        expect(mockOnChange).toHaveBeenCalled();
      });
      expect(MediaLibrary.createAssetAsync).not.toHaveBeenCalled();
    });

    it('still sets the answer when the gallery write throws', async () => {
      act(() => {
        BuildParamsState.update((s) => {
          s.saveToGallery = 1;
        });
      });
      MediaLibrary.createAssetAsync.mockRejectedValueOnce(new Error('no space'));
      const mockOnChange = jest.fn();
      const { getByTestId } = renderField(mockOnChange);

      await capturePhoto(getByTestId);

      // The throw is swallowed and reported to Sentry; asserting the report needs
      // a spy, and the shared mock in setup-test-env.js is a plain function.
      // What matters here is that the answer survives the failure.
      await waitFor(() => {
        expect(mockOnChange).toHaveBeenCalled();
      });
    });

    // T28 — a picked photo is already in the gallery
    it('does not copy back a photo picked from the gallery', async () => {
      act(() => {
        BuildParamsState.update((s) => {
          s.saveToGallery = 1;
        });
      });
      const { getByTestId } = render(
        <TypeImage
          onChange={jest.fn()}
          keyform={1}
          value={null}
          id={fieldID}
          label="Site photo"
          useGallery
        />,
      );

      fireEvent.press(getByTestId('btn-from-gallery'));

      await waitFor(() => {
        expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalled();
      });
      expect(MediaLibrary.createAssetAsync).not.toHaveBeenCalled();
    });
  });
});
