from django.core.management import call_command
from django.utils.timezone import make_aware
from datetime import datetime
from rest_framework_simplejwt.tokens import RefreshToken
from api.v1.v1_profile.models import Administration
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


class VisualizationValuesTestMixin(ProfileTestHelperMixin):
    """Shared test data setup for /visualization/values tests.

    Uses form seeder with example-vis-6 form definitions:
    - example-vis-6.json: Registration form (id=6001)
    - example-vis-6.monitoring.json: Monitoring form (id=6002)

    Creates test data:
    - 1 superuser
    - 2 administrations (parent-child)
    - 2 registration records (in different administrations)
    - 4 monitoring records (2 per parent, different dates)
    - Answers for: number, option, multiple_option, date,
      and repeatable number questions
    """

    # Form IDs from example-vis-6 seed files
    REGISTRATION_FORM_ID = 6001
    MONITORING_FORM_ID = 6002

    # Question IDs from example-vis-6.monitoring seed file
    Q_DATE_ID = 600201            # date: inspection_date
    Q_NUMBER_ID = 600202          # number: measurement_value
    Q_OPTION_ID = 600203          # option: operational_status
    Q_MULTI_ID = 600204           # multiple_option: features
    Q_TEXT_ID = 600205            # text: notes (unsupported type)
    Q_NUMBER_REPEAT_ID = 600206   # number: test_result (repeatable)

    # Registration question IDs
    Q_REG_OPTION_ID = 600102      # option: site_type
    Q_REG_ADMIN_ID = 600103       # administration: location
    Q_REG_GEO_ID = 600104         # geo: geolocation

    BASE_URL = "/api/v1/visualization/values"

    def setUp(self):
        super().setUp()
        self.maxDiff = None
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")

        # User
        self.user = self.create_user(
            email="viz_test@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )

        # Every endpoint in this app now requires authentication
        # (VIZ-003). Setting the credential once here keeps the 17 test
        # modules that use this mixin unchanged, so their assertions
        # remain the regression gate they were written to be.
        #
        # ProfileTestHelperMixin.get_auth_token() posts a dict body to
        # /api/v1/login with an explicit content_type. Every existing
        # caller of that helper is a plain TestCase, whose Django test
        # Client JSON-encodes a dict body when the content_type is
        # explicit. DRF's APIClient (used here, and required for
        # self.client.credentials()) does not: with an explicit
        # content_type it treats the body as already-encoded and just
        # stringifies the dict, so the login view receives invalid
        # JSON. Minting the token directly avoids that mismatch without
        # editing a helper shared by 60+ unrelated test modules.
        self.token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )

        # Load seeded forms
        self.registration = Forms.objects.get(
            pk=self.REGISTRATION_FORM_ID,
        )
        self.monitoring = Forms.objects.get(
            pk=self.MONITORING_FORM_ID,
        )

        # Load seeded questions
        self.q_date = Questions.objects.get(pk=self.Q_DATE_ID)
        self.q_number = Questions.objects.get(pk=self.Q_NUMBER_ID)
        self.q_option = Questions.objects.get(pk=self.Q_OPTION_ID)
        self.q_multi = Questions.objects.get(pk=self.Q_MULTI_ID)
        self.q_text = Questions.objects.get(pk=self.Q_TEXT_ID)
        self.q_number_repeat = Questions.objects.get(
            pk=self.Q_NUMBER_REPEAT_ID,
        )

        # Administrations: pick parent (level 0) and child (level 1)
        self.adm_parent = Administration.objects.filter(
            level__level=0,
        ).first()
        self.adm_child = Administration.objects.filter(
            level__level=1,
        ).first()

        # Load registration questions
        self.q_reg_option = Questions.objects.get(
            pk=self.Q_REG_OPTION_ID,
        )
        self.q_reg_admin = Questions.objects.get(
            pk=self.Q_REG_ADMIN_ID,
        )
        self.q_reg_geo = Questions.objects.get(
            pk=self.Q_REG_GEO_ID,
        )

        # Create registration records (2, different administrations)
        self.reg1 = FormData.objects.create(
            id=7200,
            name="Site Alpha",
            form=self.registration,
            administration=self.adm_parent,
            geo=[-18.1190718, 178.4504677],
            created_by=self.user,
        )
        # Registration answers for reg1
        Answers.objects.create(
            data=self.reg1,
            question=self.q_reg_admin,
            value=self.adm_parent.id,
            created_by=self.user,
        )
        Answers.objects.create(
            data=self.reg1,
            question=self.q_reg_geo,
            options=[-18.1190718, 178.4504677],
            created_by=self.user,
        )

        self.reg2 = FormData.objects.create(
            id=7201,
            name="Site Beta",
            form=self.registration,
            administration=self.adm_child,
            geo=[-18.1175162, 178.4478261],
            created_by=self.user,
        )
        # Registration answers for reg2
        Answers.objects.create(
            data=self.reg2,
            question=self.q_reg_admin,
            value=self.adm_child.id,
            created_by=self.user,
        )
        Answers.objects.create(
            data=self.reg2,
            question=self.q_reg_geo,
            options=[-18.1175162, 178.4478261],
            created_by=self.user,
        )

        # Create monitoring records with answers
        # reg1: 2 monitoring records (Jan + Mar)
        self.mon1a = self._create_monitoring(
            parent=self.reg1,
            created_date=datetime(2025, 1, 15),
            number_val=10.0,
            number_repeat_vals=[5.0, 15.0],
            option_val="active",
            multi_vals=["feature_x", "feature_y"],
            date_val="2025-01-15T00:00:00.000Z",
        )
        self.mon1b = self._create_monitoring(
            parent=self.reg1,
            created_date=datetime(2025, 3, 10),
            number_val=20.0,
            number_repeat_vals=[8.0, 12.0, 4.0],
            option_val="active",
            multi_vals=["feature_y", "feature_z"],
            date_val="2025-03-10T00:00:00.000Z",
        )

        # reg2: 2 monitoring records (Jan + Mar)
        self.mon2a = self._create_monitoring(
            parent=self.reg2,
            created_date=datetime(2025, 1, 20),
            number_val=30.0,
            number_repeat_vals=[10.0, 20.0],
            option_val="inactive",
            multi_vals=["feature_x", "feature_z"],
            date_val="2025-01-20T00:00:00.000Z",
        )
        self.mon2b = self._create_monitoring(
            parent=self.reg2,
            created_date=datetime(2025, 3, 15),
            number_val=40.0,
            number_repeat_vals=[25.0, 35.0],
            option_val="pending",
            multi_vals=["feature_x", "feature_y", "feature_z"],
            date_val="2025-03-15T00:00:00.000Z",
        )

    def _create_monitoring(
        self,
        parent,
        created_date,
        number_val=None,
        number_repeat_vals=None,
        option_val=None,
        multi_vals=None,
        date_val=None,
    ):
        """Create a monitoring FormData with answers.

        Args:
            parent: Parent registration FormData.
            created_date: datetime for FormData.created.
            number_val: Value for measurement_value question.
            number_repeat_vals: List of values for repeatable
                test_result question.
            option_val: Option value for operational_status.
            multi_vals: List of option values for features.
            date_val: ISO date string for inspection_date.

        Returns:
            Created FormData instance.
        """
        mon = FormData.objects.create(
            name=f"{parent.name} - Monitoring",
            form=self.monitoring,
            parent=parent,
            administration=parent.administration,
            created_by=self.user,
        )
        # Set created date (bypass auto_now_add)
        FormData.objects.filter(id=mon.id).update(
            created=make_aware(created_date),
        )
        mon.refresh_from_db()

        if number_val is not None:
            Answers.objects.create(
                data=mon,
                question=self.q_number,
                value=number_val,
                created_by=self.user,
                index=0,
            )

        if number_repeat_vals:
            for idx, val in enumerate(number_repeat_vals):
                Answers.objects.create(
                    data=mon,
                    question=self.q_number_repeat,
                    value=val,
                    created_by=self.user,
                    index=idx,
                )

        if option_val:
            Answers.objects.create(
                data=mon,
                question=self.q_option,
                options=[option_val],
                created_by=self.user,
                index=0,
            )

        if multi_vals:
            Answers.objects.create(
                data=mon,
                question=self.q_multi,
                options=multi_vals,
                created_by=self.user,
                index=0,
            )

        if date_val:
            Answers.objects.create(
                data=mon,
                question=self.q_date,
                name=date_val,
                created_by=self.user,
                index=0,
            )

        return mon
