from rest_framework import status
from rest_framework.response import Response

from api.v1.v1_profile.models import Levels


def bulk_upload_ready(user):
    """Is this tenant's hierarchy defined enough to upload units into?

    Bulk upload is meaningful only once the tenant has named its top tier
    and added at least one tier below it. Without a deeper level the
    template is a single column holding the root the tenant already has,
    and an upload against it could not say anything new. Configuration
    always names level 0, so in practice this asserts "a level below the
    root exists".
    """
    levels = Levels.objects.for_user(user)
    has_named_level_0 = levels.filter(level=0).exclude(name="").exists()
    has_deeper_level = levels.filter(level__gte=1).exists()
    return has_named_level_0 and has_deeper_level


def bulk_upload_not_ready_response():
    return Response(
        {"message": "Define your administrative levels first: name the top "
                    "level and add at least one level below it."},
        status=status.HTTP_400_BAD_REQUEST,
    )
