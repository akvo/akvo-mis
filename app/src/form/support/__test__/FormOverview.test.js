import React from 'react';
import { render, act } from '@testing-library/react-native';
import FormOverview from '../FormOverview';
import { FormState } from '../../../store';

// The lib barrel pulls in background-task (ExpoTaskManager); ImageView only needs api.
jest.mock('../../../lib', () => ({
  api: { getConfig: () => ({ baseURL: 'http://localhost/api/v1/device' }) },
}));

jest.mock('../../../lib/cascades', () => ({
  loadDataSource: jest.fn((source, id) =>
    Promise.resolve({ id, full_path_name: 'Kenya|Nairobi|Westlands' }),
  ),
}));

// Mocked at the loader, not expo-asset: the row icons load fonts through expo-asset too.
jest.mock('../../../lib/map-draw-html', () => jest.fn(() => Promise.resolve('<html></html>')));

const formDefinition = {
  question_group: [
    {
      id: 1,
      name: 'group',
      label: 'Group',
      question: [
        { id: 11, name: 'name', label: 'Name', type: 'input' },
        { id: 12, name: 'photo', label: 'Photo', type: 'image' },
        { id: 13, name: 'sign', label: 'Signature', type: 'signature' },
        { id: 14, name: 'doc', label: 'Document', type: 'attachment' },
        { id: 15, name: 'plot', label: 'Plot', type: 'geoshape' },
        {
          id: 16,
          name: 'adm',
          label: 'Location',
          type: 'cascade',
          source: { file: 'administrator.sqlite' },
        },
        {
          id: 17,
          name: 'adm2',
          label: 'Other location',
          type: 'cascade',
          source: { file: 'administrator.sqlite' },
        },
      ],
    },
  ],
};

describe('FormOverview answers', () => {
  it('shows files and shapes as previews, not as raw paths or coordinates', async () => {
    act(() => {
      FormState.update((s) => {
        s.currentValues = {
          11: 'John Doe',
          12: 'file:///data/photo.jpg',
          13: 'data:image/png;base64,AAAA',
          14: 'file:///data/report.pdf',
          15: [
            [9.03, 38.74],
            [9.03, 38.75],
            [9.04, 38.75],
          ],
          16: [42],
          17: [43],
        };
        // 16 was rendered this session, so TypeCascade stored its name; 17 was not.
        s.cascades = { 16: 'Kenya|Kisumu' };
      });
    });

    const { getByTestId, findByTestId, getByText, findByText, queryByText } = render(
      <FormOverview
        formDefinition={formDefinition}
        onEditGroup={jest.fn()}
        onEditQuestion={jest.fn()}
      />,
    );

    expect(getByText('John Doe')).toBeTruthy();
    expect(getByTestId('overview-image-12').props.source.uri).toBe('file:///data/photo.jpg');
    expect(getByTestId('overview-image-13').props.source.uri).toBe('data:image/png;base64,AAAA');
    expect(getByTestId('overview-file-14').props.children).toBe('report.pdf');
    expect(await findByTestId('webview-geometry-15')).toBeTruthy();
    expect(queryByText('file:///data/photo.jpg')).toBeNull();
    expect(getByTestId('overview-cascade-16').props.children).toBe('Kenya|Kisumu');
    expect(await findByText('Kenya|Nairobi|Westlands')).toBeTruthy();
  });
});
