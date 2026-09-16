from django.core.management import BaseCommand
from api.v1.v1_profile.models import (
    Administration,
    AdministrationAttribute,
    AdministrationAttributeValue,
    Levels,
)
from api.v1.v1_mobile.models import MobileAssignment
from faker import Faker
from typing import List
from utils.tenant_command import resolve_tenant

fake = Faker()


def seed_administration_attribute(self, test: bool, tenant=None):
    attribute_types = ["value", "option", "multiple_option", "aggregate"]
    for at in attribute_types:
        name = "Population"
        options = []
        if at == "option":
            name = "Urban or Rural"
            options = ["Urban", "Rural"]
        if at == "multiple_option":
            name = "Primary Occupations"
            options = ["Agriculture", "Livestock Farming", "Tourism"]
        if at == "aggregate":
            name = "Education"
            options = ["Primary", "Secondary", "Higher"]
        if not test:
            self.stdout.write(name)
        # get_or_create on (name, tenant), the key administration_csv_seeder
        # already uses. `create()` meant a second run produced a second
        # "Population" attribute for the same workspace, and the attribute
        # manager lists both.
        AdministrationAttribute.objects.get_or_create(
            name=name,
            tenant=tenant,
            defaults={"type": at, "options": options},
        )


def seed_administration_attribute_value(
    self,
    adm_attributes: List[AdministrationAttribute],
    administration: Administration,
    test: bool,
):
    for adm_attr in adm_attributes:
        value = fake.random_int(min=50, max=500)
        if adm_attr.type in ["option", "multiple_option", "aggregate"]:
            value = fake.random_choices(
                elements=adm_attr.options,
                length=(
                    fake.random_int(min=1, max=len(adm_attr.options))
                    if adm_attr.type == "multiple_option"
                    else 1
                ),
            )
        value = {"value": value}
        if not test:
            self.stdout.write(f"{administration.name} - {adm_attr.name}")
        AdministrationAttributeValue.objects.create(
            administration=administration, attribute=adm_attr, value=value
        )


def seed_data(self, repeat: int = 2, test: bool = False, tenant=None):
    # Every lookup below is scoped. Unscoped, this attached one
    # workspace's attributes to another workspace's administrations --
    # AdministrationAttributeValue would then carry an `administration`
    # owned by A and an `attribute` owned by B, which no tenant filter
    # can untangle afterwards.
    adm_attributes = AdministrationAttribute.objects.filter(tenant=tenant)
    mobile_assignments = MobileAssignment.objects.filter(
        user__tenant=tenant
    ).prefetch_related(
        "administrations",
    )
    adms = [
        adm
        for m in mobile_assignments
        for adm in [a for a in m.administrations.all()]
    ]
    for adm in adms:
        seed_administration_attribute_value(
            self, adm_attributes=adm_attributes, administration=adm, test=test
        )
    if len(adms) == 0:
        # Generate randomly. order_by("-level"), not "-id": ids ascend by
        # creation order across the whole install, so on a multi-workspace
        # database the highest id was whichever workspace was configured
        # last -- not the deepest tier of this one.
        last_level = (
            Levels.objects.filter(tenant=tenant).order_by("-level").first()
        )
        if last_level is None:
            return
        randoms = Administration.objects.filter(
            level=last_level, tenant=tenant
        ).order_by("?")[:repeat]
        for r in randoms:
            seed_administration_attribute_value(
                self,
                adm_attributes=adm_attributes,
                administration=r,
                test=test,
            )


class Command(BaseCommand):
    help = (
        "Seed example administration attributes and values for one "
        "workspace. Omit --tenant to seed the tenant-less space."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-t", "--test", nargs="?", const=False, default=False, type=bool
        )
        parser.add_argument(
            "-r", "--repeat", nargs="?", const=3, default=3, type=int
        )
        parser.add_argument(
            "-c", "--clean", nargs="?", const=1, default=False, type=int
        )
        # No short flag: -t is already --test here.
        parser.add_argument(
            "--tenant",
            default=None,
            type=str,
            help=(
                "Workspace subdomain to seed into. Omit to seed the "
                "tenant-less space."
            ),
        )

    def handle(self, *args, **options):
        test = options.get("test")
        repeat = options.get("repeat")
        clean = options.get("clean")
        tenant = resolve_tenant(options.get("tenant"))
        if clean:
            # Scoped, because this deletes. Unscoped it wiped every
            # workspace's attribute definitions, including ones imported
            # from a real hierarchy by administration_csv_seeder --
            # "Bounding Box" among them, which the data seeder needs.
            AdministrationAttributeValue.objects.filter(
                administration__tenant=tenant
            ).delete()
            self.stdout.write("-- Administration attribute value Cleared")
            AdministrationAttribute.objects.filter(tenant=tenant).delete()
            self.stdout.write("-- Administration attribute Cleared")
        else:
            seed_administration_attribute(self, test=test, tenant=tenant)
            seed_data(self, repeat=repeat, test=test, tenant=tenant)
        if not test:
            self.stdout.write("-- FINISH")
