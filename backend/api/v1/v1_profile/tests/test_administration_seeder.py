from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.management.commands import administration_seeder
from api.v1.v1_profile.models import Levels, Administration


@override_settings(USE_TZ=False, TEST_ENV=True)
class AdministrationSeederTestCase(TestCase):
    def test_administration_seeder_test(self):
        administration_seeder.seed_administration_test()
        administrator_level = (
            Administration.objects.order_by("-level")
            .values_list("level", flat=True)
            .distinct()
        )
        level_ids = Levels.objects.order_by("-id").values_list("id", flat=True)
        self.assertEqual(list(administrator_level), list(level_ids))
        national = Administration.objects.filter(level__level=0).first()
        response = self.client.get(
            f"/api/v1/administration/{national.pk}", follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            list(response.json()),
            [
                "id",
                "level",
                "level_name",
                "name",
                "parent",
                "children",
                "children_level_name",
                "full_name",
                "path"
            ]
        )

        # Test max_level
        response = self.client.get(
            f"/api/v1/administration/{national.pk}?max_level=0", follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], national.pk)
        self.assertEqual(len(response.json()["children"]), 0)

        # tests filter
        first_child = Administration.objects.filter(parent=national).first()
        response = self.client.get(
            f"/api/v1/administration/{national.pk}?filter={first_child.pk}",
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["children"]), 1)
