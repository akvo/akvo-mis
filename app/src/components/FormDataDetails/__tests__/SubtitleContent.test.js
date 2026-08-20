import React from 'react';
import { render, waitFor } from '@testing-library/react-native';

import SubtitleContent from '../SubtitleContent';
import { QUESTION_TYPES } from '../../../lib/constants';

jest.mock('../../../lib', () => ({
  cascades: {
    loadDataSource: jest.fn(async () => ({ full_path_name: 'Fiji|Central|Suva' })),
  },
  i18n: {
    text: jest.fn(() => ({
      latitude: 'Latitude',
      longitude: 'Longitude',
      openFileButton: 'Open File',
    })),
  },
}));

describe('SubtitleContent', () => {
  it('renders latitude and longitude for a geo answer', () => {
    const { getByTestId } = render(
      <SubtitleContent index={0} type={QUESTION_TYPES.geo} answer={[-18.1416, 178.4419]} />,
    );

    expect(getByTestId('text-type-geo-0')).toBeDefined();
  });

  it('renders the resolved full path for a cascade answer', async () => {
    const { getByTestId } = render(
      <SubtitleContent
        index={1}
        type={QUESTION_TYPES.cascade}
        answer="65"
        source={{ file: 'administration.sqlite' }}
      />,
    );

    await waitFor(() => {
      expect(getByTestId('text-answer-1').props.children).toBe('Fiji|Central|Suva');
    });
  });

  it('formats a date answer', () => {
    const { getByTestId } = render(
      <SubtitleContent index={2} type={QUESTION_TYPES.date} answer="2026-07-17T14:05:00" />,
    );

    expect(getByTestId('text-answer-2').props.children).toBe('2026-07-17');
  });

  it('renders a dash for an empty date', () => {
    const { getByTestId } = render(
      <SubtitleContent index={3} type={QUESTION_TYPES.date} answer={null} />,
    );

    expect(getByTestId('text-answer-3').props.children).toBe('-');
  });

  it('maps option values to their labels', () => {
    const { getByTestId } = render(
      <SubtitleContent
        index={4}
        type={QUESTION_TYPES.option}
        answer={['yes']}
        option={[
          { value: 'yes', label: 'Yes' },
          { value: 'no', label: 'No' },
        ]}
      />,
    );

    expect(getByTestId('text-answer-4').props.children).toBe('Yes');
  });

  it('renders the file name and open button for an attachment answer', () => {
    const { getByTestId } = render(
      <SubtitleContent
        index={5}
        type={QUESTION_TYPES.attachment}
        answer="file:///files/attachments/report.pdf"
      />,
    );

    expect(getByTestId('text-answer-5').props.children).toBe('report.pdf');
    expect(getByTestId('open-file-button-5')).toBeDefined();
  });

  it('renders a dash for an empty attachment answer', () => {
    const { getByTestId } = render(
      <SubtitleContent index={6} type={QUESTION_TYPES.attachment} answer={null} />,
    );

    expect(getByTestId('text-type-attachment-6')).toBeDefined();
  });

  it('renders 0 rather than a dash for a zero answer', () => {
    const { getByTestId } = render(<SubtitleContent index={7} type="number" answer={0} />);

    expect(getByTestId('text-answer-7').props.children).toBe(0);
  });

  it('renders a dash for an empty default answer', () => {
    const { getByTestId } = render(<SubtitleContent index={8} type="input" answer="" />);

    expect(getByTestId('text-answer-8').props.children).toBe('-');
  });
});
