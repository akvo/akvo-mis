from concurrent.futures import ThreadPoolExecutor

from django.core.management import call_command
from django.db import close_old_connections
from django.test import TransactionTestCase
from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_data.serializers import SubmitPendingFormSerializer
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionKeyConcurrencyTest(
    TransactionTestCase, ProfileTestHelperMixin
):
    """Two retries racing from one device must still store one row.

    The application-level lookup in SubmitPendingFormSerializer.create() can
    be passed by both racers -- neither sees the other's uncommitted INSERT.
    Only the unique index stops the second one, and the `except IntegrityError`
    clause is what turns that into a successful no-op.

    This cannot use django.test.TestCase: threads need committed rows and
    their own connections, and TestCase wraps every test in a transaction
    that the threads would never see.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.form = Forms.objects.get(pk=1)
        self.administration = Administration.objects.filter(
            parent__isnull=True
        ).first()
        self.user = self.create_user(
            email="concurrency@test.com",
            role_level=self.IS_SUPER_ADMIN,
            administration=self.administration,
        )

    def submit(self, submission_key):
        try:
            serializer = SubmitPendingFormSerializer(
                data={
                    "data": {
                        "name": "racing submission",
                        "administration": self.administration.id,
                        "submission_key": submission_key,
                    },
                    "answer": [{"question": 101, "value": "Jane"}],
                },
                context={"user": self.user, "form": self.form},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return None
        except Exception as error:  # noqa: BLE001 - the assertion is below
            return error
        finally:
            close_old_connections()

    def test_concurrent_replay_stores_one_row(self):
        key = "cccccccc-cccc-cccc-cccc-cccccccccccc"

        with ThreadPoolExecutor(max_workers=2) as pool:
            errors = list(pool.map(self.submit, [key, key]))

        # Neither caller sees an error: the loser adopts the winner's row.
        self.assertEqual([e for e in errors if e is not None], [])
        self.assertEqual(
            FormData._base_manager.filter(submission_key=key).count(), 1
        )
