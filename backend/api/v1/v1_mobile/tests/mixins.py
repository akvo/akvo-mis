from typing import Protocol

from django.db.models import F
from django.db.models.functions import Coalesce
from django.test import Client

from api.v1.v1_data.models import FormData
from utils.datapoint_file_model import FILE_CURRENT


class HasTestClientProtocol(Protocol):
    @property
    def client(self) -> Client:
        ...


class AssignmentTokenTestHelperMixin:

    def get_assignment_token(
        self: HasTestClientProtocol, passcode: str
    ) -> str:
        resp = self.client.post(
            '/api/v1/device/auth',
            {'code': passcode},
            content_type='application/json',
        )
        return resp.data.get('syncToken')


def mark_datapoint_files_written() -> None:
    """Give every row a file stamped at its own last change.

    The device listing hides rows whose file is missing or stale (APP-517
    D-2). Stamping at `updated or created` makes every file current while
    leaving the cursor and `last_updated` exactly what they were before the
    stamp existed, so listing assertions keep their meaning.
    """
    FormData._base_manager.exclude(FILE_CURRENT).update(
        file_generated_at=Coalesce(F("updated"), F("created"))
    )


class DatapointFilesWrittenMixin:
    """For suites that test the device listing, not the files behind it.

    Rows here are created through the ORM, so no file is ever written. Each
    GET first marks every file written; the file guarantee itself is covered
    by v1_data's tests_datapoint_files.
    """

    def _pre_setup(self):
        super()._pre_setup()
        get = self.client.get
        # For the test that needs a row whose file is still owed.
        self.get_without_files_written = get

        def get_with_files_written(*args, **kwargs):
            mark_datapoint_files_written()
            return get(*args, **kwargs)

        self.client.get = get_with_files_written
