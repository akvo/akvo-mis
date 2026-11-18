from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from utils.custom_permissions import DataOnboardingAccess


@extend_schema(tags=["Data Onboarding"], summary="List Data Onboardings")
@api_view(["GET"])
@permission_classes([IsAuthenticated, DataOnboardingAccess])
def data_onboarding_list(request, version):
    # No DataOnboarding record exists yet; the model lands with upload.
    return Response([])
