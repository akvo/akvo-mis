import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';

import ImageView from '../ImageView';

jest.mock('../../../lib', () => ({
  api: { getConfig: jest.fn(() => ({ baseURL: 'http://example.com/api/v1/any/' })) },
}));

const LOCAL_URI = 'file:///data/user/0/app/files/images/gone.jpg';
const REMOTE_URI = '/images/stored-on-server.jpg';

const baseProps = {
  label: 'Photo of water point',
  imageTestID: 'image-question-0',
  textTestID: 'text-question-0',
  missingText: 'Photo file is missing on this device.',
  loadFailedText: 'Photo could not be loaded.',
  retakeLabel: 'Retake photo',
  galleryLabel: 'From Gallery',
  tryAgainLabel: 'Try again',
};

// createElement rather than JSX spread: airbnb forbids react/jsx-props-no-spreading
const buildImageView = (props = {}) => React.createElement(ImageView, { ...baseProps, ...props });
const renderImageView = (props = {}) => render(buildImageView(props));

describe('ImageView', () => {
  it('renders the image and no error state before onError fires', () => {
    const { getByTestId, queryByTestId } = renderImageView({ uri: LOCAL_URI });

    expect(getByTestId('image-question-0')).toBeDefined();
    expect(queryByTestId('image-question-0-missing')).toBeNull();
    expect(queryByTestId('image-question-0-load-failed')).toBeNull();
  });

  // T2 — onError is the only thing that flips into the error state
  it('shows both repair buttons when a local file is missing', () => {
    const { getByTestId } = renderImageView({
      uri: LOCAL_URI,
      onRetake: jest.fn(),
      onPickGallery: jest.fn(),
    });

    fireEvent(getByTestId('image-question-0'), 'error');

    expect(getByTestId('image-question-0-missing')).toBeDefined();
    expect(getByTestId('image-question-0-retake')).toBeDefined();
    expect(getByTestId('image-question-0-gallery')).toBeDefined();
  });

  it('calls onPickGallery when the gallery button is pressed', () => {
    const onPickGallery = jest.fn();
    const { getByTestId } = renderImageView({ uri: LOCAL_URI, onPickGallery });

    fireEvent(getByTestId('image-question-0'), 'error');
    fireEvent.press(getByTestId('image-question-0-gallery'));

    expect(onPickGallery).toHaveBeenCalledTimes(1);
  });

  // T1 — the gallery button needs BOTH a handler and a local uri
  it('hides the gallery button when no handler is given', () => {
    const { getByTestId, queryByTestId } = renderImageView({
      uri: LOCAL_URI,
      onRetake: jest.fn(),
    });

    fireEvent(getByTestId('image-question-0'), 'error');

    expect(getByTestId('image-question-0-retake')).toBeDefined();
    expect(queryByTestId('image-question-0-gallery')).toBeNull();
  });

  // T15 — copy is chosen from the uri shape, not from a caller flag
  it('shows connection copy and no repair buttons for a remote uri', () => {
    const { getByTestId, queryByTestId } = renderImageView({
      uri: REMOTE_URI,
      onRetake: jest.fn(),
      onPickGallery: jest.fn(),
    });

    fireEvent(getByTestId('image-question-0'), 'error');

    expect(getByTestId('image-question-0-load-failed')).toBeDefined();
    expect(queryByTestId('image-question-0-missing')).toBeNull();
    expect(queryByTestId('image-question-0-retake')).toBeNull();
    expect(queryByTestId('image-question-0-gallery')).toBeNull();
  });

  // T16 — Try again clears the error and remounts the Image
  it('restores the image when Try again is pressed', () => {
    const { getByTestId, queryByTestId } = renderImageView({ uri: REMOTE_URI });

    fireEvent(getByTestId('image-question-0'), 'error');
    expect(getByTestId('image-question-0-load-failed')).toBeDefined();

    fireEvent.press(getByTestId('image-question-0-reload'));

    expect(queryByTestId('image-question-0-load-failed')).toBeNull();
    expect(getByTestId('image-question-0')).toBeDefined();
  });

  // The preview must appear after a pick without the parent remounting us —
  // the error state is derived from the uri, not a latched boolean.
  it('clears the error state when the uri is replaced', () => {
    const { getByTestId, queryByTestId, rerender } = renderImageView({
      uri: LOCAL_URI,
      onRetake: jest.fn(),
      onPickGallery: jest.fn(),
    });

    fireEvent(getByTestId('image-question-0'), 'error');
    expect(getByTestId('image-question-0-missing')).toBeDefined();

    rerender(
      buildImageView({
        uri: 'file:///data/user/0/app/files/images/picked.jpg',
        onRetake: jest.fn(),
        onPickGallery: jest.fn(),
      }),
    );

    expect(queryByTestId('image-question-0-missing')).toBeNull();
    expect(queryByTestId('image-question-0-gallery')).toBeNull();
    expect(getByTestId('image-question-0')).toBeDefined();
  });

  it('keeps the error state when an unrelated prop changes', () => {
    const { getByTestId, rerender } = renderImageView({ uri: LOCAL_URI, onRetake: jest.fn() });

    fireEvent(getByTestId('image-question-0'), 'error');
    rerender(buildImageView({ uri: LOCAL_URI, onRetake: jest.fn(), label: 'Renamed' }));

    expect(getByTestId('image-question-0-missing')).toBeDefined();
  });

  it('shows the processing spinner instead of any error state', () => {
    const { getByTestId, queryByTestId } = renderImageView({
      uri: LOCAL_URI,
      onRetake: jest.fn(),
      onPickGallery: jest.fn(),
      isRetaking: true,
      processingLabel: 'Compressing...',
    });

    expect(getByTestId('image-question-0-processing')).toBeDefined();
    expect(queryByTestId('image-question-0-retake')).toBeNull();
    expect(queryByTestId('image-question-0-gallery')).toBeNull();
  });
});
