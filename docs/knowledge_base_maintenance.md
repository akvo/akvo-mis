# Knowledge Base Maintenance & Coverage Audit Guide

This document establishes the systematic procedure and automated tooling for maintaining and auditing the Akvo MIS AI Knowledge Base (`docs/knowledge_base/`).

---

## 1. Overview & Audit Tooling

The knowledge base is continuously audited by a standalone verification tool:
- **Direct Script**: [`scripts/check_kb_coverage.py`](file:///Users/galihpratama/Sites/akvo-mis/scripts/check_kb_coverage.py)
- **Helper Command**: `./kb.sh check`

### Why This Exists
Instead of relying on reactive user reports for undocumented features, this tool extracts **100% of all properties, field types, and config parameters** from upstream libraries (`akvo-react-form`, `akvo-react-form-editor`) and verifies their presence in `docs/knowledge_base/**/*.md`.

---

## 2. Using `check_kb_coverage.py`

### Standard Human-Readable Audit
Run the check directly via `kb.sh` or the Python script:
```bash
./kb.sh check
# OR
./scripts/check_kb_coverage.py
```
**Output**: Displays a table-by-table inventory with pass/fail markers, percentage coverage, and an actionable list of any missing gaps.

---

### Detailed / Verbose Tracing
To see which specific `.md` file(s) satisfy each inventoried item:
```bash
./kb.sh check --verbose
# OR
./scripts/check_kb_coverage.py --verbose
```

---

### Structured JSON for CI / Tooling
To integrate the audit into CI pipelines or automated reporting:
```bash
./scripts/check_kb_coverage.py --format json > coverage_report.json
```
**Exit Codes for CI**:
- `0`: All inventoried items are 100% covered in the Knowledge Base.
- `1`: One or more items are missing (fails CI build).
- `2`: Missing source files or invalid directory arguments.

---

### Custom Source Paths
If auditing against sibling git checkouts instead of the installed `node_modules`:
```bash
./scripts/check_kb_coverage.py \
  --react-form-path ../akvo-react-form/README.md \
  --react-form-editor-path ../akvo-react-form-editor/README.md
```

---

### Optional Platform RST Headings Audit
To check if headings from `docs/source/*.rst` (user manual) are also present in the markdown KB:
```bash
./scripts/check_kb_coverage.py --include-rst
```

---

## 3. Step-by-Step Maintenance Lifecycle

When updating `akvo-react-form` or `akvo-react-form-editor`:

```
┌──────────────────────────────────────────────────────────┐
│ 1. Update Upstream Packages / Checkouts                  │
├──────────────────────────────────────────────────────────┤
│ 2. Run Coverage Audit: ./kb.sh check                     │
│    ➔ Identifies any new props or types (Gaps)            │
├──────────────────────────────────────────────────────────┤
│ 3. Update Markdown in docs/knowledge_base/*.md           │
│    ➔ Add property definitions & inline source citations  │
├──────────────────────────────────────────────────────────┤
│ 4. Re-run Audit: ./kb.sh check                           │
│    ➔ Confirms 100% coverage (Exit Code 0)                │
├──────────────────────────────────────────────────────────┤
│ 5. Compile & Synchronize Vector Store: ./kb.sh sync      │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Markdown Formatting Rules for KB Authors

1. **Standard Headings**: Use standard Markdown `#`, `##`, `###`.
2. **Lists & Bullets**: Use `-` or `*` with blank lines before and after lists.
3. **Data Tables**: Format tables using standard Markdown pipe syntax `| Prop | Type | Description |`. Avoid nested code fences inside list items.
4. **Traceable Citations**: Always include an inline audit citation for every table/feature, e.g.:
   `(source: akvo-react-form/README.md#question)`
