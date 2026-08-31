#!/usr/bin/env python3
"""
scripts/check_kb_coverage.py

Standalone audit script that verifies the Markdown knowledge base under
docs/knowledge_base/ has documented every prop, question type, and named
config option appearing in upstream source-of-truth documentation
(akvo-react-form, akvo-react-form-editor, and optionally akvo-mis RST docs).

PURPOSE & SCOPE:
- Extracts all documented tables and props from upstream READMEs and RST docs.
- Searches docs/knowledge_base/**/*.md recursively for matching terminology.
- Reports covered items vs. actionable gaps.
- Exits with code 0 if all items are covered, or code 1 if any gaps exist.

NOTE ON COVERAGE:
This script audits terminology presence across the knowledge base. A match
indicates the term appears in the KB; it verifies surface presence and
coverage, not subjective semantic documentation quality.

USAGE EXAMPLES:
  # Default audit against local packages and docs/knowledge_base:
  ./scripts/check_kb_coverage.py

  # Emit structured JSON report for CI/tooling:
  ./scripts/check_kb_coverage.py --format json > coverage.json

  # Audit with external repo paths and verbose matching details:
  ./scripts/check_kb_coverage.py --react-form-path ../akvo-react-form --verbose
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class InventoryItem:
    source_repo: str
    source_table: str
    item_name: str
    raw_text: str
    source_file: str
    line_number: int


@dataclass
class TableCoverage:
    source_repo: str
    source_table: str
    total_items: int
    covered_items: int
    missing_items: List[str] = field(default_factory=list)
    covered_details: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class AuditReport:
    total_inventoried: int
    total_covered: int
    total_missing: int
    coverage_percentage: float
    tables: List[TableCoverage] = field(default_factory=list)
    missing_by_table: Dict[str, List[str]] = field(default_factory=dict)


def clean_markdown_cell(cell: str) -> str:
    """Normalize markdown cell: strip links, bold, code, whitespace."""
    # Convert markdown links [Label](url) -> Label
    cell = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cell)
    # Strip bold **text** or __text__
    cell = re.sub(r"\*\*([^*]+)\*\*", r"\1", cell)
    cell = re.sub(r"__([^_]+)__", r"\1", cell)
    # Strip italics *text* (avoiding identifier underscores)
    cell = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", cell)
    # Strip backticks `code`
    cell = re.sub(r"`([^`]+)`", r"\1", cell)
    # Strip surrounding whitespace
    return cell.strip()


def parse_markdown_tables(
    file_path: Path, source_name: str
) -> List[InventoryItem]:
    """Parse pipe-delimited markdown tables from a README file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Source file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    items: List[InventoryItem] = []
    current_heading = "General"
    current_table_lines: List[Tuple[int, str]] = []

    def flush_table(heading: str, table_lines: List[Tuple[int, str]]):
        if len(table_lines) < 3:
            return
        # Verify separator row
        sep_line = table_lines[1][1]
        if not re.search(r"\|?\s*[-:]+\s*\|", sep_line):
            return

        header_line = table_lines[0][1]
        header_cells = [
            clean_markdown_cell(c) for c in header_line.split("|")[1:-1]
        ]

        for line_no, row_str in table_lines[2:]:
            cells = [c.strip() for c in row_str.split("|")[1:-1]]
            if not cells:
                continue

            cleaned_cells = [clean_markdown_cell(c) for c in cells]

            # Special handling for "Supported Question Type" tables
            is_type_table = (
                "Supported Question Type" in heading
                or "Supported Field Type" in heading
            )
            if is_type_table:
                has_value_col = (
                    len(cleaned_cells) >= 2
                    and header_cells
                    and header_cells[0].lower() == "type"
                    and header_cells[1].lower() == "value"
                )
                if has_value_col:
                    val_name = cleaned_cells[1]
                    if val_name:
                        items.append(
                            InventoryItem(
                                source_repo=source_name,
                                source_table=heading,
                                item_name=val_name,
                                raw_text=cells[1],
                                source_file=str(file_path),
                                line_number=line_no,
                            )
                        )
                else:
                    item_name = cleaned_cells[0]
                    if item_name:
                        items.append(
                            InventoryItem(
                                source_repo=source_name,
                                source_table=heading,
                                item_name=item_name,
                                raw_text=cells[0],
                                source_file=str(file_path),
                                line_number=line_no,
                            )
                        )
            else:
                item_name = cleaned_cells[0]
                if item_name:
                    # Normalize dynamic property names like Unique{any}
                    clean_name = re.sub(
                        r"^Unique\{.*\}$", "Unique{any}", item_name
                    )
                    items.append(
                        InventoryItem(
                            source_repo=source_name,
                            source_table=heading,
                            item_name=clean_name,
                            raw_text=cells[0],
                            source_file=str(file_path),
                            line_number=line_no,
                        )
                    )

    for idx, line in enumerate(lines):
        line_num = idx + 1
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            if current_table_lines:
                flush_table(current_heading, current_table_lines)
                current_table_lines = []
            current_heading = heading_match.group(2).strip()
            continue

        if line.strip().startswith("|"):
            current_table_lines.append((line_num, line.strip()))
        else:
            if current_table_lines:
                flush_table(current_heading, current_table_lines)
                current_table_lines = []

    if current_table_lines:
        flush_table(current_heading, current_table_lines)

    return items


