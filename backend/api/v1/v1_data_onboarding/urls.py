from django.urls import re_path

from api.v1.v1_data_onboarding.views import (
    data_onboarding_detail,
    data_onboarding_list,
)

urlpatterns = [
    re_path(r"^(?P<version>(v1))/data-onboarding$", data_onboarding_list),
    re_path(
        r"^(?P<version>(v1))/data-onboarding/(?P<pk>[0-9]+)$",
        data_onboarding_detail,
    ),
]
