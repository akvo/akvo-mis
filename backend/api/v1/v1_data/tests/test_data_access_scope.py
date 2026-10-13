from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.db.models import Q
from django.test import TestCase

from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from utils.data_access_scope import accessible_administration_q


class AccessibleAdministrationQTest(TestCase, ProfileTestHelperMixin):
    """Locks in the helper's contract. The data-listing views rely on these
    exact return shapes -- a superuser or a context-less caller must get an
    empty Q (no restriction), and only a real non-superuser is scoped -- so a
    change here would silently widen or empty out those views."""

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

    def test_none_user_is_unrestricted(self):
        # Internal/background callers pass user=None; tenant scoping is applied
        # separately, so this must not restrict by administration.
        self.assertEqual(accessible_administration_q(None), Q())

    def test_superuser_is_unrestricted(self):
        superuser = self.create_user("su@akvo.org", self.IS_SUPER_ADMIN)
        self.assertTrue(superuser.is_superuser)
        self.assertEqual(accessible_administration_q(superuser), Q())

    def test_anonymous_matches_nothing(self):
        self.assertEqual(
            accessible_administration_q(AnonymousUser()), Q(pk__in=[])
        )

    def test_non_superuser_with_role_is_scoped(self):
        adm = Administration.objects.filter(level__level=1).first()
        user = self.create_user(
            "prov@akvo.org", self.IS_ADMIN, administration=adm
        )
        scope = accessible_administration_q(user)
        # Restricted, but not the "match nothing" sentinel.
        self.assertNotEqual(scope, Q())
        self.assertNotEqual(scope, Q(pk__in=[]))
        self.assertTrue(scope.children)
