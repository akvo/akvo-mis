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
    with connection.cursor() as cursor:
        for sql in connection.ops.sequence_reset_sql(no_style(), [Levels]):
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
                    # The row names no parent at this tier, so attach to
                    # the root. This used to look the root up by
                    # COUNTRY_NAME.capitalize(), which was "Fiji" even
                    # while seeding the Indonesian sample.
                    parent = Administration.objects.filter(
                        parent__isnull=True
                    ).first()

        # Get the level from the geo_config
        level = Levels.objects.filter(level=geo["level"]).first()
        # Get the code from the row
        code = row.get(f"code_{geo['level']}")
        # Get the name from the row
        name = row.get(col_level)
        # A row that names no unit at this tier creates nothing. The old
        # code invented one from COUNTRY_NAME here, which put a "Fiji"
        # root into every fixture regardless of the data.
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


class Command(BaseCommand):
    help = (
        "Seed the bundled sample hierarchy, for development and tests. "
        "For a real hierarchy in a real workspace use "
        "administration_csv_seeder, which is tenant-aware."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-t", "--test", nargs="?", const=1, default=False, type=int
        )
        parser.add_argument(
            "-c", "--clean", nargs="?", const=1, default=False, type=int
        )

    def handle(self, *args, **options):
        clean = options.get("clean")
        if clean:
            Levels.objects.all().delete()
            Administration.objects.all().delete()
            self.stdout.write("-- Administration Cleared")
        # --test is accepted but no longer switches anything: the
        # TopoJSON path it used to select was hardcoded to one country
        # and wrote tenant=None. The flag stays so the 140-odd callers
        # that pass it keep working.
        seed_administration_test()
