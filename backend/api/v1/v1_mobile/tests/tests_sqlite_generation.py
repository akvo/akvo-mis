import os
import sqlite3
import pandas as pd
from api.v1.v1_profile.tests.utils import AdministrationEntitiesTestFactory
from mis.settings import MASTER_DATA
from django.test import TestCase, override_settings
from api.v1.v1_profile.models import Administration, Entity, EntityData
from api.v1.v1_profile.management.commands.administration_seeder import (
    seed_levels
)
from api.v1.v1_profile.constants import DEFAULT_ADMINISTRATION_LEVELS
from api.v1.v1_users.models import Organisation, SystemUser
from api.v1.v1_mobile.authentication import MobileAssignmentToken
from api.v1.v1_mobile.models import MobileAssignment
from django.core.management import call_command
from utils.custom_generator import generate_sqlite, update_sqlite
from unittest.mock import patch


@override_settings(USE_TZ=False, TEST_ENV=True)
class SQLiteGenerationTest(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("organisation_seeder", "--test")
        self.administration = Administration.objects.all()
        self.organization = Organisation.objects.all()

    def test_generate_sqlite(self):
        # Test for Organisation
        file_name = generate_sqlite(Organisation)
        self.assertTrue(os.path.exists(file_name))
        conn = sqlite3.connect(file_name)
        self.assertEqual(
            len(self.organization),
            len(pd.read_sql_query("SELECT * FROM nodes", conn)),
        )
        conn.close()
        os.remove(file_name)

        # Test for Administration
        file_name = generate_sqlite(Administration)
        self.assertTrue(os.path.exists(file_name))
        conn = sqlite3.connect(file_name)
        self.assertEqual(
            len(self.administration),
            len(pd.read_sql_query("SELECT * FROM nodes", conn)),
        )
        conn.close()
        os.remove(file_name)

    def test_sqlite_generation_command(self):
        call_command("generate_sqlite", "--test", True)
        output_1 = f"{MASTER_DATA}/test_administrator.sqlite"
        output_2 = f"{MASTER_DATA}/test_organisation.sqlite"
        self.assertTrue(os.path.exists(output_1))
        self.assertTrue(os.path.exists(output_2))
        os.remove(output_1)
        os.remove(output_2)

    def test_sqlite_file_endpoint(self):
        file_name = generate_sqlite(Administration)
        self.assertTrue(os.path.exists(file_name))
        conn = sqlite3.connect(file_name)
        self.assertEqual(
            len(self.administration),
            len(pd.read_sql_query("SELECT * FROM nodes", conn)),
        )
        conn.close()
        # The device asks for the logical table name, not the on-disk one:
        # the server picks the file, which is how it stays inside the
        # caller's tenant. This user is tenant-less, so it gets the root
        # file the assertions above just checked.
        user = SystemUser.objects.create_user(
            email="device@test.org", password="Secret#Pass123",
            first_name="D", last_name="D",
        )
        assignment = MobileAssignment.objects.create_assignment(
            user=user, name="device"
        )
        token = MobileAssignmentToken.for_assignment(assignment)
        response = self.client.get(
            "/api/v1/device/sqlite/administrator.sqlite",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        os.remove(file_name)

    def test_sqlite_file_endpoint_rejects_an_anonymous_caller(self):
        generate_sqlite(Administration)
        response = self.client.get(
            "/api/v1/device/sqlite/administrator.sqlite"
        )
        self.assertEqual(response.status_code, 401)

    def test_update_sqlite_org_added(self):
        # Test for adding new org
        file_name = generate_sqlite(Organisation)
        self.assertTrue(os.path.exists(file_name))

        org = Organisation.objects.create(name="SQLite Company")
        update_sqlite(
            model=Organisation,
            data={"id": org.id, "name": org.name},
            id=None,
        )
        conn = sqlite3.connect(file_name)
        self.assertEqual(
            1,
            len(
                pd.read_sql_query(
                    "SELECT * FROM nodes where id = ?", conn, params=[org.id]
                )
            ),
        )
        conn.close()
        os.remove(file_name)

    def test_update_sqlite_org_updated(self):
        # Test for adding new org
        file_name = generate_sqlite(Organisation)
        self.assertTrue(os.path.exists(file_name))

        new_org_name = "Edited Company"
        org = Organisation.objects.last()
        org.name = new_org_name
        org.save()
        update_sqlite(
            model=Organisation,
            data={"name": new_org_name},
            id=org.id,
        )

        conn = sqlite3.connect(file_name)
        self.assertEqual(
            1,
            len(
                pd.read_sql_query(
                    "SELECT * FROM nodes where name = ?",
                    conn,
                    params=[new_org_name],
                )
            ),
        )
        conn.close()
        os.remove(file_name)

    def test_update_sqlite_with_no_nodes_table(self):
        # Test for adding new org
        file_name = generate_sqlite(Organisation)
        self.assertTrue(os.path.exists(file_name))

        # delete node table
        conn = sqlite3.connect(file_name)
        cursor = conn.cursor()
        try:
            cursor.execute("DROP TABLE IF EXISTS nodes")
            print("Table 'nodes' deleted successfully.")
        except sqlite3.OperationalError as e:
            print(f"Error deleting table 'nodes': {e}")
        conn.commit()
        cursor.close()
        conn.close()
        # EOL delete node table

        new_org_name = "Edited Company"
        org = Organisation.objects.last()
        org.name = new_org_name
        org.save()
        update_sqlite(
            model=Organisation,
            data={"name": new_org_name},
            id=org.id,
        )
        print("SQLite file name:", file_name)
        conn = sqlite3.connect(file_name)
        self.assertEqual(
            1,
            len(
                pd.read_sql_query(
                    "SELECT * FROM nodes where name = ?",
                    conn,
                    params=[new_org_name],
                )
            ),
        )
        conn.close()
        os.remove(file_name)

    def test_error_update_sqlite(self):
        # Test for adding new org
        file_name = generate_sqlite(Organisation)
        self.assertTrue(os.path.exists(file_name))

        org = Organisation.objects.create(name="SQLite Company")
        # Add a new org
        update_sqlite(
            model=Organisation,
            data={"id": org.id, "name": org.name},
            id=None,
        )
        conn = sqlite3.connect(file_name)
        self.assertEqual(
            1,
            len(
                pd.read_sql_query(
                    "SELECT * FROM nodes where id = ?", conn, params=[org.id]
                )
            ),
        )
        conn.close()
        # Test update with SQLite connection error
        new_org_name = "Edited Company"
        org = Organisation.objects.last()
        org.name = new_org_name
        org.save()
        # Mock sqlite3.connect to raise an OperationalError
        with patch(
            "sqlite3.connect",
            side_effect=sqlite3.OperationalError("Mocked SQLite error"),
        ):
            # We expect the update_sqlite function to catch the exception
            # So we're testing that it doesn't crash
            with self.assertRaises(sqlite3.OperationalError) as context:
                update_sqlite(
                    model=Organisation,
                    data={"name": new_org_name},
                    id=org.id,
                )
            # Verify the error message
            self.assertIn("Mocked SQLite error", str(context.exception))
        # Now test with an undefined field (without mocking)
        # This should handle the error gracefully without updating the DB
        try:
            update_sqlite(
                model=Organisation,
                data={"undefined_field": new_org_name},
                id=org.id,
            )
        except Exception as e:
            self.fail(f"update_sqlite raised unexpected exception: {e}")
        # Verify the database was not updated with the undefined field
        conn = sqlite3.connect(file_name)
        cursor = conn.cursor()
        # Check if there's a column called 'undefined_field'
        cursor.execute("PRAGMA table_info(nodes)")
        columns = [info[1] for info in cursor.fetchall()]
        self.assertNotIn(
            "undefined_field",
            columns,
            "Undefined field should not be added to the database"
        )
        cursor.close()
        conn.close()
        os.remove(file_name)


@override_settings(USE_TZ=False, TEST_ENV=True)
class EntitiesSQLiteGenerationTest(TestCase):
    def setUp(self):
        super().setUp()
        call_command("organisation_seeder", "--test")
        sdCilandak = "SD NEGERI CILANDAK TIMUR 01"
        sdMenteng = "SD MENTENG ATAS 21 PAGI"
        seed_levels(geo_config=DEFAULT_ADMINISTRATION_LEVELS)
        AdministrationEntitiesTestFactory(
            {
                "name": "Indonesia",
                "children": [
                    {
                        "name": "Jakarta",
                        "children": [
                            {
                                "name": "Jakarta Selatan",
                                "children": [
                                    {
                                        "name": "Pasar Minggu",
                                        "entities": [
                                            {
                                                "entity": "Rumah Sakit",
                                                "name": "RSUD Jati Padang",
                                            },
                                            {
                                                "entity": "Sekolah",
                                                "name": sdCilandak,
                                            },
                                        ],
                                    },
                                    {
                                        "name": "Setiabudi",
                                        "entities": [
                                            {
                                                "entity": "Rumah Sakit",
                                                "name": "RS Agung",
                                            },
                                            {
                                                "entity": "Sekolah",
                                                "name": sdMenteng,
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ).populate()

    def test_generate_entity(self):
        file_name = generate_sqlite(Entity)
        self.assertTrue(os.path.exists(file_name))
        conn = sqlite3.connect(file_name)
        df = pd.read_sql_query("SELECT * FROM nodes", conn)
        self.assertEqual(
            list(Entity.objects.all().values_list("name", flat=True)),
            df["name"].values.tolist(),
        )
        conn.close()
        os.remove(file_name)

    def test_generate_entity_data(self):
        file_name = generate_sqlite(EntityData)
        self.assertTrue(os.path.exists(file_name))
        conn = sqlite3.connect(file_name)
        df = pd.read_sql_query("SELECT * FROM nodes", conn)
        self.assertEqual(
            list(EntityData.objects.all().values_list("name", flat=True)),
            df["name"].values.tolist(),
        )
        conn.close()
        os.remove(file_name)

    def test_sqlite_generation_command(self):
        call_command("generate_sqlite", "--test", True)
        generated_entity_sqlite = f"{MASTER_DATA}/test_entities.sqlite"
        generated_entity_data_sqlite = f"{MASTER_DATA}/test_entity_data.sqlite"
        self.assertTrue(os.path.exists(generated_entity_sqlite))
        self.assertTrue(os.path.exists(generated_entity_data_sqlite))
