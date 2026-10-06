import logging
import os
from pathlib import Path
from typing import Dict, List

from django.utils import timezone
from django.db.models import Q
from api.v1.v1_data.models import FormData
from django.conf import settings
from api.v1.v1_visualization.functions import refresh_materialized_data
from utils import storage

logger = logging.getLogger(__name__)


def seed_approved_data(data: FormData):
    """
    Update FormData object from pending status to approved status
    """
    # No need to create new data, just update existing FormData
    data.updated = timezone.now()
    data.is_pending = False
    # Only the two fields this task owns. `data` is the copy pickled when the
    # task was queued, so a full save would write back a stale
    # `file_generated_at` over the stamp the request just set.
    data.save(update_fields=["updated", "is_pending"])

    # Rewritten after `updated` moved, or the stamp would read stale (APP-517)
    if not settings.TEST_ENV:
        data.write_file()
    # Refresh materialized view after saving data
    refresh_materialized_data()

    return data


# Reconcile datapoint files with the rows that own them (APP-517 D-4, D-7).
# Writing one file is the row's job (`DatapointFile.write_file()`); this is the
# batch job that repairs what slips through. It runs hourly on the worker,
# once at startup, and backs `generate_data_json`.

# More orphans than this share of the folder means the run is looking at the
# wrong database, not at deleted datapoints (D-7).
MAX_ORPHAN_SHARE = 0.5


def _folder() -> Path:
    # Read at call time, not import time, so a test can point it elsewhere.
    return Path(storage.STORAGE_PATH) / FormData.FILE_FOLDER


def _is_owed(row: Dict, on_disk: set) -> bool:
    stamp = row["file_generated_at"]
    if stamp is None or row["uuid"] not in on_disk:
        return True
    return stamp < (row["updated"] or row["created"])


def reconcile_datapoint_files(
    rewrite_all: bool = False, dry_run: bool = False, force: bool = False
) -> Dict[str, List[str]]:
    """Rewrite missing or stale files and delete orphaned ones.

    The folder is listed BEFORE the database is queried. A file written after
    the listing is not in it; one written before belongs to a row that had
    already committed, because files are written on commit. So no fresh file
    is ever mistaken for an orphan, with no grace period (D-7).

    Args:
        rewrite_all: rewrite every file, not only the owed ones.
        dry_run: report what would change, touch nothing.
        force: delete orphans even past the safety guard.

    Returns:
        UUIDs per outcome: rewritten, failed, deleted, refused.
    """
    folder = _folder()
    on_disk = (
        {p.stem for p in folder.glob("*.json")} if folder.is_dir() else set()
    )

    # `objects` drops soft-deleted rows but keeps drafts; drafts get no file.
    published = FormData.objects.filter(
        is_pending=False, is_draft=False, form__parent__isnull=True
    )
    rows = list(
        published.values(
            "pk", "uuid", "file_generated_at", "updated", "created"
        )
    )
    owed = [r for r in rows if rewrite_all or _is_owed(r, on_disk)]
    orphans = sorted(on_disk - {str(r["uuid"]) for r in rows})

    # No published rows at all is the extreme case: every file is an orphan.
    refuse = (
        len(orphans) > MAX_ORPHAN_SHARE * len(on_disk) and not force
    )
    result = {"rewritten": [], "failed": [], "deleted": [], "refused": []}
    if refuse:
        result["refused"] = orphans
    if dry_run:
        # Reports the guard's verdict too: a dry run is what someone reads
        # before deciding on --force.
        result["rewritten"] = [r["uuid"] for r in owed]
        if not refuse:
            result["deleted"] = orphans
        return result

    owed_ids = [r["pk"] for r in owed]
    for data in published.filter(pk__in=owed_ids).select_related("form"):
        key = "rewritten" if data.write_file() else "failed"
        result[key].append(data.uuid)

    if not orphans:
        return result
    if refuse:
        logger.error(
            "Refusing to delete %s of %s datapoint files: the database "
            "looks wrong. Run generate_data_json --force if intended.",
            len(orphans),
            len(on_disk),
        )
        return result
    for name in orphans:
        try:
            os.remove(folder / f"{name}.json")
        except FileNotFoundError:
            pass
        result["deleted"].append(name)
    # Any row still carrying one of these UUIDs (soft-deleted, a draft) must
    # not claim a file it no longer has, or `restore()` would bring it back
    # looking current.
    FormData._base_manager.filter(
        Q(uuid__in=orphans) & Q(file_generated_at__isnull=False)
    ).update(file_generated_at=None)
    return result
