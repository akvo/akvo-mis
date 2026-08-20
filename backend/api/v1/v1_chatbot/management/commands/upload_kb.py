import os
import subprocess
import sys
from django.conf import settings
from django.core.management.base import BaseCommand
from pathlib import Path


class Command(BaseCommand):
    help = "Uploads Akvo MIS Knowledge Base PDFs to OpenAI Vector Store"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-assistant",
            action="store_true",
            help="Create and configure an OpenAI Assistant",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate PDF files without making network calls",
        )

    def handle(self, *args, **options):
        root_dir = Path(settings.BASE_DIR).parent
        script_path = root_dir / "scripts" / "upload_kb.py"

        if not script_path.exists():
            self.stderr.write(
                self.style.ERROR(f"Script not found at {script_path}")
            )
            return

        cmd = [sys.executable, str(script_path)]
        if options.get("create_assistant"):
            cmd.append("--create-assistant")
        if options.get("dry_run"):
            cmd.append("--dry-run")

        env = os.environ.copy()
        if hasattr(settings, "OPENAI_API_KEY") and settings.OPENAI_API_KEY:
            env["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

        self.stdout.write(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=env)
        if result.returncode != 0:
            self.stderr.write(self.style.ERROR("upload_kb failed."))
        else:
            self.stdout.write(
                self.style.SUCCESS("upload_kb executed successfully.")
            )
