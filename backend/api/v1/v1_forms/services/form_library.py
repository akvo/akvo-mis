"""FB-018 Form Library service.

A thin layer over existing machinery (see doc/design/FB-018-form-library.md).
A template is an ordinary form marked with ``meta["template"] = True`` and
owned by no workspace (``tenant`` is NULL, since templates are created by
curators, who are platform admins with no tenant). This module adds the
library browse query, the family clone used by "Use this form", and the
cross-tenant promote. ``duplicate_form`` is reused unchanged.

# ponytail: template-ness lives in the meta JSON (no new column). Promote to
# a real indexed column only if the catalog ever needs heavy filtering.
"""
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_forms.functions import duplicate_form
from api.v1.v1_forms.models import FormCategory, Forms


def library_registration_qs():
    """Published registration templates (family roots).

    This is the one deliberate cross-tenant read; it does NOT use for_user().
    """
    return Forms.objects.filter(
        meta__template=True,
        type=FormTypes.registration,
        status=FormStatus.published,
        parent__isnull=True,
    )


def get_library_form(form_id):
    """A single published registration template by id, or None."""
    return library_registration_qs().filter(pk=form_id).first()


def _published_children(registration):
    return registration.children.filter(
        status=FormStatus.published
    ).order_by("id")


@transaction.atomic
def clone_family(registration, user):
    """'Use this form': clone the template family into the caller's tenant.

    duplicate_form already re-tenants each copy to ``user.tenant`` and sets it
    draft, and does NOT copy meta, so the clone carries no template flag. We
    only re-point the children's parent, stamp provenance, and bump the
    template's import_count.

    Returns (new_registration, [new_monitoring, ...]).
    """
    new_registration = duplicate_form(registration, user=user)
    new_registration.meta = {
        "copied_from": {
            "form_id": registration.id,
            "name": registration.name,
            "at": timezone.now().date().isoformat(),
        }
    }
    new_registration.save(update_fields=["meta"])

    new_children = []
    for child in _published_children(registration):
        new_child = duplicate_form(child, user=user)
        # duplicate_form copies parent_id verbatim (the library registration);
        # re-point it to the freshly created registration in the caller tenant.
        new_child.parent_id = new_registration.id
        new_child.save(update_fields=["parent"])
        new_children.append(new_child)

    Forms.objects.filter(pk=registration.id).update(
        import_count=F("import_count") + 1
    )
    return new_registration, new_children


@transaction.atomic
def promote_family(source_registration, user, category_ids=None):
    """'Promote' (Path 1): snapshot a source family into the Library.

    The source (which lives in some workspace) is never modified. Each copy
    is marked as a template (meta.template), left tenant-less, and published;
    the source workspace is recorded in meta.source. Returns the new
    registration template.
    """
    source_tenant = source_registration.tenant
    now = timezone.now()

    def _to_template(new_form, source_name, meta):
        # duplicate_form appends " (Copy)", sets draft + the caller's tenant
        # (None, as the curator is a platform admin). For a template we keep
        # the real name, publish it, and tag it in meta. tenant stays NULL.
        new_form.name = source_name
        new_form.status = FormStatus.published
        new_form.published_at = now
        new_form.meta = meta

    new_registration = duplicate_form(source_registration, user=user)
    _to_template(
        new_registration,
        source_registration.name,
        {
            "template": True,
            "source": {
                "tenant_id": getattr(source_tenant, "id", None),
                "tenant_name": (
                    getattr(source_tenant, "name", "")
                    or getattr(source_tenant, "subdomain", None)
                ),
                "form_id": source_registration.id,
                "promoted_at": now.date().isoformat(),
            },
        },
    )
    new_registration.save(
        update_fields=["name", "status", "published_at", "meta"]
    )
    if category_ids:
        new_registration.categories.set(
            FormCategory.objects.filter(id__in=category_ids)
        )

    for child in _published_children(source_registration):
        new_child = duplicate_form(child, user=user)
        # Children are reached via the parent template, not listed directly,
        # so they carry no template flag; just publish and re-point.
        _to_template(new_child, child.name, None)
        new_child.parent_id = new_registration.id
        new_child.save(
            update_fields=["name", "status", "published_at", "meta", "parent"]
        )

    return new_registration
