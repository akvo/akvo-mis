import React from 'react';
import { Image } from 'react-native';
import { render, act } from '@testing-library/react-native';
import EmptyState from '../EmptyState';
import { UIState } from '../../store';

const sources = (tree) =>
  tree.UNSAFE_getAllByType(Image).map((img) => JSON.stringify(img.props.source));

describe('EmptyState', () => {
  it.each(['light', 'dark'])('uses the %s artwork', (mode) => {
    act(() => {
      UIState.update((s) => {
        s.darkModePreference = mode;
      });
    });
    const tree = render(<EmptyState title="No forms yet" body="Add a form" />);
    expect(tree.getByText('No forms yet')).toBeTruthy();
    expect(tree.getByText('Add a form')).toBeTruthy();
    const [paper, arrow] = sources(tree);
    expect(paper).toContain(`paper-${mode}`);
    expect(arrow).toContain(`arrow-${mode}`);
  });

  it('leaves the arrow out when asked', () => {
    const tree = render(<EmptyState title="t" body="b" showArrow={false} testID="es" />);
    expect(tree.queryByTestId('es-arrow')).toBeNull();
    expect(sources(tree)).toHaveLength(1);
  });
});
