from datetime import datetime

from django.core.management import call_command
from django.utils.timezone import make_aware
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import FormStatus, FormTypes, QuestionTypes
from api.v1.v1_forms.models import (
    Forms,
    QuestionGroup,
    QuestionOptions,
    Questions,
)
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin

# ── Option values used across the global filter tests ──

# "What is the water source?"
GROUND = "ground_water"
SURFACE = "surface_water"
RAIN = "rainwater"

# "Were you able to take a water sample?" (and the other yes/no questions)
YES = "yes"
NO = "no"

# "Is the infrastructure operational?" - the filter question of the sketch
OPERATIONAL = "operational"
BROKEN = "non_operational"

# "What is the weather during the check?"
FINE = "fine"
RAINY = "rainy"


class GlobalFilterTestMixin(ProfileTestHelperMixin):
    """VIZ-027 §10 fixture: ten water points, three forms, one family.

    Forms (sketch name in brackets):

      Water point registration [FR]   registers each water point (site)
      Water quality visit      [A]    monitoring form of the registration
      Quick status check       [B]    monitoring form of the registration
      School registration      [OTHER] a different family, never allowed

    Questions:

      Water point registration
        Q_SOURCE      "What is the water source?" [FR-Q1]
                      Ground water | Surface water | Rainwater
      Water quality visit
        Q_SAMPLE      "Were you able to take a water sample?" [MA-Q1]
                      Yes | No
        Q_HOUSEHOLDS  "How many households use this water point?" (number)
        Q_VISIT_DATE  "Date of visit" (date)
        Q_SOURCE_SEEN "What is the water source?" - same `name` as
                      Q_SOURCE, re-asked during the visit (D-8)
      Quick status check
        Q_STATUS      "Is the infrastructure operational?" [B-Q]
                      Operational | Non-operational
        Q_WEATHER     "What is the weather during the check?" [MB-Q2]
                      Fine | Rainy
      School registration
        Q_TOILET      "Does the school have a toilet?" Yes | No

    The data. All dates are 2025. Water points are registered on 01-01,
    except site 8 (2024-12-01). OK = Operational, BROKEN = Non-operational.

      site  water source   visit: sample taken?  check: infrastructure
      1, 2  Ground water   Yes 02-15             OK 03-10
      3     Ground water   Yes 02-15             BROKEN 01-10, OK 03-10
      4     Ground water   Yes 02-15, No 02-20   OK 01-10, BROKEN 03-10
      5     Ground water   Yes 02-15             BROKEN 01-20 (only check)
      6     Ground water   Yes 02-15             BROKEN 03-10 (only check)
      7     Surface water  Yes 02-15             OK 03-10
      8, 9  Rainwater      Yes 02-15             OK 03-10
      10    (no answer)    never visited         never checked

    Every check reports the weather as Fine. Every visit records
    Q_HOUSEHOLDS = the site number and Q_VISIT_DATE = the visit date.

    So, filtering out "Non-operational" (the sketch) removes the water
    points whose LATEST check says Non-operational: sites 4, 5 and 6.
    Site 3 stays (broken in January, fixed in March). Site 10 stays (never
    checked, so nothing says it is broken).
    """

    REG_ID = 7001
    VISIT_ID = 7002
    CHECK_ID = 7003
    SCHOOL_ID = 7101

    Q_SOURCE = 700101
    Q_SAMPLE = 700201
    Q_HOUSEHOLDS = 700202
    Q_VISIT_DATE = 700203
    Q_SOURCE_SEEN = 700204
    Q_STATUS = 700301
    Q_WEATHER = 700302
    Q_TOILET = 710101

    VALUES_URL = "/api/v1/visualization/values"

    def setUp(self):
        super().setUp()
        self.maxDiff = None
        call_command("administration_seeder", "--test")
        self.user = self.create_user(
            email="viz_global_filter@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.adm = Administration.objects.filter(level__level=0).first()

        self.registration = self._form(
            self.REG_ID, "Water point registration", FormTypes.registration,
        )
        self.visit_form = self._form(
            self.VISIT_ID, "Water quality visit", FormTypes.monitoring,
            parent=self.registration,
        )
        self.check_form = self._form(
            self.CHECK_ID, "Quick status check", FormTypes.monitoring,
            parent=self.registration,
        )
        self.school = self._form(
            self.SCHOOL_ID, "School registration", FormTypes.registration,
        )

        self._question(
            self.registration, self.Q_SOURCE, "water_source",
            "What is the water source?",
            [(GROUND, "Ground water"), (SURFACE, "Surface water"),
             (RAIN, "Rainwater")],
        )
        self._question(
            self.visit_form, self.Q_SAMPLE, "sample_taken",
            "Were you able to take a water sample?",
            [(YES, "Yes"), (NO, "No")],
        )
        self._question(
            self.visit_form, self.Q_HOUSEHOLDS, "households",
            "How many households use this water point?",
            type_=QuestionTypes.number,
        )
        self._question(
            self.visit_form, self.Q_VISIT_DATE, "visit_date",
            "Date of visit", type_=QuestionTypes.date,
        )
        self._question(
            self.visit_form, self.Q_SOURCE_SEEN, "water_source",
            "What is the water source?",
            [(GROUND, "Ground water"), (SURFACE, "Surface water"),
             (RAIN, "Rainwater")],
        )
        self._question(
            self.check_form, self.Q_STATUS, "infrastructure_status",
            "Is the infrastructure operational?",
            [(OPERATIONAL, "Operational"), (BROKEN, "Non-operational")],
        )
        self._question(
            self.check_form, self.Q_WEATHER, "weather",
            "What is the weather during the check?",
            [(FINE, "Fine"), (RAINY, "Rainy")],
        )
        self._question(
            self.school, self.Q_TOILET, "has_toilet",
            "Does the school have a toilet?",
            [(YES, "Yes"), (NO, "No")],
        )

        water_source = {
            1: GROUND, 2: GROUND, 3: GROUND, 4: GROUND, 5: GROUND,
            6: GROUND, 7: SURFACE, 8: RAIN, 9: RAIN,
        }
        self.site = {}
        for n in range(1, 11):
            registered = (
                datetime(2024, 12, 1) if n == 8 else datetime(2025, 1, 1)
            )
            self.site[n] = self._register(n, registered, water_source.get(n))

        for n in range(1, 10):
            self._visit(n, datetime(2025, 2, 15), sample_taken=YES)
        self._visit(4, datetime(2025, 2, 20), sample_taken=NO)

        march = datetime(2025, 3, 10)
        for n in (1, 2, 7, 8, 9):
            self._check(n, march, [OPERATIONAL])
        self._check(3, datetime(2025, 1, 10), [BROKEN])
        self._check(3, march, [OPERATIONAL])
        self._check(4, datetime(2025, 1, 10), [OPERATIONAL])
        self._check(4, march, [BROKEN])
        self._check(5, datetime(2025, 1, 20), [BROKEN])
        self._check(6, march, [BROKEN])

    # ── builders ──

    def _form(self, pk, name, form_type, parent=None):
        return Forms.objects.create(
            id=pk,
            name=name,
            type=form_type,
            parent=parent,
            status=FormStatus.published,
        )

    def _question(self, form, pk, name, label, options=(), type_=None):
        group, _ = QuestionGroup.objects.get_or_create(
            form=form, name=f"group_{form.pk}", defaults={"order": 1},
        )
        question = Questions.objects.create(
            id=pk,
            form=form,
            question_group=group,
            order=pk % 100,
            label=label,
            name=name,
            type=type_ or QuestionTypes.option,
        )
        for order, (value, option_label) in enumerate(options, start=1):
            QuestionOptions.objects.create(
                question=question,
                order=order,
                value=value,
                label=option_label,
            )
        return question

    def _stamp(self, data, created):
        FormData.objects.filter(pk=data.pk).update(created=make_aware(created))
        data.refresh_from_db()
        return data

    def _register(self, n, registered, water_source):
        """Register water point `Site n`."""
        site = FormData.objects.create(
            name=f"Site {n}",
            form=self.registration,
            administration=self.adm,
            geo=[-18.0 - n / 100, 178.0 + n / 100],
            created_by=self.user,
        )
        if water_source:
            self._answer(site, self.Q_SOURCE, options=[water_source])
        return self._stamp(site, registered)

    def _visit(self, n, visited, sample_taken):
        """A water quality visit to `Site n`."""
        visit = FormData.objects.create(
            name=f"Site {n} - visit",
            form=self.visit_form,
            parent=self.site[n],
            administration=self.adm,
            created_by=self.user,
        )
        self._answer(visit, self.Q_SAMPLE, options=[sample_taken])
        self._answer(visit, self.Q_HOUSEHOLDS, value=n)
        self._answer(
            visit, self.Q_VISIT_DATE,
            name=visited.strftime("%Y-%m-%dT00:00:00.000Z"),
        )
        return self._stamp(visit, visited)

    def _check(self, n, checked, statuses, weather=FINE):
        """A quick status check of `Site n`.

        `statuses` holds one infrastructure status per repeat (index), so
        a check that inspected two pumps passes two values (D-9).
        `weather=None` leaves the weather question unanswered.
        """
        check = FormData.objects.create(
            name=f"Site {n} - check",
            form=self.check_form,
            parent=self.site[n],
            administration=self.adm,
            created_by=self.user,
        )
        for index, status in enumerate(statuses):
            self._answer(check, self.Q_STATUS, options=[status], index=index)
        if weather:
            self._answer(check, self.Q_WEATHER, options=[weather])
        return self._stamp(check, checked)

    def _answer(self, data, question_id, index=0, **fields):
        return Answers.objects.create(
            data=data,
            question_id=question_id,
            created_by=self.user,
            index=index,
            **fields,
        )

    # ── request helpers ──

    @staticmethod
    def filter_out(question_id, *values):
        """`global_criteria` occurrences that filter these answers out.

        One `option_not_in:<qid>:<value>` per value (D-15); the test
        client repeats the query key for a list. Combine two filters by
        adding their lists.
        """
        return [f"option_not_in:{question_id}:{value}" for value in values]

    def values(self, **params):
        return self.client.get(self.VALUES_URL, params)

    def site_numbers(self, names):
        """'Site 3' / 'Site 3 - visit' -> 3, for every name given."""
        return {int(name.split(" ")[1]) for name in names}

    def sites_on_visit_form(self, **params):
        """Water points a "Water quality visit" chart draws (latest visit)."""
        response = self.values(
            form_id=self.VISIT_ID, group_by="parent_id", **params,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return self.site_numbers(response.json()["labels"])

    def sites_on_registration(self, **params):
        """Water points a "Water point registration" chart draws."""
        response = self.values(form_id=self.REG_ID, group_by="id", **params)
        self.assertEqual(response.status_code, 200, response.content)
        return self.site_numbers(response.json()["labels"])

    def by_option(self, response):
        """{option value: count} of an option chart."""
        self.assertEqual(response.status_code, 200, response.content)
        return {
            row["group"]: row["value"] for row in response.json()["data"]
        }
