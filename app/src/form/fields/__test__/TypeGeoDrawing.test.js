import React from 'react';
import { act, render, fireEvent } from '@testing-library/react-native';
import { useNavigation } from '@react-navigation/native';

import TypeGeoDrawing from '../TypeGeoDrawing';
import { FormState } from '../../../store';
import { OVERLAP_STATUS, runOverlapCheck } from '../../lib/overlap-check';

jest.mock('@react-navigation/native');
jest.mock('expo-sqlite');
jest.mock('../../../lib/sync-datapoints', () => ({
  requestDatapointSync: jest.fn(() => Promise.resolve()),
}));
jest.mock('../../lib/overlap-check', () => ({
  ...jest.requireActual('../../lib/overlap-check'),
  runOverlapCheck: jest.fn(),
}));

const { requestDatapointSync } = require('../../../lib/sync-datapoints');

/** A question that has opted into overlap detection, which is what shows the Validate button. */
const OVERLAP_EXTRA = { geoConfig: { detectOverlaps: true } };

const triangle = [
  [9.03, 38.74],
  [9.03, 38.75],
  [9.04, 38.75],
];

describe('TypeGeoDrawing', () => {
  beforeEach(() => {
    act(() => {
      FormState.update((s) => {
        s.lang = 'en';
        s.polygonValidation = {};
        s.submissionUuid = 'self-uuid';
        s.overlapFormId = 123;
      });
    });
  });

  it('prompts when nothing has been captured', () => {
    const { getByTestId, queryByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" />,
    );
    expect(getByTestId('text-no-points')).toBeDefined();
    expect(queryByTestId('text-point-count')).toBeNull();
    expect(queryByTestId('text-area')).toBeNull();
  });

  it('shows the point count and area for a captured shape', () => {
    const { getByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value={triangle} />,
    );
    expect(getByTestId('text-point-count').props.children).toContain(3);
    expect(getByTestId('text-area')).toBeDefined();
  });

  it('withholds the area below three points', () => {
    const { queryByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value={triangle.slice(0, 2)} />,
    );
    expect(queryByTestId('text-point-count').props.children).toContain(2);
    expect(queryByTestId('text-area')).toBeNull();
  });

  it('tolerates a non-array value instead of crashing', () => {
    const { getByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value="" />,
    );
    expect(getByTestId('text-no-points')).toBeDefined();
  });

  it('opens the map screen with the current points', () => {
    const navigation = useNavigation();
    const { getByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value={triangle} />,
    );

    fireEvent.press(getByTestId('button-draw-on-map'));

    expect(navigation.navigate).toHaveBeenCalledWith('MapDrawView', {
      id: 42,
      value: triangle,
      name: 'Plot boundary',
      type: 'geoshape',
      extra: null,
    });
  });

  it('does not render a map of its own', () => {
    const { queryByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value={triangle} />,
    );
    expect(queryByTestId('webview-map-draw')).toBeNull();
  });

  it('passes the question type through to the map screen', () => {
    const navigation = useNavigation();
    const { getByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Route walked" type="geotrace" value={triangle} />,
    );

    fireEvent.press(getByTestId('button-draw-on-map'));

    expect(navigation.navigate).toHaveBeenCalledWith('MapDrawView', {
      id: 42,
      value: triangle,
      name: 'Route walked',
      type: 'geotrace',
      extra: null,
    });
  });

  /**
   * A geotrace is an open line: it encloses nothing, so reporting an area for it would be
   * a number with no meaning.
   */
  it('reports no area for a geotrace', () => {
    const { getByTestId, queryByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Route walked" type="geotrace" value={triangle} />,
    );
    expect(getByTestId('text-point-count').props.children).toContain(3);
    expect(queryByTestId('text-area')).toBeNull();
  });
});

