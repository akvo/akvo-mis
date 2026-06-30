import json
from mis.settings import COUNTRY_NAME
from django.core.management.base import BaseCommand
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
            # Key on name + level + parent: in the Marshall Islands many
            # islets share their atoll's (municipality's) name, so name
            # alone is not unique across the hierarchy.
            Administration.objects.update_or_create(
                name=name,
                level=level,
                parent=parent,
                defaults={
                    "code": code,
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
            # HDX TopoJSON files concatenate the adm0/adm1/adm2 layers, but
            # only the leaf features carry the full "<alias>_<level>" path
            # (e.g. National_0, Municipality_1, Islet_2). The top layers lack
            # those keys, so keep only features that carry the alias path --
            # otherwise the level config can't be derived and the keyless
            # rows create a spurious root via the COUNTRY_NAME fallback.
            def level_keys(row: dict) -> list:
                return [
                    k for k in row.keys()
                    if k.split("_")[-1].isdigit() and not k.startswith("code_")
                ]

            administrations = [
                adm for adm in administrations if level_keys(adm)
            ]

            # Build the level config from the union of alias keys (one per
            # level, deduplicated) so it doesn't depend on the first row.
            alias_by_level = {}
            for adm in administrations:
                for key in level_keys(adm):
                    alias_by_level[int(key.split("_")[-1])] = \
                        key.split("_")[0]
            geo_config = [
                {"level": level, "alias": alias}
                for level, alias in sorted(alias_by_level.items())
            ]
            # Ensure a national (level 0) level exists for files that only
            # provide sub-national levels (e.g. levels starting at 1).
            if not any(geo["level"] == 0 for geo in geo_config):
                geo_config.insert(0, {"level": 0, "alias": "National"})
            # Assign sequential ids ordered by level.
            for i, geo in enumerate(geo_config):
                geo["id"] = i + 1
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
