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
# Dynamic Markdown Knowledge Base Compiler
# ---------------------------------------------------------------------------


def add_markdown_file(pdf: SimplePDFWriter, file_path: Path):
    """Parses a Markdown file and appends content to SimplePDFWriter."""
    if not file_path.exists():
        return

    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    in_code_block = False
    current_paragraph = []

    def flush_paragraph():
        if current_paragraph:
            combined = " ".join(current_paragraph).strip()
            if combined:
                pdf.add_paragraph(combined)
            current_paragraph.clear()

    for line in lines:
        stripped = line.strip()

        # Code block fences
        if stripped.startswith("```"):
            flush_paragraph()
            in_code_block = not in_code_block
            continue

        if in_code_block:
            pdf.add_line(line[:78])
            continue

        if not stripped:
            flush_paragraph()
            continue

        # Horizontal rules
        if re.match(r"^---+$", stripped) or re.match(r"^===+$", stripped):
            flush_paragraph()
            continue

        # Headings
        if stripped.startswith("#"):
            flush_paragraph()
            if stripped.startswith("###"):
                level = 3
                heading_text = stripped.lstrip("#").strip()
            elif stripped.startswith("##"):
                level = 2
                heading_text = stripped.lstrip("#").strip()
            else:
                level = 1
                heading_text = stripped.lstrip("#").strip()
            pdf.add_heading(heading_text, level=level)
            continue

        # Bullet points and numbered items
        bullet_match = re.match(r"^(\s*)([-*]|\d+\.)\s+(.+)$", line)
        if bullet_match:
            flush_paragraph()
            indent_spaces = len(bullet_match.group(1))
            indent_level = min(2, indent_spaces // 2)
            bullet_text = bullet_match.group(3).strip()
            pdf.add_bullet(bullet_text, indent=indent_level)
            continue

        # Markdown tables
        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            # Skip separator rows like |---|---|
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            row_str = " | ".join(cells)
            pdf.add_bullet(row_str, indent=0)
            continue

        # Regular prose line -> accumulate in current paragraph
        current_paragraph.append(stripped)

    flush_paragraph()


def build_form_editor_docs_pdf(output_pdf: Path, kb_dir: Path = None):
    """Generates akvo-react-form-editor-docs.pdf from docs/knowledge_base/."""
    print(f"Building supplementary {output_pdf}...")
    pdf = SimplePDFWriter(title="Akvo MIS - Form Builder & Knowledge Base")

    pdf.add_heading("Akvo Form Builder & System Knowledge Base", level=1)
    pdf.add_paragraph(
        "Comprehensive technical reference, form design recipes, property "
        "catalogs, calculation formulas, and platform capability guides "
        "for Akvo MIS."
    )

    if kb_dir and kb_dir.exists():
        md_files = sorted(kb_dir.rglob("*.md"))
        print(
            f"  Compiling {len(md_files)} knowledge base modules from "
            f"{kb_dir}..."
        )
        for md_file in md_files:
            print(f"    + {md_file.relative_to(kb_dir.parent)}")
            add_markdown_file(pdf, md_file)
    else:
        print("  [warning] No docs/knowledge_base directory found.")

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
        "Comprehensive user and administrator guide for Akvo MIS - a "
        "Real-Time Monitoring Information System. Covers form design, "
        "data collection, approvals, administration, and mobile app."
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

    kb_dir = docs_dir / "knowledge_base"
    mis_docs_pdf = build_dir / "akvo-mis-docs.pdf"
    form_editor_pdf = build_dir / "akvo-react-form-editor-docs.pdf"

    build_platform_docs_pdf(docs_dir, mis_docs_pdf)
    build_form_editor_docs_pdf(form_editor_pdf, kb_dir=kb_dir)

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
