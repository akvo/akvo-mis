#!/usr/bin/env python3
"""
scripts/upload_kb.py

Uploads Akvo MIS Knowledge Base PDFs to OpenAI Vector Store.
Reuses existing Vector Store and Assistant if IDs or matching names are found.

Usage:
    OPENAI_API_KEY=sk-... python scripts/upload_kb.py

Options:
    --create-assistant       Create or update the OpenAI Assistant
    --vector-store-id ID     Specify an existing Vector Store ID
    --assistant-id ID        Specify an existing Assistant ID
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
ASSISTANT_NAME = "Mira - Akvo MIS Support"

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
    "6. SCOPE: You only answer questions about Akvo MIS and its features "
    "(forms, data collection, approvals, users, mobile app, reports, and "
    "related platform topics). If a question is clearly unrelated to "
    "Akvo MIS — for example about politics, geography, science, history, "
    "other software products, or general knowledge — politely decline and "
    "redirect: 'I can only help with Akvo MIS questions. Feel free to ask "
    "me about forms, data collection, approvals, or any other platform "
    "feature!'\n"
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


def get_or_create_assistant(
    client, vs_id: str, assistant_id: str = None
) -> str:
    """Retrieves/updates existing assistant or creates a new one."""
    if assistant_id:
        try:
            assistant = client.beta.assistants.retrieve(
                assistant_id=assistant_id
            )
            print(f"Found Assistant: {assistant.id} ({assistant.name})")
            # Update tool_resources to attach current vector store
            client.beta.assistants.update(
                assistant_id=assistant.id,
                instructions=ASSISTANT_INSTRUCTIONS,
                tools=[{"type": "file_search"}],
                tool_resources={"file_search": {"vector_store_ids": [vs_id]}},
            )
            print(f"Updated Assistant {assistant.id} with VS {vs_id}")
            return assistant.id
        except Exception as e:
            print(f"Warning: Could not retrieve Assistant {assistant_id}: {e}")

    # Search for an existing assistant by name
    print(f"Checking for existing Assistant named '{ASSISTANT_NAME}'...")
    try:
        assistants = client.beta.assistants.list(limit=50)
        for a in assistants.data:
            if a.name == ASSISTANT_NAME:
                print(f"Found existing Assistant by name: {a.id}")
                client.beta.assistants.update(
                    assistant_id=a.id,
                    instructions=ASSISTANT_INSTRUCTIONS,
                    tools=[{"type": "file_search"}],
                    tool_resources={
                        "file_search": {"vector_store_ids": [vs_id]}
                    },
                )
                print(f"Updated Assistant {a.id} with VS {vs_id}")
                return a.id
    except Exception as e:
        print(f"Warning: Could not list assistants: {e}")

    # If none found, create a new one
    print(f"Creating new OpenAI Assistant '{ASSISTANT_NAME}'...")
    try:
        assistant = client.beta.assistants.create(
            name=ASSISTANT_NAME,
            instructions=ASSISTANT_INSTRUCTIONS,
            model="gpt-4o-mini",
            tools=[{"type": "file_search"}],
            tool_resources={"file_search": {"vector_store_ids": [vs_id]}},
        )
        print(f"Assistant Created: {assistant.id}")
        return assistant.id
    except Exception as e:
        err_detail = ""
        if hasattr(e, "response") and hasattr(e.response, "json"):
            try:
                err_detail = f" | Details: {e.response.json()}"
            except Exception:
                pass
        print(
            f"Warning: Could not create Assistant automatically: {e}{err_detail}"  # noqa
        )
        return None


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

    # 3. Resolve Assistant
    asst_id = None
    if create_assistant or os.environ.get("OPENAI_ASSISTANT_ID"):
        asst_id_to_use = assistant_id or os.environ.get("OPENAI_ASSISTANT_ID")
        asst_id = get_or_create_assistant(client, vs_id, asst_id_to_use)

    print("\n" + "=" * 60)
    print("Knowledge Base Ingestion Complete!")
    print("=" * 60)
    print("Ensure the following are in your .env:\n")
    masked_key = (
        f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 12 else "sk-..."
    )
    print(f"OPENAI_API_KEY={masked_key}")
    print(f"OPENAI_VECTOR_STORE_ID={vs_id}")
    if asst_id:
        print(f"OPENAI_ASSISTANT_ID={asst_id}")
    else:
        print("# Tip: Run with --create-assistant to auto-link the assistant")
        print("OPENAI_ASSISTANT_ID=asst_...")
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