def parse_rst_headings(
    rst_dir: Path, source_name: str = "akvo-mis (RST)"
) -> List[InventoryItem]:
    """Extract headings and subheadings from platform RST documentation."""
    if not rst_dir.exists():
        return []

    items: List[InventoryItem] = []
    adornment_chars = {"=", "-", "~", "^", '"'}

    for rst_file in sorted(rst_dir.glob("*.rst")):
        lines = rst_file.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            line_str = line.strip()
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if (
                    next_line
                    and len(next_line) >= 3
                    and len(set(next_line)) == 1
                    and set(next_line).issubset(adornment_chars)
                    and line_str
                    and not line_str.startswith("..")
                ):
                    items.append(
                        InventoryItem(
                            source_repo=source_name,
                            source_table=rst_file.name,
                            item_name=line_str,
                            raw_text=line_str,
                            source_file=str(rst_file),
                            line_number=i + 1,
                        )
                    )
    return items


def load_kb_documents(kb_dir: Path) -> Dict[str, str]:
    """Load all markdown documents under docs/knowledge_base/."""
    if not kb_dir.exists():
        raise FileNotFoundError(
            f"Knowledge base directory not found: {kb_dir}"
        )

    docs: Dict[str, str] = {}
    for md_file in kb_dir.rglob("*.md"):
        docs[md_file.name] = md_file.read_text(encoding="utf-8")
    return docs


def audit_coverage(
    inventory: List[InventoryItem], kb_docs: Dict[str, str]
) -> AuditReport:
    """Audit all inventory items against loaded KB documents."""
    table_groups: Dict[Tuple[str, str], List[InventoryItem]] = {}
    for item in inventory:
        key = (item.source_repo, item.source_table)
        table_groups.setdefault(key, []).append(item)

    table_reports: List[TableCoverage] = []
    total_inventoried = len(inventory)
    total_covered = 0
    total_missing = 0
    missing_by_table: Dict[str, List[str]] = {}

    for (repo, table_name), items in table_groups.items():
        covered_count = 0
        missing_list: List[str] = []
        covered_details: Dict[str, List[str]] = {}

        for item in items:
            name = item.item_name
            # Search pattern: boundary match or backtick match
            escaped = re.escape(name)
            pattern = re.compile(rf"(?:\b|`){escaped}(?:\b|`)", re.IGNORECASE)

            matches = [
                doc_name
                for doc_name, content in kb_docs.items()
                if pattern.search(content)
            ]

            if matches:
                covered_count += 1
                covered_details[name] = matches
            else:
                missing_list.append(name)

        total_covered += covered_count
        total_missing += len(missing_list)

        table_key = f"[{repo}] {table_name}"
        if missing_list:
            missing_by_table[table_key] = missing_list

        table_reports.append(
            TableCoverage(
                source_repo=repo,
                source_table=table_name,
                total_items=len(items),
                covered_items=covered_count,
                missing_items=missing_list,
                covered_details=covered_details,
            )
        )

    pct = (
        (total_covered / total_inventoried * 100.0)
        if total_inventoried > 0
        else 100.0
    )

    return AuditReport(
        total_inventoried=total_inventoried,
        total_covered=total_covered,
        total_missing=total_missing,
        coverage_percentage=round(pct, 2),
        tables=table_reports,
        missing_by_table=missing_by_table,
    )


def resolve_path(
    arg_path: Optional[str], default_candidates: List[Path]
) -> Optional[Path]:
    """Resolve file or directory path from CLI argument or defaults."""
    if arg_path:
        p = Path(arg_path)
        if p.is_dir():
            readme = p / "README.md"
            if readme.exists():
                return readme
        return p

    for cand in default_candidates:
        if cand.exists():
            return cand
    return None


