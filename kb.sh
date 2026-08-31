#!/usr/bin/env bash
set -e

# Akvo MIS Knowledge Base Helper Script
# Usage:
#   ./kb.sh check                     - Audit KB coverage against upstream docs
#   ./kb.sh build                     - Build documentation PDFs
#   ./kb.sh upload                    - Upload PDFs to OpenAI Vector Store
#   ./kb.sh upload --create-assistant - Upload and create/link OpenAI Assistant
#   ./kb.sh upload --dry-run          - Validate files without calling OpenAI
#   ./kb.sh sync [--create-assistant] - Build PDFs and upload in one step

ACTION="${1:-help}"

run_in_docker() {
  local CMD="$1"
  if [ -f ".env" ]; then
    docker run --rm -v "$(pwd):/repo" -w /repo --env-file .env python:3.10-slim \
      bash -c "pip install -q --no-cache-dir \"openai>=1.30.0\" && python $CMD"
  else
    docker run --rm -v "$(pwd):/repo" -w /repo python:3.10-slim \
      bash -c "pip install -q --no-cache-dir \"openai>=1.30.0\" && python $CMD"
  fi
}

case "$ACTION" in
  check|coverage)
    shift || true
    echo "🔍 Auditing Knowledge Base Coverage..."
    python3 scripts/check_kb_coverage.py "$@"
    ;;

  build)
    echo "🔨 Building Knowledge Base PDFs..."
    run_in_docker "scripts/build_kb_pdf.py"
    ;;

  upload)
    shift || true
    echo "🚀 Uploading Knowledge Base to OpenAI..."
    run_in_docker "scripts/upload_kb.py $*"
    ;;

  sync|all)
    shift || true
    echo "🔨 [1/2] Building Knowledge Base PDFs..."
    run_in_docker "scripts/build_kb_pdf.py"
    echo "🚀 [2/2] Uploading to OpenAI Vector Store..."
    run_in_docker "scripts/upload_kb.py $*"
    ;;

  *)
    echo "Akvo MIS Knowledge Base Utility"
    echo ""
    echo "Usage:"
    echo "  ./kb.sh check                      Audit KB coverage against upstream docs"
    echo "  ./kb.sh check --verbose            Audit with matched file details"
    echo "  ./kb.sh check --format json        Emit coverage report as structured JSON"
    echo "  ./kb.sh build                      Build documentation PDFs into docs/build/"
    echo "  ./kb.sh upload                     Upload PDFs to OpenAI Vector Store"
    echo "  ./kb.sh upload --create-assistant  Upload PDFs and create/link Mira Assistant"
    echo "  ./kb.sh upload --dry-run           Validate PDFs without calling OpenAI"
    echo "  ./kb.sh sync [--create-assistant]  Build PDFs and upload in a single command"
    echo ""
    exit 0
    ;;
esac
