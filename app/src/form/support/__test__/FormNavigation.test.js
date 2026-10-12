import React from 'react';
import { ToastAndroid } from 'react-native';
import { act, render, fireEvent, waitFor } from '@testing-library/react-native';
import FormNavigation from '../FormNavigation';
import { FormState } from '../../../store';

jest
  .useFakeTimers({
    doNotFake: [
      'nextTick',
      'setImmediate',
      'clearImmediate',
      'setInterval',
      'clearInterval',
      'setTimeout',
      'clearTimeout',
    ],
  })
  .setSystemTime(new Date('2024-03-15'));
jest.mock('expo-font');
jest.mock('expo-asset');
// Pulled in transitively via src/lib; their native modules are absent under Jest.
jest.mock('expo-task-manager', () => ({}));
jest.mock('expo-background-task', () => ({}));

const firstGroup = {
  name: 'registration',
  label: 'Registration',
  order: 1,
  question: [
    {
      id: 11,
      name: 'your_name',
      label: 'Your Name',
      order: 1,
      type: 'input',
      required: true,
      meta: true,
    },
  ],
};

const lastGroup = {
  name: 'hygiene',
  label: 'Hygiene',
  order: 2,
  question: [
    {
      id: 21,
      name: 'water_available',
      label: 'Water available?',
      order: 1,
      type: 'option',
      required: true,
      meta: true,
      option: [
        {
          id: 211,
          label: 'Yes',
          value: 'yes',
          order: 1,
        },
        {
          id: 212,
          label: 'No',
          value: 'no',
          order: 2,
        },
      ],
    },
  ],
};

const optionalGeoshapeGroup = {
  name: 'plot',
  label: 'Plot',
  order: 1,
  question: [
    {
      id: 31,
      name: 'your_name',
      label: 'Your Name',
      order: 1,
      type: 'input',
      required: true,
      meta: true,
    },
    {
      id: 32,
      name: 'boundary',
      label: 'Plot boundary',
      order: 2,
      type: 'geoshape',
      required: false,
    },
  ],
};