describe('TypeGeoDrawing validation report (GEO-007)', () => {
  beforeEach(() => {
    // Not clearAllMocks: that resets the manual @react-navigation mock's return value.
    runOverlapCheck.mockReset();
    requestDatapointSync.mockClear();
    act(() => {
      FormState.update((s) => {
        s.lang = 'en';
        s.polygonValidation = {};
        s.submissionUuid = 'self-uuid';
        s.overlapFormId = 123;
        // FormState is global; a gate message left by the previous test would suppress the
        // report the next one is asserting on.
        s.feedback = {};
      });
    });
  });

  it('shows no Validate button on a question with no rules configured', () => {
    const { queryByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value={triangle} />,
    );
    // A plain geoshape must look exactly as it did in phase 1.
    expect(queryByTestId('button-validate-polygon')).toBeNull();
  });

  it('shows the Validate button once rules are configured', () => {
    const { getByTestId } = render(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={triangle}
        extra={OVERLAP_EXTRA}
      />,
    );
    expect(getByTestId('button-validate-polygon')).toBeDefined();
  });

  it('shows a green tick on a pass and no failure lines', async () => {
    runOverlapCheck.mockResolvedValue({ status: OVERLAP_STATUS.passed, conflicts: [] });
    const { getByTestId, queryByTestId } = render(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={triangle}
        extra={OVERLAP_EXTRA}
      />,
    );
    await act(async () => {
      fireEvent.press(getByTestId('button-validate-polygon'));
    });
    expect(getByTestId('text-polygon-validated')).toBeDefined();
    expect(queryByTestId('button-retry-sync')).toBeNull();
  });

  it('reports several conflicts as one numbered line, naming nobody', async () => {
    runOverlapCheck.mockResolvedValue({
      status: OVERLAP_STATUS.failed,
      conflicts: [
        { uuid: 'a', name: 'Plot A - Indonesia - Jakarta - Cawang', percent: 41.2, threshold: 20 },
        { uuid: 'b', name: 'Plot B - Indonesia - Jakarta - Cawang', percent: 22.5, threshold: 20 },
      ],
    });
    const { getByTestId, queryByTestId } = render(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={triangle}
        required
        extra={OVERLAP_EXTRA}
      />,
    );
    await act(async () => {
      fireEvent.press(getByTestId('button-validate-polygon'));
    });
    const line = getByTestId('text-polygon-report-overlapMany');
    expect(line.props.children).toContain('#1 (41.2%), #2 (22.5%)');
    // The generated datapoint name is every meta answer joined with " - ". It filled the
    // report on device and identified nothing, so it is not in the message any more.
    expect(line.props.children).not.toContain('Jakarta');
    expect(queryByTestId('text-polygon-validated')).toBeNull();
  });

  it('drops the blocking line from the report once the submit gate prints it', async () => {
    runOverlapCheck.mockResolvedValue({
      status: OVERLAP_STATUS.failed,
      conflicts: [{ uuid: 'a', name: 'Plot A', percent: 28.3, threshold: 20 }],
    });
    const { getByTestId, queryByTestId } = render(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={triangle}
        required
        extra={OVERLAP_EXTRA}
      />,
    );
    await act(async () => {
      fireEvent.press(getByTestId('button-validate-polygon'));
    });
    expect(getByTestId('text-polygon-report-overlap')).toBeDefined();

    // The gate speaks on submit; its message is the same sentence with the label prefixed.
    await act(async () => {
      FormState.update((s) => {
        s.feedback = { 42: 'Plot boundary: Overlaps 1 plot by 28.3% (limit 20%).' };
      });
    });
    expect(queryByTestId('text-polygon-report-overlap')).toBeNull();
  });

  it('refreshes the gate message when the points are retaken and validated again', async () => {
    runOverlapCheck.mockResolvedValue({
      status: OVERLAP_STATUS.failed,
      conflicts: [
        { uuid: 'a', name: 'Plot A', percent: 100, threshold: 20 },
        { uuid: 'b', name: 'Plot B', percent: 20.7, threshold: 20 },
      ],
    });
    const field = (value) => (
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={value}
        required
        extra={OVERLAP_EXTRA}
      />
    );
    const { getByTestId, rerender } = render(field(triangle));
    await act(async () => {
      fireEvent.press(getByTestId('button-validate-polygon'));
    });
    await act(async () => {
      FormState.update((s) => {
        s.feedback = { 42: 'Plot boundary: Overlaps 2 plots: #1 (100.0%), #2 (20.7%).' };
      });
    });

    // MapDrawView's Save writes the new points straight into the store, bypassing onChange.
    const retaken = [...triangle, [9.035, 38.745]];
    await act(async () => {
      rerender(field(retaken));
    });
    expect(FormState.getRawState().feedback[42]).not.toContain('#2');

    runOverlapCheck.mockResolvedValue({
      status: OVERLAP_STATUS.failed,
      conflicts: [{ uuid: 'a', name: 'Plot A', percent: 38.7, threshold: 20 }],
    });
    await act(async () => {
      fireEvent.press(getByTestId('button-validate-polygon'));
    });
    const message = FormState.getRawState().feedback[42];
    expect(message).toContain('38.7');
    expect(message).not.toContain('100.0');
  });

  it('offers Retry when sync can close the gap, and kicks a sync', async () => {
    runOverlapCheck.mockResolvedValue({
      status: OVERLAP_STATUS.unavailable,
      cause: 'syncIncomplete',
      retryable: true,
      conflicts: [],
    });
    const { getByTestId, queryByTestId } = render(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={triangle}
        required
        extra={OVERLAP_EXTRA}
      />,
    );
    await act(async () => {
      fireEvent.press(getByTestId('button-validate-polygon'));
    });
    expect(queryByTestId('text-polygon-validated')).toBeNull();
    await act(async () => {
      fireEvent.press(getByTestId('button-retry-sync'));
    });
    expect(requestDatapointSync).toHaveBeenCalled();
  });

  it('offers no Retry when the local database is the problem', async () => {
    runOverlapCheck.mockResolvedValue({
      status: OVERLAP_STATUS.unavailable,
      cause: 'localFailure',
      retryable: false,
      conflicts: [],
    });
    const { getByTestId, queryByTestId } = render(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={triangle}
        required
        extra={OVERLAP_EXTRA}
      />,
    );
    await act(async () => {
      fireEvent.press(getByTestId('button-validate-polygon'));
    });
    // A second tap cannot heal a corrupt database, so no Retry is offered (D-10).
    expect(queryByTestId('button-retry-sync')).toBeNull();
  });

  it('drops the green tick when the polygon is edited after a pass', async () => {
    runOverlapCheck.mockResolvedValue({ status: OVERLAP_STATUS.passed, conflicts: [] });
    const { getByTestId, queryByTestId, rerender } = render(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={triangle}
        extra={OVERLAP_EXTRA}
      />,
    );
    await act(async () => {
      fireEvent.press(getByTestId('button-validate-polygon'));
    });
    expect(getByTestId('text-polygon-validated')).toBeDefined();

    const moved = [...triangle.slice(0, 2), [9.041, 38.75]];
    rerender(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={moved}
        extra={OVERLAP_EXTRA}
      />,
    );
    expect(queryByTestId('text-polygon-validated')).toBeNull();
  });
});

