# Knowledge Base Maintenance Procedure (SOP)

This document establishes the systematic, repeatable procedure for keeping the Akvo MIS AI Knowledge Base provably complete and synchronized with upstream source code repositories.

---

## 1. Trigger Conditions for KB Updates

A knowledge base audit and recompilation is required whenever any of the following occur:
1. **Upstream Schema Updates**: New properties, field types, or dependency operators are added to `akvo-react-form`.
2. **Editor Enhancements**: New props, UI controls, or parameters are added to `akvo-react-form-editor`.
3. **Platform Releases**: New features, workflows, or documentation pages are added to `akvo-mis/docs/source/*.rst` or `frontend/`.

---

## 2. 4-Phase Maintenance Lifecycle

```
┌──────────────────────────────┐
│ Phase 1: Source Inventory    │ ➔ Extract all props, types, and RST headings
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ Phase 2: Matrix Mapping      │ ➔ Map 100% of items to docs/knowledge_base/*.md
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ Phase 3: Content & Verify    │ ➔ Author/update markdown with inline audit notes
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ Phase 4: Sync & Ingest       │ ➔ Run ./kb.sh sync to compile PDF & Vector Store
└──────────────────────────────┘
```

---

## 3. Step-by-Step Execution Workflow

### Step 1: Inventory Diffing (Phase 1)
Run an automated diff against upstream READMEs:
```bash
# Check akvo-react-form README
git diff HEAD upstream/main -- frontend/node_modules/akvo-react-form/README.md

# Check akvo-react-form-editor README
git diff HEAD upstream/main -- frontend/node_modules/akvo-react-form-editor/README.md
```
Extract any newly added props, field types, or options into the inventory matrix.

### Step 2: Update Target Markdown Files (Phase 2 & 3)
- Update or create the target `.md` file under `docs/knowledge_base/`.
- Ensure standard formatting: `#`/`##`/`###` headings, `-` bullet points, and `|` tables.
- Avoid nested code blocks in bullet points or inline images.
- Include the inline audit citation: `(source: repo/file.md#section)`.

### Step 3: Coverage Verification
Verify that every inventory item maps to at least one file and section in `docs/knowledge_base/`.

### Step 4: Compile and Upload
Execute the synchronized build and vector store upload script:
```bash
./kb.sh sync
```
Verify that:
1. `akvo-mis-docs.pdf` compiles without errors from RST sources.
2. `akvo-react-form-editor-docs.pdf` compiles all modules from `docs/knowledge_base/`.
3. The OpenAI Vector Store confirms status: `completed`.