def print_human_report(report: AuditReport, verbose: bool = False):
    """Format and print a clean human-readable audit report."""
    print("=" * 80)
    print("AKVO MIS KNOWLEDGE BASE COVERAGE AUDIT REPORT")
    print("=" * 80)

    for table in report.tables:
        status_symbol = "✓" if not table.missing_items else "✗"
        pct = (
            (table.covered_items / table.total_items * 100.0)
            if table.total_items > 0
            else 100.0
        )
        print(f"\n{status_symbol} [{table.source_repo}] {table.source_table}")
        print(
            f"  Coverage: {table.covered_items}/{table.total_items} items "
            f"({pct:.1f}%)"
        )

        if table.missing_items:
            print("  Gaps (Actionable):")
            for gap in table.missing_items:
                print(f"    - {gap}")

        if verbose and table.covered_details:
            print("  Covered Items Detail:")
            for item_name, doc_matches in table.covered_details.items():
                print(f"    + {item_name} -> {', '.join(doc_matches)}")

    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)
    print(f"Total Inventoried Items: {report.total_inventoried}")
    print(f"Total Covered in KB:     {report.total_covered}")
    print(f"Total Missing Gaps:      {report.total_missing}")
    print(f"Overall Coverage:        {report.coverage_percentage:.2f}%")

    if report.total_missing == 0:
        print(
            "\n✨ STATUS: PASSED - 100% of inventoried surfaces are covered!"
        )
    else:
        print(
            f"\n⚠️ STATUS: FAILED - Found {report.total_missing} undocumented "
            f"item(s)."
        )
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Audit knowledge base coverage against documentation."
    )
    parser.add_argument(
        "--react-form-path",
        help="Path to akvo-react-form README.md or repo directory",
        default=None,
    )
    parser.add_argument(
        "--react-form-editor-path",
        help="Path to akvo-react-form-editor README.md or repo directory",
        default=None,
    )
    parser.add_argument(
        "--rst-path",
        help="Path to akvo-mis docs/source directory containing RST docs",
        default="docs/source",
    )
    parser.add_argument(
        "--kb-path",
        help="Path to docs/knowledge_base directory",
        default="docs/knowledge_base",
    )
    parser.add_argument(
        "--include-rst",
        action="store_true",
        help="Include platform RST headings in coverage audit",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (text or json)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show matched KB files for each covered item",
    )

    args = parser.parse_args()

    repo_root = Path.cwd()

    arf_path = resolve_path(
        args.react_form_path,
        [
            repo_root
            / "frontend"
            / "node_modules"
            / "akvo-react-form"
            / "README.md",
            repo_root / ".." / "akvo-react-form" / "README.md",
        ],
    )

    arfe_path = resolve_path(
        args.react_form_editor_path,
        [
            repo_root
            / "frontend"
            / "node_modules"
            / "akvo-react-form-editor"
            / "README.md",
            repo_root / ".." / "akvo-react-form-editor" / "README.md",
        ],
    )

    kb_path = repo_root / args.kb_path
    rst_path = repo_root / args.rst_path

    if not arf_path or not arf_path.exists():
        print(
            "Error: Could not locate akvo-react-form README. "
            "Specify via --react-form-path.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not arfe_path or not arfe_path.exists():
        print(
            "Error: Could not locate akvo-react-form-editor README. "
            "Specify via --react-form-editor-path.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not kb_path.exists():
        print(
            f"Error: Knowledge base directory '{kb_path}' does not exist.",
            file=sys.stderr,
        )
        sys.exit(2)

    # 1. Parse inventories
    inventory: List[InventoryItem] = []
    inventory.extend(parse_markdown_tables(arf_path, "akvo-react-form"))
    inventory.extend(
        parse_markdown_tables(arfe_path, "akvo-react-form-editor")
    )

    if args.include_rst and rst_path.exists():
        inventory.extend(parse_rst_headings(rst_path, "akvo-mis (RST)"))

    # 2. Load KB markdown files
    kb_docs = load_kb_documents(kb_path)

    # 3. Perform coverage audit
    report = audit_coverage(inventory, kb_docs)

    # 4. Output results
    if args.format == "json":
        print(json.dumps(asdict(report), indent=2))
    else:
        print_human_report(report, verbose=args.verbose)

    # 5. Exit code: 0 if passed (no missing items), 1 if gaps found
    sys.exit(0 if report.total_missing == 0 else 1)


if __name__ == "__main__":
    main()
