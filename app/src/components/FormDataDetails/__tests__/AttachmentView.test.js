import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import * as FileSystem from 'expo-file-system';
import * as Linking from 'expo-linking';

import AttachmentView from '../AttachmentView';

jest.mock('expo-file-system');
jest.mock('expo-linking');

const LOCAL_URI = 'file:///data/user/0/app/files/attachments/report.pdf';

const baseProps = {
  label: 'Inspection report',
  index: 0,
  missingText: 'Attached file is missing on this device.',
  reattachLabel: 'Re-attach file',
  openLabel: 'Open File',
};

// createElement rather than JSX spread: airbnb forbids react/jsx-props-no-spreading
const renderAttachmentView = (props = {}) =>
  render(React.createElement(AttachmentView, { ...baseProps, ...props }));

describe('AttachmentView', () => {
  beforeEach(() => {
    FileSystem.getInfoAsync.mockResolvedValue({ exists: true });
    Linking.canOpenURL.mockResolvedValue(true);
    Linking.openURL.mockResolvedValue();
  });

  it('shows the file name and open button when the file exists', async () => {
    const { getByTestId, queryByTestId } = renderAttachmentView({ uri: LOCAL_URI });

    await waitFor(() => {
      expect(getByTestId('open-file-button-0')).toBeDefined();
    });
    expect(getByTestId('text-answer-0').props.children).toBe('report.pdf');
    expect(queryByTestId('attachment-missing-0')).toBeNull();
  });

  it('opens the file manager when the open button is pressed', async () => {
    const { getByTestId } = renderAttachmentView({ uri: LOCAL_URI });

    await waitFor(() => {
      expect(getByTestId('open-file-button-0')).toBeDefined();
    });
    fireEvent.press(getByTestId('open-file-button-0'));

    await waitFor(() => {
      expect(Linking.openURL).toHaveBeenCalledWith(LOCAL_URI);
    });
  });

  // Non-image files have no onError signal, so existence is checked explicitly
  it('shows the missing notice and re-attach button when the file is gone', async () => {
    FileSystem.getInfoAsync.mockResolvedValue({ exists: false });
    const { getByTestId } = renderAttachmentView({ uri: LOCAL_URI, onReattach: jest.fn() });

    await waitFor(() => {
      expect(getByTestId('attachment-missing-0')).toBeDefined();
      expect(getByTestId('attachment-reattach-0')).toBeDefined();
    });
  });

  it('treats a getInfoAsync rejection as missing', async () => {
    FileSystem.getInfoAsync.mockRejectedValue(new Error('boom'));
    const { getByTestId } = renderAttachmentView({ uri: LOCAL_URI, onReattach: jest.fn() });

    await waitFor(() => {
      expect(getByTestId('attachment-missing-0')).toBeDefined();
    });
  });

  it('hides the re-attach button when no handler is given', async () => {
    FileSystem.getInfoAsync.mockResolvedValue({ exists: false });
    const { getByTestId, queryByTestId } = renderAttachmentView({ uri: LOCAL_URI });

    await waitFor(() => {
      expect(getByTestId('attachment-missing-0')).toBeDefined();
    });
    expect(queryByTestId('attachment-reattach-0')).toBeNull();
  });

  it('never runs an existence check on a remote uri', async () => {
    const { getByTestId } = renderAttachmentView({ uri: '/attachments/report.pdf' });

    await waitFor(() => {
      expect(getByTestId('open-file-button-0')).toBeDefined();
    });
    expect(FileSystem.getInfoAsync).not.toHaveBeenCalled();
  });

  it('shows the processing spinner while re-attaching', () => {
    const { getByTestId } = renderAttachmentView({
      uri: LOCAL_URI,
      isReattaching: true,
      processingLabel: 'Compressing...',
    });

    expect(getByTestId('attachment-processing-0')).toBeDefined();
  });
});
