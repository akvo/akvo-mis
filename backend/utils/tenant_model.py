from django.db import models


def tenant_fk(related_name: str) -> models.ForeignKey:
    # Ownership FK for the definition-root tables. Nullable so
    # pre-existing rows and the test seeders stay valid; PROTECT so
    # removing a tenant that still owns data stays an explicit decision.
    # The lazy reference keeps this usable from any app.
    return models.ForeignKey(
        "v1_users.Tenant",
        on_delete=models.PROTECT,
        related_name=related_name,
        default=None,
        null=True,
    )
