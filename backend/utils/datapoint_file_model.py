"""A row published to devices as a JSON file, the way Draft models drafts.

Devices never read answers from the API: they list rows, then fetch
`{WEBDOMAIN}/<FILE_FOLDER>/<uuid>.json`. A row listed without its file is
one no device can download. `file_generated_at` records that the file was
written, `downloadable()` lists only rows whose file is current, and the
reconcile in v1_data repairs what slips through. See
doc/design/APP-517-datapoint-file-guarantee.md.

The model must have `uuid`, `created` and `updated`, and supplies the JSON
through `file_payload()`.
"""
import json
import logging
import os
from tempfile import TemporaryDirectory
from typing import Dict

from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from utils import storage

logger = logging.getLogger(__name__)

# Written, and no older than the row's last change.
FILE_CURRENT = Q(file_generated_at__gte=Coalesce(F("updated"), F("created")))


class DatapointFileQuerySetMixin:
    def downloadable(self):
        """Rows a device can fetch: the file is current, or none is owed."""
        return self.filter(self.model.FILE_EXEMPT | FILE_CURRENT)


class DatapointFileManagerMixin:
    # Managers do not proxy custom queryset methods; Draft delegates the
    # same way.
    def downloadable(self):
        return self.get_queryset().downloadable()


class DatapointFile(models.Model):
    FILE_FOLDER = "datapoints"
    # Rows that never get a file. Matches nothing unless the model says so;
    # keep it in step with `needs_file()`.
    FILE_EXEMPT = Q(pk__in=[])

    # When this row's file was last written. NULL = never; older than
    # `updated` = stale. Set by `write_file()` alone.
    file_generated_at = models.DateTimeField(null=True, default=None)

    class Meta:
        abstract = True

    def needs_file(self) -> bool:
        return True

    def file_payload(self) -> Dict:
        raise NotImplementedError

    def write_file(self) -> bool:
        """Write this row's file and stamp the row.

        Never raises: the row is already saved, and failing the caller over
        the file would lose nothing and fix nothing. A failure leaves the
        stamp as it was, so the row reads as owed and the reconcile retries.

        Returns:
            True when the file was written.
        """
        if not self.needs_file():
            return False
        # Captured before the payload is read: an edit that commits while
        # the file is being written then carries a later `updated` and reads
        # stale. Stamping after the write would call that file current.
        started = timezone.now()
        try:
            self._upload(self.file_payload())
        # ponytail: deliberately broad. Any failure here, a full disk or one
        # answer that will not serialise, means the same thing: owed.
        except Exception:
            logger.exception(
                "File write failed: %s id=%s uuid=%s",
                type(self).__name__, self.pk, self.uuid,
            )
            return False
        type(self)._base_manager.filter(pk=self.pk).update(
            file_generated_at=started
        )
        self.file_generated_at = started
        return True

    def _upload(self, payload: Dict) -> None:
        name = f"{self.uuid}.json"
        # A temporary folder, not the working directory: a failed upload
        # used to leave `<uuid>.json` behind in the app's root.
        with TemporaryDirectory() as tmp:
            path = os.path.join(tmp, name)
            with open(path, "w") as f:
                json.dump(payload, f)
            storage.upload(file=path, folder=self.FILE_FOLDER, filename=name)
