.. raw:: html

    <style>
      .bolditalic {font-style: italic; font-weight: 700;}
    </style>

.. role:: bolditalic

===========================
Form Builder Best Practices
===========================

A few habits make forms easier to analyse, safer to change, and more pleasant to
fill in — especially on mobile. This page collects the ones that matter most.

.. contents::
   :local:
   :depth: 1

Naming and variable conventions
-------------------------------

- Give each question a clear, stable :bolditalic:`Question Name` (variable
  name). It appears in exports and in calculated fields, so consistency pays off.
- Avoid renaming a variable after data has been collected — exports and
  autofields reference it by name.
- Use short, descriptive names (``household_size``, not ``q7``) so exported
  columns are self-explanatory.

Structuring question groups
---------------------------

- Group related questions together; a group becomes a clear section on both web
  and mobile.
- Use :bolditalic:`repeatable` groups for lists — for example one entry per
  water point or per household member — instead of duplicating questions.
- Keep groups reasonably short. Very long groups are tiring to scroll on a
  phone.

Required fields and dependencies
--------------------------------

- Mark a question :bolditalic:`required` only when an answer is genuinely
  mandatory. Over-using "required" frustrates respondents and encourages junk
  answers.
- Remember that a required question inside skip logic is enforced only when it is
  visible (see :doc:`dependencies`).

Publishing and versioning discipline
------------------------------------

- Always check a form on the :bolditalic:`Preview` tab before publishing.
- Editing a published form creates a new version; publish deliberately and let
  field teams know when a form has changed.
- Prefer additive changes (new questions) over removing or renaming existing
  ones, so historical data stays comparable across versions.

Mobile considerations
----------------------

- Long option lists and many images increase the data the mobile app must sync;
  keep option lists focused.
- Test the form on the mobile app before rolling it out to field teams — screen
  size, GPS and photo capture behave differently than on the web.

.. note::
   **Keeping this page in sync.** Review this guidance against the Form Builder
   design documents ``doc/design/FB-001`` through ``FB-007`` when Form Builder
   features change.
