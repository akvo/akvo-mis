import json
from mis.settings import COUNTRY_NAME
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connection
from api.v1.v1_profile.models import Levels, Administration
from api.v1.v1_profile.constants import (
    DEFAULT_ADMINISTRATION_DATA,
    DEFAULT_ADMINISTRATION_LEVELS,
)


def seed_levels(geo_config: list = []) -> None:
    """
    Seed the Levels model with the given geo_config.
    :param geo_config: A list of dictionaries containing the geo configuration.
    """
    for geo in geo_config:
        level = Levels(id=geo["id"], name=geo["alias"], level=geo["level"])
        level.save()
    # Saving with an explicit id bypasses the id sequence, which stays
    # where it was. Registration creates a level of its own per tenant,
    # so the next insert would collide with a seeded id. Realign the
    # sequence with the rows actually present.
    reset_sql = connection.ops.sequence_reset_sql(no_style(), [Levels])
    with connection.cursor() as cursor:
        for sql in reset_sql:
            cursor.execute(sql)


def seed_administration(row: dict, geo_config: list = []) -> None:
    """
    Seed the Administration model with the given row data and geo_config.
    :param row: A dictionary containing the row data.
    :param geo_config: A list of dictionaries containing the geo configuration.
    """
    for geo in geo_config:
        col_level = f"{geo['alias']}_{geo['level']}"
        parent = None
        if geo["level"] > 0:
            # Get parent Level
            prev_level = geo["level"] - 1
            parent_level = Levels.objects.filter(
                level=prev_level
            ).first()
            if parent_level:
                parent_key = f"{parent_level.name}_{parent_level.level}"
                parent_name = row.get(parent_key)
                if parent_name:
                    parent = Administration.objects.filter(
                        name=parent_name,
                        level=parent_level
                    ).first()
                else:
                    parent = Administration.objects.filter(
                        name=COUNTRY_NAME.capitalize()
                    ).first()

        # Get the level from the geo_config
        level = Levels.objects.filter(level=geo["level"]).first()
        # Get the code from the row
        code = row.get(f"code_{geo['level']}")
        # Get the name from the row
        name = row.get(col_level)
        if not name and geo["level"] == 0:
            name = COUNTRY_NAME.capitalize()
        if name:
            Administration.objects.update_or_create(
                name=name,
                defaults={
                    "level": level,
                    "code": code,
                    "parent": parent,
                },
            )


def seed_administration_test(
    rows: list = DEFAULT_ADMINISTRATION_DATA,
    geo_config: list = DEFAULT_ADMINISTRATION_LEVELS,
) -> None:
    """
    Seed the Administration model with test data.
    :param rows: A list of dictionaries containing the row data.
    :param geo_config: A list of dictionaries containing the geo configuration.
    """
    seed_levels(geo_config=geo_config)
    for row in rows:
        seed_administration(row=row, geo_config=geo_config)


def seed_administration_prod() -> int:
    """
    Seed the Administration model with production data from a TopoJSON file.
    :return: The number of administrations created.
    """
    topojson_file_path = f"./source/{COUNTRY_NAME}.topojson"
    with open(topojson_file_path, "r") as f:
        topo_data = json.load(f)
        features = topo_data.get('objects', {}).values()
        administrations = [
            f["properties"]
            for fg in features
            for f in fg.get('geometries', [])
        ]
        if administrations:
            # Get first row of administrations to seed_levels
            first_row = administrations[0]
            geo_config = list(first_row.keys())
            # Filter out keys that end with pattern "_<digit>"
            # eg: "Province_1"
            geo_config = [
                key for key in geo_config if (
                    key.split("_")[-1].isdigit()
                    and not key.startswith("code_")
                )
            ]
            geo_config = [
                {
                    "level": int(key.split("_")[-1]),
                    "alias": key.split("_")[0],
                }
                for i, key in enumerate(geo_config)
            ]
            # Order geo_config by level
            geo_config.sort(key=lambda x: x["level"])
            # Add id to geo_config
            for i, geo in enumerate(geo_config):
                # Assign id starting from 2
                # to avoid conflict with the national level
                geo["id"] = i + 2
            # Add the national level
            geo_config.insert(
                0,
                {"id": 1, "level": 0, "alias": "National"}
            )
            seed_levels(geo_config=geo_config)

            for adm in administrations:
                seed_administration(row=adm, geo_config=geo_config)

        return len(administrations)


class Command(BaseCommand):
    help = "Generates administrations from the TopoJSON."

    def add_arguments(self, parser):
        parser.add_argument(
            "-t", "--test", nargs="?", const=1, default=False, type=int
        )
        parser.add_argument(
            "-c", "--clean", nargs="?", const=1, default=False, type=int
        )

    def handle(self, *args, **options):
        test = options.get("test")
        clean = options.get("clean")
        if clean:
            Levels.objects.all().delete()
            Administration.objects.all().delete()
            self.stdout.write("-- Administration Cleared")
        if test:
            seed_administration_test()
        if not test:
            total = seed_administration_prod()
            self.stdout.write(self.style.SUCCESS(
                f"Created {total} Administrations successfully."
            ))  # pragma: no cover
