"""Snapshot data exports so a framework upgrade can be checked for drift.

Run once on the pre-upgrade stack to capture reference files, then after
each upgrade step with --compare to diff the new output cell by cell.
Exports carry the riskiest behaviour changes of the upgrade -- pandas 1
to 2, and Django 6.1's first()/last() ordering -- while the test suite
asserts little about their contents, so this compares the real files.

The download's context sheet is deliberately not written: it holds the
download timestamp, the only part of the output that is not a pure
function of the database.
"""
from pathlib import Path

import pandas as pd
from django.core.management import BaseCommand, CommandError
from openpyxl import load_workbook

from api.v1.v1_forms.models import Forms
from api.v1.v1_jobs.constants import DataDownloadTypes
from api.v1.v1_jobs.job import generate_data_sheet
from api.v1.v1_users.models import SystemUser
from utils.export_form import blank_data_template

# Enough to see the pattern of a drift without flooding the terminal.
MAX_DIFFS_SHOWN = 20


def snapshot(out_dir: Path) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    forms = Forms.objects.filter(parent__isnull=True).order_by("id")
    for form in forms:
        # Downloads are scoped to the requesting user's tenant, so act
        # as a user of the form's own tenant. A tenant without users has
        # nothing anyone could download.
        user = (
            SystemUser.objects.filter(tenant=form.tenant)
            .order_by("id")
            .first()
        )
        if user is None:
            continue
        data_path = out_dir / f"form-{form.id}-data.xlsx"
        with pd.ExcelWriter(data_path, engine="xlsxwriter") as writer:
            generate_data_sheet(
                writer=writer,
                form=form,
                download_type=DataDownloadTypes.all,
                use_label=True,
                user=user,
            )
        template_path = out_dir / f"form-{form.id}-template.xlsx"
        with pd.ExcelWriter(template_path, engine="xlsxwriter") as writer:
            blank_data_template(form=form, writer=writer)
        written += [data_path, template_path]
    return written


def diff_workbooks(reference: Path, candidate: Path) -> list:
    ref = load_workbook(reference, read_only=True)
    new = load_workbook(candidate, read_only=True)
    if ref.sheetnames != new.sheetnames:
        return [f"sheets {ref.sheetnames} != {new.sheetnames}"]
    diffs = []
    for name in ref.sheetnames:
        ref_rows = list(ref[name].iter_rows(values_only=True))
        new_rows = list(new[name].iter_rows(values_only=True))
        if len(ref_rows) != len(new_rows):
            diffs.append(
                f"{name}: {len(ref_rows)} rows != {len(new_rows)} rows"
            )
        for number, (a, b) in enumerate(zip(ref_rows, new_rows), start=1):
            if a != b:
                diffs.append(f"{name}!row {number}: {a} != {b}")
    return diffs


class Command(BaseCommand):
    help = "Write export snapshots, optionally comparing to a reference."

    def add_arguments(self, parser):
        parser.add_argument("out_dir", type=Path)
        parser.add_argument("--compare", type=Path, default=None)

    def handle(self, *args, **options):
        out_dir = options["out_dir"]
        written = {p.name: p for p in snapshot(out_dir)}
        self.stdout.write(f"Wrote {len(written)} files to {out_dir}")
        reference_dir = options["compare"]
        if reference_dir is None:
            return

        reference = {p.name: p for p in reference_dir.glob("*.xlsx")}
        problems = []
        for name in sorted(reference.keys() - written.keys()):
            problems.append(f"{name}: missing from new snapshot")
        for name in sorted(written.keys() - reference.keys()):
            problems.append(f"{name}: not in reference")
        for name in sorted(reference.keys() & written.keys()):
            diffs = diff_workbooks(reference[name], written[name])
            problems += [f"{name}: {d}" for d in diffs[:MAX_DIFFS_SHOWN]]
            if len(diffs) > MAX_DIFFS_SHOWN:
                hidden = len(diffs) - MAX_DIFFS_SHOWN
                problems.append(f"{name}: ... {hidden} more")

        for line in problems:
            self.stdout.write(line)
        if problems:
            raise CommandError(f"{len(problems)} export differences")
        self.stdout.write(self.style.SUCCESS("Exports match reference"))
