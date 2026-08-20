#!/usr/bin/env python3
"""
scripts/build_kb_pdf.py

Builds knowledge base PDFs for OpenAI Vector Store ingestion:
1. docs/build/akvo-mis-docs.pdf - Platform documentation from docs/source/*.rst
2. docs/build/akvo-react-form-editor-docs.pdf - Form builder & runtime guide

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
            self.pages.append(self.current_page_lines)
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

    def finalize(self):
        if self.current_page_lines:
            self.pages.append(self.current_page_lines)
            self.current_page_lines = []

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
        num_pages = max(1, len(self.pages))
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
            b"/BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n"  # noqa
        )

        # Pages & content
        for idx in range(num_pages):
            p_obj_id = page_obj_ids[idx]
            c_obj_id = content_obj_ids[idx]
            lines = self.pages[idx] if idx < len(self.pages) else [""]

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


def clean_rst_text(content: str) -> str:
    """Strips RST directives and formatting for clean doc text."""
    content = re.sub(r"\.\.\s+image::[^\n]*", "", content)
    content = re.sub(r"\.\.\s+figure::[^\n]*", "", content)
    content = re.sub(r"^\s+:[a-zA-Z_-]+:.*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"\.\.\s+toctree::[\s\S]*?(?=\n\n|\Z)", "", content)
    content = re.sub(r":[a-zA-Z_-]+:`([^`]+)`", r"\1", content)
    content = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
    content = re.sub(r"\*([^*]+)\*", r"\1", content)
    content = re.sub(r"\.\.\s+code-block::[^\n]*", "", content)
    content = re.sub(r"::[\s]*\n", "\n", content)
    return content.strip()


def build_platform_docs_pdf(docs_dir: Path, output_pdf: Path):
    """Parses docs/source/*.rst and generates akvo-mis-docs.pdf."""
    print(f"Building {output_pdf} from RST docs...")
    pdf = SimplePDFWriter(title="Akvo MIS - Platform Documentation")
    pdf.add_heading("Akvo MIS Platform Documentation", level=1)
    pdf.add_paragraph(
        "Comprehensive user and administrator guide for Akvo MIS. "
        "Covers Form Builder, Data Management, Approvals, Admin, Mobile."
    )

    source_dir = docs_dir / "source"
    rst_files = [
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

    for fname in rst_files:
        fpath = source_dir / fname
        if not fpath.exists():
            continue

        raw = fpath.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_rst_text(raw)
        section_title = fname.replace(".rst", "").replace("_", " ")
        pdf.add_heading(section_title, level=2)

        for paragraph in cleaned.split("\n\n"):
            p = paragraph.strip()
            if p:
                pdf.add_paragraph(p)

    pdf.write_to_file(output_pdf)
    print(f"Generated: {output_pdf} ({output_pdf.stat().st_size} bytes)")


def build_form_editor_docs_pdf(output_pdf: Path):
    """Generates the supplementary akvo-react-form-editor-docs.pdf."""
    print(f"Building supplementary {output_pdf}...")
    pdf = SimplePDFWriter(title="Akvo MIS - Form Builder & Runtime Guide")

    pdf.add_heading("Akvo Form Builder & Runtime Reference Guide", level=1)
    pdf.add_paragraph(
        "Technical specification for Akvo Form Builder, editor layout, "
        "tabs, question groups, skip logic, and validation."
    )

    pdf.add_heading("1. Editor Layout and Workspace Tabs", level=2)
    pdf.add_paragraph(
        "The Form Builder editor (/control-center/form-builder/:id/edit) "
        "provides 4 tabs: Edit Form, Translations, Preview, and JSON schema."
    )

    pdf.add_heading("2. Question Groups and Repeatable Sections", level=2)
    pdf.add_paragraph(
        "Question Groups act as logical containers for questions. "
        "Repeatable Groups enable '+ Add Another' dynamic entry in runtime."
    )

    pdf.add_heading(
        "3. Question Configuration and Validation Settings", level=2
    )
    pdf.add_paragraph(
        "Settings include Label, Variable Name, Tooltip, Required flag, "
        "Double Entry validation, Min/Max Bounds, Prefix and Suffix."
    )

    pdf.add_heading("4. Skip Logic and Cascading Dependencies", level=2)
    pdf.add_paragraph(
        "Skip logic shows/hides questions based on conditions. "
        "Cascade questions bind to root administration endpoints."
    )

    pdf.add_heading("5. Comprehensive Question Types (16 Types)", level=2)
    types_info = [
        ("Input / Text", "Single-line and multi-line text entries."),
        ("Number", "Integer or float values with min/max bound validation."),
        ("Date", "Calendar date picker with range constraints."),
        ("Option", "Radio button or dropdown choice selecting one option."),
        (
            "Multiple Option",
            "Checkboxes allowing selection of multiple choices.",
        ),
        ("Cascade", "Hierarchical multi-level cascading dropdowns."),
        ("Tree", "Nested tree selector for hierarchical taxonomy."),
        ("Table", "Tabular matrix for structured inputs."),
        ("Autofield", "Formula-driven computed fields using math operators."),
        ("Geo / Geopoint", "GPS location capture for lat/long/elevation."),
        ("Geotrace / Geoshape", "Line string and polygon boundary capture."),
        ("Entity", "Selects or links an existing registered entity."),
        ("Signature", "Digital signature pad verification."),
        ("Attachment", "Image capture and document uploads with validation."),
    ]
    for qtype, desc in types_info:
        pdf.add_paragraph(f"- {qtype}: {desc}")

    pdf.add_heading("6. Form Lifecycle, Publishing, and Permissions", level=2)
    pdf.add_paragraph(
        "Registration Forms create new entities. Monitoring Forms track "
        "ongoing indicators via parent_id. Publishing creates immutable snapshots."  # noqa
    )

    pdf.write_to_file(output_pdf)
    print(f"Generated: {output_pdf} ({output_pdf.stat().st_size} bytes)")


def main():
    root_dir = Path(__file__).resolve().parent.parent
    docs_dir = root_dir / "docs"
    build_dir = docs_dir / "build"

    mis_docs_pdf = build_dir / "akvo-mis-docs.pdf"
    form_editor_pdf = build_dir / "akvo-react-form-editor-docs.pdf"

    build_platform_docs_pdf(docs_dir, mis_docs_pdf)
    build_form_editor_docs_pdf(form_editor_pdf)

    print("\nKnowledge Base PDFs ready for upload in docs/build/!")


if __name__ == "__main__":
    main()
