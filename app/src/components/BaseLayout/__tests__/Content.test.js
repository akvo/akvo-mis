import React from 'react';
import { Text } from 'react-native';
import { render, fireEvent, within } from '@testing-library/react-native';
import Content from '../Content';

const data = [
  { id: 1, formId: 11, name: 'HH Form 1', version: '1.0.0', submitted: 2, draft: 1, synced: 2 },
  { id: 2, formId: 12, name: 'HH Form 2', version: '1.0.1', submitted: 4, draft: 0, synced: 3 },
];

const sections = [
  { key: 'latest', title: 'Latest submissions', data: [data[1]] },
  { key: 'earlier', title: 'Earlier submissions', data: [data[0]] },
];

describe('Content component', () => {
  it('renders each section as a counted, titled container with a card per form', () => {
    const { getByText, getByTestId } = render(<Content sections={sections} />);
    expect(getByText('Latest submissions')).toBeTruthy();
    expect(getByText('Earlier submissions')).toBeTruthy();
    expect(within(getByTestId('form-group-latest')).getByText('HH Form 2')).toBeTruthy();
    expect(within(getByTestId('form-group-earlier')).getByText('HH Form 1')).toBeTruthy();
    expect(within(getByTestId('section-header-latest')).getByText('1')).toBeTruthy();
  });

  it('closes the last visible section with the footer', () => {
    const footer = <Text>Add form</Text>;
    const { getByTestId, rerender } = render(<Content sections={sections} footer={footer} />);
    expect(within(getByTestId('form-group-earlier')).getByText('Add form')).toBeTruthy();
    rerender(<Content sections={[sections[0], { ...sections[1], data: [] }]} footer={footer} />);
    expect(within(getByTestId('form-group-latest')).getByText('Add form')).toBeTruthy();
  });

  it('leaves out a section without data', () => {
    const { queryByText } = render(
      <Content sections={[{ ...sections[0], data: [] }, sections[1]]} />,
    );
    expect(queryByText('Latest submissions')).toBeNull();
    expect(queryByText('Earlier submissions')).toBeTruthy();
  });

  it('collapses one section from its header and keeps its count', () => {
    const { getByTestId, queryByTestId } = render(<Content sections={sections} />);
    fireEvent.press(getByTestId('section-header-latest'));
    expect(queryByTestId('form-group-latest')).toBeNull();
    expect(queryByTestId('form-group-earlier')).toBeTruthy();
    expect(within(getByTestId('section-header-latest')).getByText('1')).toBeTruthy();
  });

  it('renders children when no section has data', () => {
    const { getByText } = render(
      <Content sections={[{ key: 'earlier', title: 'Earlier', data: [] }]}>
        <Text>Nothing here</Text>
      </Content>,
    );
    expect(getByText('Nothing here')).toBeTruthy();
  });

  it('calls action with the form id when a card is pressed', () => {
    const onPressMock = jest.fn();
    const { getByTestId } = render(<Content sections={sections} action={onPressMock} />);
    fireEvent.press(getByTestId('card-touchable-2'));
    expect(onPressMock).toHaveBeenCalledWith(2);
  });
});
