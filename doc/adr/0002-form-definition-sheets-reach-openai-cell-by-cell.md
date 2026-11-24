# A sheet that defines a form, not records, may reach OpenAI cell by cell

Teams often bring Data Onboarding a spreadsheet that describes a form: an XLSForm from Kobo or ODK, an Akvo Flow export, a paper survey, a question list. ADR 0001 sends OpenAI a column profile, which for such a file describes columns named "type", "label" and "Question type". OpenAI then models the definition rows as records, and the Proposal is useless.

We split it three ways:

- **XLSForm** (a `survey` sheet with `type` and `name` headers) is parsed by the form builder's own XLSForm import, with no OpenAI. It is the most common definition format, and parsing keeps its options, rules, conditions and repeats exactly.
- **Any other definition layout** goes to OpenAI cell by cell, so it can read layouts no parser knows. Code decides first which sheets these are: one of the first 10 rows has a header naming the question (`question`, `label`) and another header describing it (`type`, `options`, `mandatory`, `hint`, ...), and the sheet has at most 1,000 rows. Only those sheets are sent. The other sheets in the file are not read, and the Proposal notes say so.
- **Everything else** is data, profiled as ADR 0001 says.

We accept this because a definition holds questions and option lists, not anyone's records. The row cap keeps a large data sheet with question-like headers on the data path. The rejected alternatives: a parser for each layout, which can't keep up with the layouts teams bring, and keeping definitions out of Data Onboarding, which sends teams to the form builder's import, which handles XLSForm only.

## Consequences

- A definition's Proposal has forms and no data. Apply creates and publishes the forms and loads no rows; the Report lists them with 0 records.
- The Proposal's questions carry `tooltip`, `dependency` and `dependency_rule`, and its groups carry `repeatable`, so a definition's logic survives. Proposals stored before these fields existed get their defaults when they are next checked.
- A data sheet with question-like headers and at most 1,000 rows would be sent cell by cell. The header test needs two different definition headers to make this unlikely. A sheet described only by an "Answer" or "Response" column that holds answers (respondent | question | answer) is records; a paper survey leaves that column as lines to fill in.
- A file whose other sheet is headed by the definition's own cells (records beside their codebook) is data, so its records still load.
