from django.core.management import BaseCommand
from django.utils.text import slugify

from api.v1.v1_forms.models import FormCategory

# Starter categories named in the planning call. Curators add more at runtime.
STARTER_CATEGORIES = ["WASH", "Agriculture"]


class Command(BaseCommand):
    help = (
        "FB-018: provision the Form Library starter categories. "
        "Idempotent — safe to run more than once. Templates themselves are "
        "ordinary tenant-less forms marked with meta.template; no dedicated "
        "tenant is needed."
    )

    def handle(self, *args, **options):
        for name in STARTER_CATEGORIES:
            _, created = FormCategory.objects.get_or_create(
                slug=slugify(name), defaults={"name": name}
            )
            verb = "created" if created else "exists"
            self.stdout.write(f"  category {name}: {verb}")
