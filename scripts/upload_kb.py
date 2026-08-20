#!/usr/bin/env python3
"""
scripts/upload_kb.py

Uploads Akvo MIS Knowledge Base PDFs to OpenAI Vector Store.

Usage:
    OPENAI_API_KEY=sk-... python scripts/upload_kb.py

Options:
    --create-assistant    Also create an OpenAI Assistant with the Vector Store
    --dry-run             Validate PDF paths without calling OpenAI
"""

import argparse
import os
import sys
from pathlib import Path

# Paths to documentation PDFs (in docs/build/)
PDF_FILES = [
    "docs/build/akvo-mis-docs.pdf",
    "docs/build/akvo-react-form-editor-docs.pdf",
]

ASSISTANT_INSTRUCTIONS = (
    "You are Mira, the intelligent support assistant for Akvo MIS.\n"
    "Your role is to help users navigate the platform, design forms, "
    "manage data, configure approvals, and understand features.\n\n"
    "Guidelines:\n"
    "1. Ground your answers directly in the attached documentation.\n"
    "2. If the user message includes a page context tag "
    "(e.g. [Context: User is on the 'Form Builder — Edit' page]), "
    "tailor your answer specifically to that page/feature context first.\n"
    "3. If the user asks about a different feature, answer accurately.\n"
    "4. Keep answers concise, step-by-step, actionable, and formatted.\n"
    "5. If docs do not cover a topic, politely inform the user.\n"
)


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def validate_pdfs(root_dir: Path) -> list:
    resolved_paths = []
    for rel_path in PDF_FILES:
        full_path = root_dir / rel_path
        if not full_path.exists():
            print(f"Error: Required PDF not found at {full_path}")
            print("Please run `python scripts/build_kb_pdf.py` first.")
            sys.exit(1)
        resolved_paths.append(full_path)
    return resolved_paths


def upload_kb(create_assistant: bool = False, dry_run: bool = False):
    root_dir = get_project_root()
    pdf_paths = validate_pdfs(root_dir)

    print(f"Found {len(pdf_paths)} Knowledge Base PDFs:")
    for p in pdf_paths:
        print(f"  - {p.relative_to(root_dir)} ({p.stat().st_size:,} bytes)")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key and not dry_run:
        print("\nError: OPENAI_API_KEY environment variable is not set.")
        print("Set it via: export OPENAI_API_KEY=sk-...")
        sys.exit(1)

    if dry_run:
        print("\n[Dry Run] PDFs validated. OpenAI API calls skipped.")
        return

    try:
        from openai import OpenAI
    except ImportError:
        print("\nError: 'openai' package is not installed.")
        print("Install it with: pip install openai>=1.30.0")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # 1. Create Vector Store
    print("\nCreating OpenAI Vector Store 'akvo-mis-kb'...")
    vector_store = client.vector_stores.create(name="akvo-mis-kb")
    vs_id = vector_store.id
    print(f"Vector Store Created: {vs_id}")

    # 2. Upload PDFs and poll for indexing completion
    print("Uploading and indexing documentation PDFs...")
    file_streams = [open(p, "rb") for p in pdf_paths]
    try:
        batch = client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vs_id,
            files=file_streams,
        )
        print(f"Ingestion status: {batch.status}")
        completed = batch.file_counts.completed
        failed = batch.file_counts.failed
        print(f"Files indexed: {completed} succeeded, {failed} failed")
    finally:
        for s in file_streams:
            s.close()

    # 3. Optionally create Assistant
    asst_id = None
    if create_assistant:
        print("\nCreating OpenAI Assistant 'Mira - Akvo MIS Support'...")
        assistant = client.beta.assistants.create(
            name="Mira - Akvo MIS Support",
            instructions=ASSISTANT_INSTRUCTIONS,
            model="gpt-4o-mini",
            tools=[{"type": "file_search"}],
            tool_resources={"file_search": {"vector_store_ids": [vs_id]}},
        )
        asst_id = assistant.id
        print(f"Assistant Created: {asst_id}")

    print("\n" + "=" * 60)
    print("Knowledge Base Ingestion Complete!")
    print("=" * 60)
    print("Add the following to your .env and deployment configs:\n")
    print(f"OPENAI_VECTOR_STORE_ID={vs_id}")
    if asst_id:
        print(f"OPENAI_ASSISTANT_ID={asst_id}")
    else:
        print("# Set OPENAI_ASSISTANT_ID once created in dashboard")
        print("OPENAI_ASSISTANT_ID=asst_...")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Upload Akvo MIS docs to OpenAI Vector Store"
    )
    parser.add_argument(
        "--create-assistant",
        action="store_true",
        help="Create and configure an OpenAI Assistant with the Vector Store",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate PDF files without making network calls",
    )
    args = parser.parse_args()
    upload_kb(create_assistant=args.create_assistant, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