describe('TypeGeoDrawing overlap review (GEO-008)', () => {
  const THRESHOLD_EXTRA = { geoConfig: { detectOverlaps: true, accuracyThreshold: 25 } };

  /** Coordinates and all: the screen draws from this array and never re-reads the datapoints. */
  const CONFLICTS = [
    {
      uuid: 'a',
      name: 'Plot A - Indonesia - Jakarta - Cawang',
      percent: '41.2',
      rawPercent: 41.2,
      threshold: '20.0',
      coordinates: [
        [9.031, 38.741, 30],
        [9.031, 38.751],
        [9.041, 38.751],
      ],
    },
  ];

  const renderFailed = async () => {
    runOverlapCheck.mockResolvedValue({ status: OVERLAP_STATUS.failed, conflicts: CONFLICTS });
    const view = render(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={triangle}
        extra={THRESHOLD_EXTRA}
      />,
    );
    await act(async () => {
      fireEvent.press(view.getByTestId('button-validate-polygon'));
    });
    return view;
  };

  beforeEach(() => {
    // Not clearAllMocks: that resets the manual @react-navigation mock's return value.
    runOverlapCheck.mockReset();
    act(() => {
      FormState.update((s) => {
        s.lang = 'en';
        s.polygonValidation = {};
        s.submissionUuid = 'self-uuid';
        s.overlapFormId = 123;
        s.feedback = {};
      });
    });
  });

  it('offers the map once an overlap has been reported', async () => {
    const { getByTestId } = await renderFailed();
    expect(getByTestId('button-review-overlaps')).toBeDefined();
  });

  /**
   * The error text says `#1 (41.2%)` and names nobody, so the map is the only way to find out
   * which plot that is. The labels are attached HERE, next to the check that produced them:
   * `conflictsForMap` and the message share one numbering function, and a screen that labelled
   * its own polygons could sort them differently and make `#1` mean two plots.
   */
  it('hands the map the conflicts already labelled and still carrying coordinates', async () => {
    const navigation = useNavigation();
    const { getByTestId } = await renderFailed();

    fireEvent.press(getByTestId('button-review-overlaps'));

    expect(navigation.navigate).toHaveBeenCalledWith('OverlapMapView', {
      value: triangle,
      conflicts: [
        {
          label: '#1',
          name: 'Plot A - Indonesia - Jakarta - Cawang',
          percent: '41.2',
          coordinates: [
            [9.031, 38.741, 30],
            [9.031, 38.751],
            [9.041, 38.751],
          ],
        },
      ],
      name: 'Plot boundary',
      type: 'geoshape',
      accuracyThreshold: 25,
    });
  });

  it('offers no map when the check passed', async () => {
    runOverlapCheck.mockResolvedValue({ status: OVERLAP_STATUS.passed, conflicts: [] });
    const { getByTestId, queryByTestId } = render(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={triangle}
        extra={THRESHOLD_EXTRA}
      />,
    );
    await act(async () => {
      fireEvent.press(getByTestId('button-validate-polygon'));
    });
    expect(queryByTestId('button-review-overlaps')).toBeNull();
  });

  /**
   * A verdict belongs to the geometry it was computed from. After an edit the stored conflicts
   * describe a shape that no longer exists, and a map of it would be confidently wrong - the
   * same reason the green tick drops out.
   */
  it('withdraws the map once the polygon is edited', async () => {
    const { getByTestId, queryByTestId, rerender } = await renderFailed();
    expect(getByTestId('button-review-overlaps')).toBeDefined();

    const moved = [...triangle.slice(0, 2), [9.041, 38.75]];
    rerender(
      <TypeGeoDrawing
        keyform={0}
        id={42}
        label="Plot boundary"
        value={moved}
        extra={THRESHOLD_EXTRA}
      />,
    );
    expect(queryByTestId('button-review-overlaps')).toBeNull();
  });
});
