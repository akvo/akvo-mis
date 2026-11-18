# The LLM drafts the Proposal; deterministic code validates and applies it

In Data Onboarding, OpenAI only drafts the Proposal (forms, units to add, column-to-question mapping), and it works from a column profile: column names, inferred types, a value shape for each column (for example "10 digits" or "free text, about 40 characters"), and the distinct values of category-like columns (at most 30 distinct values). It never receives values from any other column. Deterministic code decides Ambiguous Administration, validates every answer, and loads values straight from the uploaded file.

We chose this because spreadsheets from data teams often carry personal data, LLM output can't be reproduced or audited row by row, and a wrong silent mapping would corrupt a tenant. The rejected alternative was sending rows to the LLM and loading its output. It is simpler, but it leaks data, costs more on large files, and makes skipped-row reasons unexplainable.

## Consequences

- Value cleaning (value maps, aliases, date formats) must be expressible in the Proposal and executed by code. The LLM can't fix individual cells.
- Value maps are possible only for category-like columns, because their values are the only ones the LLM sees.
- Ambiguity checks run again at Apply, because the tree may have changed since the Proposal was drafted.
