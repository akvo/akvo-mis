#!/usr/bin/env python3
"""
scripts/build_kb_pdf.py

Builds knowledge base PDFs for OpenAI Vector Store ingestion:
1. docs/build/akvo-mis-docs.pdf   - Full platform documentation
2. docs/build/akvo-react-form-editor-docs.pdf - Form Builder reference

Generates standard PDF 1.4 documents with structured pages and headers.
"""

import os
import re
from pathlib import Path


class SimplePDFWriter:
    """A lightweight, zero-dependency PDF 1.4 generator."""

    def __init__(self, title="Documentation"):
        self.title = title
        self.pages = []
        self.current_page_lines = []
        self.max_lines_per_page = 46

    def add_line(self, line=""):
        if len(self.current_page_lines) >= self.max_lines_per_page:
            self.pages.append(list(self.current_page_lines))
            self.current_page_lines = []
        self.current_page_lines.append(line)

    def add_heading(self, text, level=1):
        self.add_line("")
        prefix = "# " if level == 1 else "## " if level == 2 else "### "
        divider = "=" * 60 if level == 1 else "-" * 40 if level == 2 else ""
        self.add_line(f"{prefix}{text.upper() if level == 1 else text}")
        if divider:
            self.add_line(divider)
        self.add_line("")

    def add_paragraph(self, text):
        words = text.split()
        current_line = []
        current_len = 0
        for word in words:
            if current_len + len(word) + 1 > 80:
                self.add_line(" ".join(current_line))
                current_line = [word]
                current_len = len(word)
            else:
                current_line.append(word)
                current_len += len(word) + 1
        if current_line:
            self.add_line(" ".join(current_line))
        self.add_line("")

    def add_bullet(self, text, indent=0):
        """Add a bullet-point line, word-wrapping at 78 chars."""
        prefix = "  " * indent + "- "
        wrap_width = 78 - len(prefix)
        words = text.split()
        first = True
        current_line = []
        current_len = 0
        for word in words:
            if current_len + len(word) + 1 > wrap_width:
                self.add_line(
                    (prefix if first else " " * len(prefix))
                    + " ".join(current_line)
                )
                first = False
                current_line = [word]
                current_len = len(word)
            else:
                current_line.append(word)
                current_len += len(word) + 1
        if current_line:
            self.add_line(
                (prefix if first else " " * len(prefix))
                + " ".join(current_line)
            )

    def finalize(self):
        """Flush remaining lines into a page. Always ensure >= 1 page."""
        if self.current_page_lines:
            self.pages.append(list(self.current_page_lines))
            self.current_page_lines = []
        # Guarantee at least one page so xref table is valid
        if not self.pages:
            self.pages.append(["(empty document)"])

    def _escape_pdf_text(self, text):
        return (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .encode("latin-1", "replace")
            .decode("latin-1")
        )

    def write_to_file(self, filepath):
        self.finalize()
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        objects = []
        num_pages = len(self.pages)
        page_obj_ids = []
        content_obj_ids = []

        current_obj_id = 6
        for _ in range(num_pages):
            page_obj_ids.append(current_obj_id)
            content_obj_ids.append(current_obj_id + 1)
            current_obj_id += 2

        # Catalog & Outlines
        objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 3 0 R >>\nendobj\n")
        objects.append(b"2 0 obj\n<< /Type /Outlines /Count 0 >>\nendobj\n")

        # Pages parent
        kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        objects.append(
            f"3 0 obj\n<< /Type /Pages /Kids [ {kids_str} ] "
            f"/Count {num_pages} >>\nendobj\n".encode("latin-1")
        )

        # Fonts
        objects.append(
            b"4 0 obj\n<< /Type /Font /Subtype /Type1 /Name /F1 "
            b"/BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n"
        )
        objects.append(
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /Name /F2 "
            b"/BaseFont /Helvetica-Bold /Encoding "
            b"/WinAnsiEncoding >>\nendobj\n"
        )

        # Pages & content
        for idx in range(num_pages):
            p_obj_id = page_obj_ids[idx]
            c_obj_id = content_obj_ids[idx]
            lines = self.pages[idx]

            stream_parts = ["BT", "72 750 Td", "14 TL"]
            stream_parts.append("/F2 9 Tf")
            esc_title = self._escape_pdf_text(self.title)
            stream_parts.append(
                f"({esc_title} | Page {idx + 1} of {num_pages}) Tj"
            )
            stream_parts.append("T*")
            stream_parts.append("T*")

            for line in lines:
                if line.startswith("# "):
                    stream_parts.append("/F2 14 Tf")
                elif line.startswith("## "):
                    stream_parts.append("/F2 11 Tf")
                elif line.startswith("### "):
                    stream_parts.append("/F2 10 Tf")
                else:
                    stream_parts.append("/F1 9 Tf")
                stream_parts.append(f"({self._escape_pdf_text(line)}) Tj")
                stream_parts.append("T*")

            stream_parts.append("ET")
            stream_data = "\n".join(stream_parts).encode("latin-1", "replace")

            page_dict = (
                f"{p_obj_id} 0 obj\n"
                f"<< /Type /Page /Parent 3 0 R /MediaBox [ 0 0 612 792 ]\n"
                f"/Contents {c_obj_id} 0 R\n"
                f"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> >>\n"
                f"endobj\n"
            ).encode("latin-1")
            objects.append(page_dict)

            content_dict = (
                (
                    f"{c_obj_id} 0 obj\n"
                    f"<< /Length {len(stream_data)} >>\n"
                    f"stream\n"
                ).encode("latin-1")
                + stream_data
                + b"\nendstream\nendobj\n"
            )
            objects.append(content_dict)

        with open(filepath, "wb") as f:
            f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
            offsets = []
            current_offset = len(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

            for obj in objects:
                offsets.append(current_offset)
                f.write(obj)
                current_offset += len(obj)

            xref_offset = current_offset
            num_total_objs = len(objects) + 1
            f.write(b"xref\n")
            f.write(f"0 {num_total_objs}\n".encode("latin-1"))
            f.write(b"0000000000 65535 f \n")
            for off in offsets:
                f.write(f"{off:010d} 00000 n \n".encode("latin-1"))

            trailer = (
                f"trailer\n"
                f"<< /Size {num_total_objs} /Root 1 0 R >>\n"
                f"startxref\n"
                f"{xref_offset}\n"
                f"%%EOF\n"
            ).encode("latin-1")
            f.write(trailer)


# ---------------------------------------------------------------------------
# RST cleaning helpers
# ---------------------------------------------------------------------------


def extract_rst_heading(content: str) -> str:
    """Extract the first meaningful heading from RST content."""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("..") or stripped.startswith(":"):
            continue
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if (
                next_line
                and all(c in "=-~^+#*" for c in next_line)
                and len(next_line) >= 2
            ):
                return stripped
    return ""


def clean_rst_text(content: str) -> str:
    """Strip RST directives and formatting for clean plain text."""
    # Remove raw HTML blocks
    content = re.sub(r"\.\.\s+raw::\s+html[\s\S]*?(?=\n\.\.|$)", "", content)
    # Remove image/figure directives (multi-line with options)
    content = re.sub(r"\.\.\s+image::[^\n]*(?:\n[ \t]+[^\n]*)*", "", content)
    content = re.sub(r"\.\.\s+figure::[^\n]*(?:\n[ \t]+[^\n]*)*", "", content)
    # Remove toctree blocks
    content = re.sub(r"\.\.\s+toctree::[\s\S]*?(?=\n\n|\Z)", "", content)
    # Remove note/warning/tip/caution/important blocks
    content = re.sub(
        r"\.\.\s+(?:note|warning|tip|caution|important)::[^\n]*"
        r"(?:\n[ \t]+[^\n]*)*",
        "",
        content,
    )
    # Remove code-block directives (keep body text for context)
    content = re.sub(r"\.\.\s+code(?:-block)?::[^\n]*\n", "", content)
    # Remove contents directive
    content = re.sub(
        r"\.\.\s+contents::[^\n]*(?:\n[ \t]+[^\n]*)*", "", content
    )
    # Remove role/class definitions
    content = re.sub(r"\.\.\s+role::[^\n]*", "", content)
    content = re.sub(r"\.\.\s+class::[^\n]*", "", content)
    # Remove field list options (:alt:, :width:, :target:, etc.)
    content = re.sub(
        r"^[ \t]+:[a-zA-Z_-]+:.*$", "", content, flags=re.MULTILINE
    )
    # Remove inline roles like :bolditalic:`text` -> text
    content = re.sub(r":[a-zA-Z_-]+:`([^`]+)`", r"\1", content)
    # Remove RST heading underlines (===, ---, ~~~)
    content = re.sub(r"^[=\-~^#+*]{3,}\s*$", "", content, flags=re.MULTILINE)
    # Remove bold/italic markers
    content = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
    content = re.sub(r"\*([^*]+)\*", r"\1", content)
    # Remove backtick literals
    content = re.sub(r"``([^`]+)``", r"\1", content)
    # Remove hyperlink targets
    content = re.sub(r"^\.\.\s+_[^\n]+$", "", content, flags=re.MULTILINE)
    # Remove badge image references
    content = re.sub(
        r"^\.\.\s+\|[^|]+\|[^\n]*$", "", content, flags=re.MULTILINE
    )
    # Collapse multiple blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


# ---------------------------------------------------------------------------
# RST-sourced sections
# ---------------------------------------------------------------------------

RST_FILES = [
    "index.rst",
    "start.rst",
    "install.rst",
    "formBuilder.rst",
    "questionTypes.rst",
    "dependencies.rst",
    "formBuilderBestPractices.rst",
    "inputChannel.rst",
    "mobileApp.rst",
    "administration.rst",
    "approval.rst",
    "dataManagement.rst",
    "MasterDataManagement.rst",
    "outputs.rst",
    "download.rst",
    "deployment.rst",
]


def add_rst_section(pdf: SimplePDFWriter, source_dir: Path, fname: str):
    """Read one RST file, extract heading, add cleaned content to PDF."""
    fpath = source_dir / fname
    if not fpath.exists():
        print(f"  [skip] {fname} not found")
        return

    raw = fpath.read_text(encoding="utf-8", errors="replace")
    heading = extract_rst_heading(raw)
    if not heading:
        heading = fname.replace(".rst", "").replace("_", " ").title()

    cleaned = clean_rst_text(raw)
    pdf.add_heading(heading, level=2)

    for paragraph in cleaned.split("\n\n"):
        p = paragraph.strip()
        if p and len(p) > 5:
            pdf.add_paragraph(p)


# ---------------------------------------------------------------------------
# Form Editor supplementary PDF
# ---------------------------------------------------------------------------


def build_form_editor_docs_pdf(output_pdf: Path):
    """Generates akvo-react-form-editor-docs.pdf."""
    print(f"Building supplementary {output_pdf}...")
    pdf = SimplePDFWriter(title="Akvo MIS - Form Builder Guide")

    pdf.add_heading("Akvo Form Builder & Runtime Reference Guide", level=1)
    pdf.add_paragraph(
        "Technical reference for the Akvo MIS Form Builder. Covers the "
        "editor interface, question configuration, skip logic, form lifecycle, "
        "and all supported question types."
    )

    pdf.add_heading("1. Editor Interface Overview", level=2)
    pdf.add_paragraph(
        "Access the Form Builder editor from: Control Centre > Form Builder > "
        "(create or select a form). The editor has four workspace tabs:"
    )
    pdf.add_bullet(
        "Edit Form - the main drag-and-drop editor for question groups "
        "and questions"
    )
    pdf.add_bullet(
        "Translations - add translated labels and option text for "
        "multi-language forms"
    )
    pdf.add_bullet(
        "Preview - live preview of the form as respondents will see it; "
        "use this to test skip logic"
    )
    pdf.add_bullet(
        "JSON - view and optionally edit the raw form schema (advanced users)"
    )

    pdf.add_heading("2. Question Groups", level=2)
    pdf.add_paragraph(
        "Questions are organised into Question Groups, which become named "
        "sections in the web and mobile form. Every form must have at least "
        "one group."
    )
    pdf.add_bullet("Add Group - click + Add Group below the last group")
    pdf.add_bullet("Rename - click the group name to edit it in-place")
    pdf.add_bullet(
        "Repeatable - toggle Repeatable to allow enumerators to add multiple "
        "entries (e.g. one row per household member)"
    )
    pdf.add_bullet("Reorder - drag the group handle to change the order")
    pdf.add_bullet(
        "Delete - remove a group and all its questions "
        "(cannot be undone on a published form)"
    )

    pdf.add_heading("3. Question Configuration", level=2)
    pdf.add_paragraph(
        "Click any question to open its settings panel. Common settings:"
    )
    pdf.add_bullet("Label - the question text shown to the respondent")
    pdf.add_bullet(
        "Variable Name - internal identifier used in exports and autofields; "
        "must be unique within the form"
    )
    pdf.add_bullet(
        "Tooltip / Help Text - additional guidance shown below the question"
    )
    pdf.add_bullet(
        "Required - blocks submission until answered "
        "(ignored when hidden by skip logic)"
    )
    pdf.add_bullet(
        "Double Entry - prompts the respondent to enter the value twice; "
        "useful for critical numeric data"
    )
    pdf.add_paragraph("Type-specific settings:")
    pdf.add_bullet("Number: Min Value, Max Value")
    pdf.add_bullet("Text: character limit")
    pdf.add_bullet("Option / Multiple Option: add, remove, reorder choices")
    pdf.add_bullet("Cascade: select source data list")
    pdf.add_bullet(
        "Autofield: define formula using references to other variable names"
    )

    pdf.add_heading("4. Skip Logic (Dependencies)", level=2)
    pdf.add_paragraph(
        "Skip logic hides a question until a specific condition is met. "
        "Configured on the dependent question (the one shown conditionally)."
    )
    pdf.add_paragraph("To add skip logic:")
    pdf.add_bullet("1. Click the question that should be conditionally shown")
    pdf.add_bullet("2. Open its Skip Logic tab")
    pdf.add_bullet("3. Select the Source Question (trigger) from the dropdown")
    pdf.add_bullet(
        "4. Select the matching answer value that will reveal this question"
    )
    pdf.add_bullet("5. Save")
    pdf.add_paragraph(
        "Best practices: avoid circular dependencies, keep chains shallow, "
        "and always test in the Preview tab before publishing."
    )

    pdf.add_heading("5. Question Types Reference", level=2)
    types_info = [
        (
            "Text (Input)",
            "Single-line free text. For names, identifiers, short answers.",
        ),
        (
            "Text Area (Memo)",
            "Multi-line text. Use for descriptions, notes, long answers.",
        ),
        (
            "Number",
            "Integer or decimal. Supports Min/Max validation bounds.",
        ),
        (
            "Date",
            "Calendar date picker (YYYY-MM-DD). Use for visit dates, "
            "dates of birth.",
        ),
        (
            "Image / Photo",
            "Camera capture or file upload. Stored server-side with the "
            "submission.",
        ),
        (
            "Geo / Geopoint",
            "Latitude + Longitude capture. On mobile reads device GPS "
            "automatically.",
        ),
        (
            "Option",
            "Single choice (radio buttons). Configure allowed choices.",
        ),
        (
            "Multiple Option",
            "Multiple choice (checkboxes). Configure allowed choices.",
        ),
        (
            "Cascade",
            "Hierarchical dropdowns (e.g. Country > Province > District). "
            "Requires a configured cascade data source.",
        ),
        (
            "Entity",
            "Dropdown linked to an entity type (e.g. schools). Requires "
            "entity data to be configured.",
        ),
        (
            "Autofield",
            "Computed field derived from other answers via a formula. "
            "Not editable by the respondent.",
        ),
        (
            "Attachment",
            "File upload for non-image files (PDF, spreadsheet, etc).",
        ),
        (
            "Signature",
            "Hand-drawn signature pad; stored as an image.",
        ),
        (
            "Table",
            "Tabular grid of answers. Cannot be created in the Form Builder "
            "UI - must be defined in the form JSON.",
        ),
        (
            "Tree",
            "Nested hierarchical selector. Cannot be created in the "
            "Form Builder UI.",
        ),
        (
            "Administration",
            "Linked to the administration hierarchy. Cannot be created in "
            "the Form Builder UI.",
        ),
    ]
    for qtype, desc in types_info:
        pdf.add_bullet(f"{qtype}: {desc}")

    pdf.add_heading("6. Form Lifecycle", level=2)
    pdf.add_paragraph("Forms progress through these states:")
    pdf.add_bullet(
        "Draft - the form is being edited and cannot receive submissions"
    )
    pdf.add_bullet("Published - the form is live; enumerators can submit data")
    pdf.add_bullet(
        "Editing a published form - creates a new draft version; the previous "
        "version remains active until the new version is published"
    )
    pdf.add_paragraph("Two form types exist:")
    pdf.add_bullet(
        "Registration Form - creates a new data record (entity/location)"
    )
    pdf.add_bullet(
        "Monitoring Form - adds ongoing data points to an existing record "
        "via a parent_id reference"
    )

    pdf.add_heading("7. Form Import and Export", level=2)
    pdf.add_bullet(
        "Import JSON - upload a previously exported JSON schema to create "
        "a new form"
    )
    pdf.add_bullet(
        "Import XLSForm - upload an XLSForm Excel file to create a form "
        "from an external definition"
    )
    pdf.add_bullet(
        "Export JSON - download the raw JSON schema for the current form"
    )
    pdf.add_bullet(
        "Export XLSForm - download the form as an XLSForm-compatible Excel "
        "file (must be enabled in Settings)"
    )

    pdf.add_heading("8. Version History", level=2)
    pdf.add_paragraph(
        "Every time a draft is published a version snapshot is saved. "
        "Open the Version History drawer (clock icon, top-right of editor) "
        "to view previous versions. Older versions are read-only."
    )

    pdf.add_heading(
        "9. Field Prefix and Suffix (addonBefore / addonAfter)", level=2
    )
    pdf.add_paragraph(
        "You can display a small label directly before or after an answer box "
        "to give users context on what to type."
    )
    pdf.add_bullet(
        "Supported field types: Available on Input (text) and Number "
        "questions only."
    )
    pdf.add_bullet(
        "Prefix (addonBefore): Appears immediately before the input box. Use "
        "it for currency symbols ($), phone country codes (+62), or short "
        "text labels."
    )
    pdf.add_bullet(
        "Suffix (addonAfter): Appears immediately after the input box. Use it "
        "for measurement units like kg, %, or cm."
    )
    pdf.add_bullet(
        "Can we add icons? No. Field prefixes and suffixes accept plain text "
        "and symbols only. Images, icons, and graphic elements are not "
        "supported."
    )
    pdf.add_paragraph(
        "How to configure: Click the question in the Form Builder to open its "
        "settings panel, then type your desired prefix or suffix text into "
        "the setting field."
    )

    pdf.add_heading("10. Option Choice Color Coding", level=2)
    pdf.add_paragraph(
        "For single-choice (Option) and multi-choice (Multiple Option) "
        "questions, you can assign a visual color tag to each answer choice."
    )
    pdf.add_bullet(
        "Visual appearance: When respondents or reviewers view the form on "
        "the web, each choice is displayed with a colored badge or highlight."
    )
    pdf.add_bullet(
        "Color format: Uses standard hex color codes. For example: enter "
        "#00FF00 for green (such as a 'Pass' status), #FF0000 for red (such "
        "as a 'Fail' status), or #FFA500 for orange (such as 'Pending')."
    )
    pdf.add_bullet(
        "Submission impact: The color code is purely visual to help users "
        "quickly spot statuses. It does not alter how answer data is stored "
        "or exported."
    )
    pdf.add_paragraph(
        "How to configure: In the Form Builder settings panel for an Option "
        "question, open the option choices list and enter the hex color code "
        "for each choice."
    )

    pdf.add_heading(
        "11. Pre-filled Default Values on the Web (Cross-Question Copying)",
        level=2,
    )
    pdf.add_paragraph(
        "On web forms, an answer can automatically copy data from an earlier "
        "question in the same form session."
    )
    pdf.add_bullet(
        "What it does: When a respondent types an answer into Question A, "
        "Question B can automatically populate with the same answer in real "
        "time."
    )
    pdf.add_bullet(
        "Example use case: Automatically copying a respondent's Name into a "
        "subsequent Confirmation or Signature section."
    )
    pdf.add_bullet(
        "Availability note: This cross-question prefilling runs in the web "
        "browser. It is currently configured in the form definition schema "
        "(using the 'pre' setting) and is not yet available as a visual toggle "
        "in the Form Builder editor."
    )

    pdf.add_heading(
        "12. Pre-filled Fields on Mobile (Registration to Monitoring)",
        level=2,
    )
    pdf.add_paragraph(
        "When using the Akvo MIS mobile app for fieldwork, monitoring forms "
        "can automatically show information recorded during the initial "
        "registration."
    )
    pdf.add_bullet(
        "Mobile-only feature: Automatic registration-to-monitoring "
        "pre-filling is specifically built into the Akvo MIS mobile app. "
        "It is not active on web browser forms."
    )
    pdf.add_bullet(
        "How it works: When an enumerator selects an existing data point on "
        "their mobile device and starts a linked Monitoring Form, known "
        "details (such as the facility name or GPS location) are pre-populated "
        "so the enumerator only updates changed information."
    )
    pdf.add_bullet(
        "Configuration: No special setup is needed in the Form Builder. "
        "Linking a Monitoring Form to a Registration Form enables this "
        "workflow automatically on mobile."
    )

    pdf.write_to_file(output_pdf)
    print(f"Generated: {output_pdf} ({output_pdf.stat().st_size:,} bytes)")


# ---------------------------------------------------------------------------
# Platform docs main builder (strictly from docs/source/*.rst)
# ---------------------------------------------------------------------------


def build_platform_docs_pdf(docs_dir: Path, output_pdf: Path):
    """Parses docs/source/*.rst -> akvo-mis-docs.pdf."""
    print(f"Building {output_pdf} from RST source files...")
    pdf = SimplePDFWriter(title="Akvo MIS - Platform Documentation")

    pdf.add_heading("Akvo MIS Platform Documentation", level=1)
    pdf.add_paragraph(
        "Comprehensive user and administrator guide for Akvo MIS - a Real-Time "
        "Monitoring Information System. Covers form design, data collection, "
        "approvals, administration, and mobile app."
    )

    source_dir = docs_dir / "source"

    print("  Reading RST source files...")
    for fname in RST_FILES:
        add_rst_section(pdf, source_dir, fname)

    pdf.write_to_file(output_pdf)
    print(f"Generated: {output_pdf} ({output_pdf.stat().st_size:,} bytes)")


# ---------------------------------------------------------------------------
# Post-build validation
# ---------------------------------------------------------------------------


def validate_pdf(filepath: Path) -> bool:
    """Basic sanity check - verifies the file is a non-empty valid PDF."""
    data = filepath.read_bytes()
    errors = []
    if not data.startswith(b"%PDF"):
        errors.append("does not start with %PDF header")
    if b"%%EOF" not in data:
        errors.append("missing %%EOF marker")
    if len(data) < 2000:
        errors.append(f"suspiciously small ({len(data)} bytes)")
    if errors:
        print(f"  WARNING {filepath.name}: {'; '.join(errors)}")
        return False
    print(f"  OK {filepath.name} ({len(data):,} bytes)")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    root_dir = Path(__file__).resolve().parent.parent
    docs_dir = root_dir / "docs"
    build_dir = docs_dir / "build"

    mis_docs_pdf = build_dir / "akvo-mis-docs.pdf"
    form_editor_pdf = build_dir / "akvo-react-form-editor-docs.pdf"

    build_platform_docs_pdf(docs_dir, mis_docs_pdf)
    build_form_editor_docs_pdf(form_editor_pdf)

    print("\nValidating generated PDFs...")
    ok1 = validate_pdf(mis_docs_pdf)
    ok2 = validate_pdf(form_editor_pdf)

    if ok1 and ok2:
        print("\nKnowledge Base PDFs are ready in docs/build/")
        print("Next step: ./kb.sh upload  (or  ./kb.sh sync)\n")
    else:
        print("\nOne or more PDFs failed validation. Check output above.\n")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