describe('FormNavigation component', () => {
  it('renders form navigation correctly', () => {
    const setActiveGroup = jest.fn();
    const onSubmit = jest.fn();
    const mockSetShowQuestionGroupList = jest.fn();
    const mockShowDialog = jest.fn();

    const { getByTestId, getByText, queryByTestId } = render(
      <FormNavigation
        currentGroup={firstGroup}
        activeGroup={0}
        setActiveGroup={setActiveGroup}
        onSubmit={onSubmit}
        totalGroup={2}
        showQuestionGroupList={false}
        setShowQuestionGroupList={mockSetShowQuestionGroupList}
        setShowDialogMenu={mockShowDialog}
      />,
    );

    const btnBack = getByTestId('form-nav-btn-back');
    expect(btnBack).toBeDefined();

    const groupCounter = getByTestId('form-nav-group-count');
    expect(groupCounter).toBeDefined();
    expect(getByText('1/2')).toBeDefined();

    const btnNext = getByTestId('form-nav-btn-next');
    expect(btnNext).toBeDefined();

    const btnSubmit = queryByTestId('form-btn-submit');
    expect(btnSubmit).toBeNull();
  });

  it('should move to the next page', async () => {
    const setActiveGroup = jest.fn();
    const onSubmit = jest.fn();
    const mockSetShowQuestionGroupList = jest.fn();
    const mockShowDialog = jest.fn();

    const { getByTestId, queryByTestId, rerender } = render(
      <FormNavigation
        currentGroup={firstGroup}
        activeGroup={0}
        setActiveGroup={setActiveGroup}
        onSubmit={onSubmit}
        totalGroup={2}
        showQuestionGroupList={false}
        setShowQuestionGroupList={mockSetShowQuestionGroupList}
        setShowDialogMenu={mockShowDialog}
      />,
    );

    act(() => {
      FormState.update((s) => {
        s.currentValues = {
          ...s.currentValues,
          11: 'John Doe',
        };
      });
    });

    const btnNext = getByTestId('form-nav-btn-next');
    expect(btnNext).toBeDefined();

    fireEvent.press(btnNext);

    rerender(
      <FormNavigation
        currentGroup={lastGroup}
        activeGroup={1}
        setActiveGroup={setActiveGroup}
        onSubmit={onSubmit}
        totalGroup={2}
        showQuestionGroupList={false}
        setShowQuestionGroupList={mockSetShowQuestionGroupList}
        setShowDialogMenu={mockShowDialog}
      />,
    );

    await waitFor(() => {
      expect(setActiveGroup).toHaveBeenCalledTimes(1);
      expect(setActiveGroup).toHaveBeenCalledWith(1);
      const btnSubmit = queryByTestId('form-btn-submit');
      expect(btnSubmit).toBeDefined();
    });
  });

  it('should disable navigation button when group list show', async () => {
    const setActiveGroup = jest.fn();
    const onSubmit = jest.fn();
    const mockSetShowQuestionGroupList = jest.fn();
    const mockShowDialog = jest.fn();

    const { getByTestId } = render(
      <FormNavigation
        currentGroup={firstGroup}
        activeGroup={0}
        setActiveGroup={setActiveGroup}
        onSubmit={onSubmit}
        totalGroup={2}
        showQuestionGroupList
        setShowQuestionGroupList={mockSetShowQuestionGroupList}
        setShowDialogMenu={mockShowDialog}
      />,
    );

    const btnBack = getByTestId('form-nav-btn-back');
    expect(btnBack).toBeDefined();
    expect(btnBack.props.accessibilityState.disabled).toBeTruthy();

    const btnNext = getByTestId('form-nav-btn-next');
    expect(btnNext).toBeDefined();
    expect(btnNext.props.accessibilityState.disabled).toBeTruthy();
  });

  /**
   * GEO-001 touchpoint 7. An unanswered question defaults to '' unless its type is in the
   * defaultVal list, and '' against the geoshape array schema is a type error. Navigation is
   * never blocked (see #136), so the symptom is quiet: a spurious error toast and the field
   * marked invalid in FormState.feedback for a polygon the enumerator was never required to
   * draw. Assert on the feedback, not on whether the group moved.
   */
  it('marks an untouched optional geoshape as valid, not errored', async () => {
    const { getByTestId } = render(
      <FormNavigation
        currentGroup={optionalGeoshapeGroup}
        activeGroup={0}
        setActiveGroup={jest.fn()}
        onSubmit={jest.fn()}
        totalGroup={2}
        showQuestionGroupList={false}
        setShowQuestionGroupList={jest.fn()}
        setShowDialogMenu={jest.fn()}
      />,
    );

    act(() => {
      FormState.update((s) => {
        // 32 is deliberately absent: the enumerator never opened the map.
        s.currentValues = { 31: 'John Doe' };
        s.feedback = {};
      });
    });

    fireEvent.press(getByTestId('form-nav-btn-next'));

    await waitFor(() => {
      expect(FormState.getRawState().feedback[32]).toBe(true);
    });
  });

  it('still flags a required geoshape that was never drawn', async () => {
    const requiredGroup = {
      ...optionalGeoshapeGroup,
      question: optionalGeoshapeGroup.question.map((q) =>
        q.id === 32 ? { ...q, required: true } : q,
      ),
    };

    const { getByTestId } = render(
      <FormNavigation
        currentGroup={requiredGroup}
        activeGroup={0}
        setActiveGroup={jest.fn()}
        onSubmit={jest.fn()}
        totalGroup={2}
        showQuestionGroupList={false}
        setShowQuestionGroupList={jest.fn()}
        setShowDialogMenu={jest.fn()}
      />,
    );

    act(() => {
      FormState.update((s) => {
        s.currentValues = { 31: 'John Doe' };
        s.feedback = {};
      });
    });

    fireEvent.press(getByTestId('form-nav-btn-next'));

    await waitFor(() => {
      expect(FormState.getRawState().feedback[32]).not.toBe(true);
    });
  });

  describe('submit', () => {
    const staffGroup = {
      id: 1,
      label: 'Staff',
      question: [{ id: 31, label: 'Number of staff', type: 'number', required: true }],
    };
    const formDefinition = { question_group: [staffGroup, lastGroup] };

    const renderLastGroup = () => {
      const handlers = {
        setActiveGroup: jest.fn(),
        onSubmit: jest.fn(),
        setShowQuestionGroupList: jest.fn(),
      };
      const utils = render(
        <FormNavigation
          currentGroup={lastGroup}
          formDefinition={formDefinition}
          activeGroup={1}
          setActiveGroup={handlers.setActiveGroup}
          onSubmit={handlers.onSubmit}
          totalGroup={2}
          showQuestionGroupList={false}
          setShowQuestionGroupList={handlers.setShowQuestionGroupList}
          setShowDialogMenu={jest.fn()}
        />,
      );
      return { ...utils, ...handlers };
    };

    const answer = (values) =>
      act(() => {
        FormState.update((s) => {
          s.currentValues = values;
        });
      });

    beforeEach(() => {
      jest.spyOn(ToastAndroid, 'show').mockImplementation(() => {});
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    it('names the invalid answer and opens its group when every field is filled', async () => {
      const { getByTestId, onSubmit, setActiveGroup, setShowQuestionGroupList } = renderLastGroup();
      answer({ 31: '2.5', 21: ['yes'] });

      fireEvent.press(getByTestId('form-btn-submit'));

      await waitFor(() => {
        expect(ToastAndroid.show).toHaveBeenCalledWith(
          'Staff: Number of staff must be an integer',
          ToastAndroid.LONG,
        );
      });
      expect(onSubmit).not.toHaveBeenCalled();
      expect(setActiveGroup).toHaveBeenCalledWith(0);
      expect(setShowQuestionGroupList).toHaveBeenCalledWith(false);
      expect(FormState.getRawState().feedback[31]).toBe('this must be an integer');
    });

    it('keeps the required-fields message when an answer is missing', async () => {
      const { getByTestId, onSubmit, setActiveGroup } = renderLastGroup();
      answer({ 21: ['yes'] });

      fireEvent.press(getByTestId('form-btn-submit'));

      await waitFor(() => {
        expect(ToastAndroid.show).toHaveBeenCalledWith(
          'Please complete all required fields in all sections before submitting',
          ToastAndroid.LONG,
        );
      });
      expect(onSubmit).not.toHaveBeenCalled();
      expect(setActiveGroup).toHaveBeenCalledWith(0);
    });

    it('submits when every answer is valid', async () => {
      const { getByTestId, onSubmit } = renderLastGroup();
      answer({ 31: '2', 21: ['yes'] });

      fireEvent.press(getByTestId('form-btn-submit'));

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledTimes(1);
      });
    });
  });
});
