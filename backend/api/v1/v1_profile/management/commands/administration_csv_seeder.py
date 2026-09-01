"""Bootstrap a workspace hierarchy from a CSV (SEED-002).

Unlike `administration_seeder`, this command targets one workspace and
builds both the Levels and the Administration rows from a file the
operator authored by hand. See
doc/design/SEED-002-administration-csv-seeder.md.
"""
import csv
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.v1.v1_jobs.administrations_bulk_upload import seed_administrations
from api.v1.v1_profile.models import Administration, Levels
from utils.tenant_command import resolve_tenant

# `{level}_{Alias}` — level FIRST, so an alias containing an underscore or
# ending in a digit still parses. The suffix form used by the topojson
# seeder splits on the last underscore and silently misreads those.
LEVEL_HEADER = re.compile(r"^(\d+)_(.+)$")

CODE_ALIAS = "code"


def parse_headers(columns):
    """Map depth -> (name_column, alias, code_column_or_None).

    Columns that do not match `^\\d+_` are ignored rather than rejected, so
    a file carrying attribute columns still imports its hierarchy (R-2).
    """
    levels, codes = {}, {}
    for col in columns:
        matched = LEVEL_HEADER.match((col or "").strip())
        if not matched:
            continue
        depth = int(matched.group(1))
        alias = matched.group(2).strip()
        if alias.lower() == CODE_ALIAS:
            codes[depth] = col
            continue
        if depth in levels:
            raise CommandError(
                f"Two name columns for level {depth}: "
                f"'{levels[depth][0]}' and '{col}'. Each tier needs "
                f"exactly one name column."
            )
        levels[depth] = (col, alias)
    if not levels:
        raise CommandError(
            "No level columns found. Headers must look like "
            "'0_National,0_Code,1_Province,1_Code'."
        )
    # A level literally named "Code" has a name column spelled exactly like
    # its own code column, so it is claimed by `codes` above and the tier
    # goes missing. The contiguity check below is what reports it.
    expected = list(range(len(levels)))
    if sorted(levels) != expected:
        raise CommandError(
            f"Levels must be contiguous from 0. Found {sorted(levels)}, "
            f"expected {expected}."
        )
    return {
        depth: (col, alias, codes.get(depth))
        for depth, (col, alias) in levels.items()
    }


def resolve_source(source):
    """Storage-relative first, literal path second.

    Storage is the intended home: country files are operator data, are
    often large, and must not be committed — backend/storage/.gitignore
    ignores its own contents. The literal fallback keeps
    `--source ./tmp/scratch.csv` working while iterating.
    """
    # settings.STORAGE_PATH, not storage.check(): utils/storage binds
    # STORAGE_PATH at import time, so it ignores override_settings and the
    # two would disagree under test.
    in_storage = os.path.join(settings.STORAGE_PATH, source)
    if os.path.isfile(in_storage):
        return in_storage
    if os.path.isfile(source):
        return source
    raise CommandError(
        f"'{source}' not found in storage ({settings.STORAGE_PATH}/) "
        f"or as a file path. Copy the CSV into "
        f"{settings.STORAGE_PATH}/administrations/ and pass "
        f"'administrations/{os.path.basename(source)}'."
    )


def read_rows(path):
    """Header list plus row dicts, with every cell stripped.

    csv rather than pandas: empty cells stay empty strings instead of
    becoming NaN, which is the whole reason the Excel path is littered
    with pd.isnull() checks.
    """
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = [
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
        ]
    if not rows:
        raise CommandError(f"'{path}' has a header but no rows.")
    return columns, rows


def validate_rows(header_map, rows):
    """Reject a path that skips a tier, naming the row and column.

    A blank cell truncates the row there, which is legal; a blank cell
    with a non-blank descendant is a hole in the path and is not.
    """
    depths = sorted(header_map)
    for index, row in enumerate(rows, start=2):
        truncated_at = None
        for depth in depths:
            column = header_map[depth][0]
            value = row.get(column, "")
            if not value:
                if truncated_at is None:
                    truncated_at = depth
                continue
            if truncated_at is not None:
                raise CommandError(
                    f"Row {index}, column "
                    f"'{header_map[truncated_at][0]}': blank name with a "
                    f"non-blank descendant '{column}'. A path cannot skip "
                    f"a tier."
                )
        if truncated_at == depths[0]:
            raise CommandError(
                f"Row {index}, column '{header_map[depths[0]][0]}': "
                f"level 0 may not be blank."
            )


