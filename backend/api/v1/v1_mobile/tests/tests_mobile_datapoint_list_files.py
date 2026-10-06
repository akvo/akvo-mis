"""APP-517: the device listing trusts `file_generated_at`, nothing else."""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin

PLOT = [[9.03, 38.74], [9.04, 38.74], [9.04, 38.75], [9.03, 38.75]]


@override_settings(USE_TZ=False, TEST_ENV=True)
class DatapointListFileGuaranteeTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.administration = Administration.objects.filter(
            parent__isnull=True
        ).first()
        self.child = self.administration.parent_administration.first()
        self.user = self.create_user(
            email="enumerator@test.org",
            role_level=self.IS_ADMIN,
            administration=self.administration,
        )
        self.form = self.make_form("Plot Form")
        self.monitoring = self.make_form("Visit", parent=self.form)
        self.assignment = MobileAssignment.objects.create_assignment(
            user=self.user, name="device", passcode="passcode1234"
        )
        self.assignment.administrations.add(self.child)
        self.assignment.forms.add(self.form, self.monitoring)
        auth = self.client.post(
            "/api/v1/device/auth",
            {"code": "passcode1234"},
            content_type="application/json",
        )
        self.token = auth.data["syncToken"]

    def make_form(self, name, parent=None):
        form = Forms.objects.create(name=name, version=1, parent=parent)
        group = QuestionGroup.objects.create(form=form, name="G", order=1)
        form.plot_question = Questions.objects.create(
            form=form, question_group=group, name="plot", label="Plot",
            order=1, type=QuestionTypes.geoshape,
            extra={"geoConfig": {"detectOverlaps": True}},
        )
        self.user.user_form.create(form=form)
        return form

    def make_datapoint(self, name, form=None, **fields):
        form = form or self.form
        data = FormData.objects.create(
            name=name, form=form, administration=self.child,
            created_by=self.user, uuid=f"uuid-{name}", **fields,
        )
        Answers.objects.create(
            data=data, question=form.plot_question, options=PLOT,
            created_by=self.user,
        )
        return data

    def stamp(self, data, at):
        FormData.objects.filter(pk=data.pk).update(file_generated_at=at)

    def listed(self, query=""):
        response = self.client.get(
            f"/api/v1/device/datapoint-list/{query}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def names(self, body):
        return sorted(row["name"] for row in body["data"])

    def test_a_row_is_listed_only_once_its_file_is_written(self):
        data = self.make_datapoint("a")
        self.assertEqual(self.names(self.listed()), [])
        self.stamp(data, timezone.now())
        self.assertEqual(self.names(self.listed()), ["a"])

    def test_a_stale_file_hides_the_row_until_it_is_rewritten(self):
        data = self.make_datapoint("a")
        written = timezone.now()
        self.stamp(data, written)
        FormData.objects.filter(pk=data.pk).update(
            updated=written + timedelta(seconds=1)
        )
        self.assertEqual(self.names(self.listed()), [])
        self.stamp(data, written + timedelta(seconds=2))
        self.assertEqual(self.names(self.listed()), ["a"])

    def test_a_monitoring_row_needs_no_file(self):
        self.make_datapoint("visit", form=self.monitoring)
        self.assertEqual(self.names(self.listed()), ["visit"])

    def test_geometry_total_still_counts_a_plot_whose_file_is_owed(self):
        """D-3: dropped from the count, the device would match its total
        against a set missing this plot and pass an overlap check."""
        written = self.make_datapoint("written")
        self.stamp(written, timezone.now())
        self.make_datapoint("owed")
        body = self.listed(f"?form_id={self.form.id}")
        self.assertEqual(self.names(body), ["written"])
        self.assertEqual(body["geometry_total"], 2)

    def test_a_rewritten_file_reaches_a_device_that_already_synced(self):
        """D-5: the row did not change, only its file did."""
        data = self.make_datapoint("a")
        first = timezone.now()
        self.stamp(data, first)
        FormData.objects.filter(pk=data.pk).update(
            created=first - timedelta(days=1)
        )
        self.assignment.last_synced_at = first + timedelta(seconds=1)
        self.assignment.save()
        self.assertEqual(self.names(self.listed()), [])

        rewritten = first + timedelta(seconds=2)
        self.stamp(data, rewritten)
        body = self.listed()
        self.assertEqual(self.names(body), ["a"])
        # Otherwise the device's skip-unchanged check keeps its old copy.
        self.assertEqual(
            body["data"][0]["last_updated"], rewritten.isoformat()
        )
