#!/usr/bin/env python3
"""
scripts/upload_kb.py

Uploads Akvo MIS Knowledge Base PDFs to OpenAI Vector Store.
Reuses an existing Vector Store if an ID or a matching name is found.

Usage:
    OPENAI_API_KEY=sk-... python scripts/upload_kb.py

Options:
    --create-assistant       Ignored (the Assistants API was shut down)
    --vector-store-id ID     Specify an existing Vector Store ID
    --assistant-id ID        Ignored (see above)
    --dry-run                Validate PDF paths without calling OpenAI
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

VECTOR_STORE_NAME = "akvo-mis-kb"


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


def get_or_create_vector_store(client, vector_store_id: str = None) -> str:
    """Retrieves existing vector store or creates a new one."""
    if vector_store_id:
        try:
            vs = client.vector_stores.retrieve(vector_store_id=vector_store_id)
            print(f"Using existing Vector Store: {vs.id} ({vs.name})")
            return vs.id
        except Exception as e:
            print(f"Warning: Could not retrieve VS {vector_store_id}: {e}")

    # Search for an existing vector store by name
    print(f"Checking for existing Vector Store named '{VECTOR_STORE_NAME}'...")
    try:
        stores = client.vector_stores.list(limit=50)
        for s in stores.data:
            if s.name == VECTOR_STORE_NAME:
                print(f"Found existing Vector Store by name: {s.id}")
                return s.id
    except Exception as e:
        print(f"Warning: Could not list vector stores: {e}")

    # If none found, create a new one
    print(f"Creating new OpenAI Vector Store '{VECTOR_STORE_NAME}'...")
    vector_store = client.vector_stores.create(name=VECTOR_STORE_NAME)
    print(f"Vector Store Created: {vector_store.id}")
    return vector_store.id


def upload_kb(
    create_assistant: bool = False,
    vector_store_id: str = None,
    assistant_id: str = None,
    dry_run: bool = False,
):
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

    # 1. Resolve Vector Store (reuse existing if available)
    vs_id_to_use = vector_store_id or os.environ.get("OPENAI_VECTOR_STORE_ID")
    vs_id = get_or_create_vector_store(client, vs_id_to_use)

    # 2. Upload PDFs and poll for indexing completion
    print("\nUploading and indexing documentation PDFs into Vector Store...")
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

    # 3. The Assistants API was shut down on 2026-08-26. The chatbot
    #    queries the vector store directly, so there is no assistant.
    if create_assistant or assistant_id:
        print(
            "\nNote: --create-assistant and --assistant-id are ignored. "
            "The chatbot uses the vector store through the Responses "
            "API, so no assistant is needed."
        )

    print("\n" + "=" * 60)
    print("Knowledge Base Ingestion Complete!")
    print("=" * 60)
    print("Ensure the following are in your .env:\n")
    masked_key = (
        f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 12 else "sk-..."
    )
    print(f"OPENAI_API_KEY={masked_key}")
    print(f"OPENAI_VECTOR_STORE_ID={vs_id}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Upload Akvo MIS docs to OpenAI Vector Store"
    )
    parser.add_argument(
        "--create-assistant",
        action="store_true",
        help="Create or update the OpenAI Assistant with the Vector Store",
    )
    parser.add_argument(
        "--vector-store-id",
        type=str,
        default=None,
        help="Specify an existing Vector Store ID",
    )
    parser.add_argument(
        "--assistant-id",
        type=str,
        default=None,
        help="Specify an existing Assistant ID",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate PDF files without making network calls",
    )
    args = parser.parse_args()
    upload_kb(
        create_assistant=args.create_assistant,
        vector_store_id=args.vector_store_id,
        assistant_id=args.assistant_id,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