def reconcile_root(header_map, rows, tenant, rename_root):
    """Make the file's level-0 value agree with the workspace root.

    A tenant has exactly one root (unique_root_administration_per_tenant),
    so a mismatch is an IntegrityError at the end of a long import unless
    it is caught here. A mismatch is far more likely to be the wrong file
    than a deliberate rename, and the root's name appears in every
    full_name / administration_column string.
    """
    depths = sorted(header_map)
    root_column = header_map[depths[0]][0]
    csv_roots = {row[root_column] for row in rows if row.get(root_column)}
    if len(csv_roots) > 1:
        raise CommandError(
            f"Column '{root_column}' has more than one value "
            f"({', '.join(sorted(csv_roots))}). A workspace has exactly "
            f"one root."
        )
    csv_root = csv_roots.pop()
    root = Administration.objects.filter(
        tenant=tenant, parent__isnull=True
    ).first()
    if not root:
        return csv_root, None
    if root.name.lower() == csv_root.lower():
        return csv_root, None
    if not rename_root:
        raise CommandError(
            f"Workspace root is '{root.name}' but the file's level-0 "
            f"column says '{csv_root}'. Pass --rename-root to rename it, "
            f"or check you are importing the right file."
        )
    previous = root.name
    root.name = csv_root
    root.save(update_fields=["name"])
    return csv_root, f"   root renamed '{previous}' -> '{root.name}'"


def build_row_data(header_map, row, levels):
    """The [(Levels, name, code), ...] tuple list seed_administrations wants.

    Ordered root-first and truncated at the first blank tier, which is
    what makes `parent=last_obj` walk the path correctly.
    """
    data = []
    for depth in sorted(header_map):
        name_column, _alias, code_column = header_map[depth]
        name = row.get(name_column, "")
        if not name:
            break
        code = row.get(code_column, "") if code_column else ""
        data.append((levels[depth], name, code or None))
    return data


class Command(BaseCommand):
    help = "Import an administration hierarchy for one workspace from CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "-s", "--source", type=str, required=True,
            help=(
                "CSV path. Resolved against STORAGE_PATH first, then as a "
                "literal file path."
            ),
        )
        parser.add_argument(
            "-t", "--tenant", type=str, required=True,
            help=(
                "Workspace subdomain to import into. 'default' exists on "
                "any migrated database."
            ),
        )
        parser.add_argument(
            "--rename-root",
            action="store_true",
            help=(
                "Allow the level-0 column to rename the workspace's "
                "existing root unit."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report; write nothing.",
        )

    def handle(self, *args, **options):
        path = resolve_source(options["source"])
        tenant = resolve_tenant(options["tenant"], required=True)
        dry_run = options["dry_run"]

        self.stdout.write(f"-- Validating {path}")
        columns, rows = read_rows(path)
        header_map = parse_headers(columns)
        validate_rows(header_map, rows)

        detected = ", ".join(
            f"{depth} {header_map[depth][1]}"
            for depth in sorted(header_map)
        )
        self.stdout.write(f"   Levels detected: {detected}")
        self.stdout.write(f"   Rows: {len(rows)}")

        with transaction.atomic():
            levels_before = Levels.objects.filter(tenant=tenant).count()
            admins_before = Administration.objects.filter(
                tenant=tenant
            ).count()

            levels, notes = self._ensure_levels(header_map, tenant)
            _root, rename_note = reconcile_root(
                header_map, rows, tenant, options["rename_root"]
            )
            if rename_note:
                notes.append(rename_note)

            for row in rows:
                row_data = build_row_data(header_map, row, levels)
                if row_data:
                    seed_administrations(row_data, tenant=tenant)

            levels_created = (
                Levels.objects.filter(tenant=tenant).count() - levels_before
            )
            admins_created = (
                Administration.objects.filter(tenant=tenant).count()
                - admins_before
            )
            self.stdout.write(
                f"-- Levels:          {levels_created} created, "
                f"{len(header_map) - levels_created} reused"
            )
            for note in notes:
                self.stdout.write(note)
            self.stdout.write(
                f"-- Administrations: {admins_created} created"
            )
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.WARNING("-- Dry run: rolled back")
                )
                return
        self.stdout.write(self.style.SUCCESS("-- Done"))

    def _ensure_levels(self, header_map, tenant):
        """ensure_levels, with the divergence notes split out."""
        levels, notes = {}, []
        for depth, (_col, alias, _code) in sorted(header_map.items()):
            level, created = Levels.objects.get_or_create(
                tenant=tenant, level=depth, defaults={"name": alias},
            )
            levels[depth] = level
            if not created and level.name != alias:
                notes.append(
                    f"   level {depth} exists as '{level.name}'; file "
                    f"says '{alias}' (kept '{level.name}')"
                )
        return levels, notes
