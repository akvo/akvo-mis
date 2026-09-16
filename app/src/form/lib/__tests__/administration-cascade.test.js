import { transformForm } from '../index';

/**
 * `extra.type` is a cascade SUB-type: "administration" or "entity". A filter that keeps
 * questions with no `extra.type` at all, meaning to let ordinary questions through,
 * silently drops every administration cascade — which is how a required Location question
 * disappeared from the form, renumbered the questions after it, and then reached the
 * server unanswered to be refused forever.
 */
const administrationQuestion = {
  id: 104,
  name: 'location',
  label: 'Location',
  order: 4,
  type: 'cascade',
  required: true,
  extra: { type: 'administration' },
  source: { file: 'administrator.sqlite', parent_id: [1] },
};

const entityQuestion = {
  id: 110,
  name: 'school',
  label: 'School',
  order: 5,
  type: 'cascade',
  required: false,
  extra: { type: 'entity' },
};

const plainQuestion = {
  id: 105,
  name: 'example_geolocation',
  label: 'Geolocation',
  order: 5,
  type: 'geo',
  required: true,
};

const buildForm = (question) => ({
  name: 'Test Form',
  defaultLanguage: 'en',
  question_group: [{ id: 1, name: 'registration', label: 'Registration', order: 1, question }],
});

const renderedIds = (form, prevAdmAnswer = null) =>
  transformForm(form, {}, 'en', {}, prevAdmAnswer)
    ?.question_group?.flatMap((qg) => qg.question)
    ?.map((q) => q.id) || [];

describe('administration cascade rendering', () => {
  it('renders an administration cascade', () => {
    const ids = renderedIds(buildForm([administrationQuestion, plainQuestion]));
    expect(ids).toContain(104);
  });

  it('keeps the questions after it in place', () => {
    const ids = renderedIds(buildForm([administrationQuestion, plainQuestion]));
    // Dropping 104 used to close the gap, so Geolocation took its number on screen.
    expect(ids).toEqual([104, 105]);
  });

  it('still renders plain questions that carry no extra', () => {
    const ids = renderedIds(buildForm([plainQuestion]));
    expect(ids).toEqual([105]);
  });

  it('hides an entity cascade until an administration answer exists', () => {
    const ids = renderedIds(buildForm([entityQuestion, plainQuestion]));
    expect(ids).not.toContain(110);
  });

  it('reveals the entity cascade once an administration answer exists', () => {
    const ids = renderedIds(buildForm([entityQuestion, plainQuestion]), [1]);
    expect(ids).toContain(110);
  });
});
