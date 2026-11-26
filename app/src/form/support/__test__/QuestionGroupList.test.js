/* eslint-disable react/prop-types */
import React from 'react';
import { render } from '@testing-library/react-native';
import QuestionGroupList, { countValidRequiredQuestions } from '../QuestionGroupList';

jest.useFakeTimers();
jest.mock('expo-font');
jest.mock('expo-asset');

// Transformed-form shape (label present, as transformForm would produce): three groups with
// 1, 2 and 1 required questions respectively (Q5 is optional).
const example = {
  name: 'Testing Form',
  question_group: [
    {
      id: 1,
      label: 'Group 1',
      question: [{ id: 1, name: 'q1', label: 'Q1', type: 'input', required: true }],
    },
    {
      id: 2,
      label: 'Group 2',
      question: [
        { id: 2, name: 'q2', label: 'Q2', type: 'input', required: true },
        { id: 3, name: 'q3', label: 'Q3', type: 'number', required: true },
      ],
    },
    {
      id: 3,
      label: 'Group 3',
      question: [
        { id: 4, name: 'q4', label: 'Q4', type: 'input', required: true },
        { id: 5, name: 'q5', label: 'Q5', type: 'text', required: false },
      ],
    },
  ],
};

describe('countValidRequiredQuestions (APP-598 per-group tally)', () => {
  it('counts required questions per group and overall, none filled when empty', async () => {
    const res = await countValidRequiredQuestions(example, {});
    expect(res.totalRequired).toBe(4);
    expect(res.groups.map((g) => g.required)).toEqual([1, 2, 1]);
    expect(res.totalFilled).toBe(0);
    expect(res.groups.every((g) => g.filled === 0)).toBe(true);
  });

  it('counts a satisfied required question as filled in its own group', async () => {
    const res = await countValidRequiredQuestions(example, { 1: 'Galih' });
    expect(res.groups[0].filled).toBe(1);
    expect(res.groups[1].filled).toBe(0);
    expect(res.totalFilled).toBe(1);
  });
});

describe('QuestionGroupList sheet', () => {
  it('renders the header and numbered group names when visible', () => {
    const { getByText, getAllByTestId } = render(
      <QuestionGroupList
        form={example}
        activeQuestionGroup={0}
        setActiveQuestionGroup={jest.fn()}
        setShowQuestionGroupList={jest.fn()}
        visible
      />,
    );
    expect(getByText('Question groups')).toBeDefined();
    expect(getByText('1 · Group 1')).toBeDefined();
    expect(getByText('2 · Group 2')).toBeDefined();
    expect(getByText('3 · Group 3')).toBeDefined();
    expect(getAllByTestId('question-group-list-item-wrapper')).toHaveLength(3);
  });

  it('marks the active group as Current', () => {
    const { getByText } = render(
      <QuestionGroupList
        form={example}
        activeQuestionGroup={1}
        setActiveQuestionGroup={jest.fn()}
        setShowQuestionGroupList={jest.fn()}
        visible
      />,
    );
    expect(getByText('Current')).toBeDefined();
  });
});
