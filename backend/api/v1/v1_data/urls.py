from django.urls import re_path

from api.v1.v1_data.views import (
    DataAnswerDetailDeleteView,
    export_form_data,
    FormDataAddListView,
    PendingFormDataView,
    PendingDataDetailDeleteView,
    DataDetailDeleteView,
)
from api.v1.v1_users.views import health_check, get_config_file, email_template

urlpatterns = [
    re_path(
        r"^(?P<version>(v1))/form-data/(?P<form_id>[0-9]+)",
        FormDataAddListView.as_view(),
    ),
    re_path(
        r"^(?P<version>(v1))/data/(?P<data_id>[0-9]+)",
        DataAnswerDetailDeleteView.as_view(),
    ),
    re_path(
        r"^(?P<version>(v1))/form-pending-data/(?P<form_id>[0-9]+)",
        PendingFormDataView.as_view(),
    ),
    re_path(
        r"^(?P<version>(v1))/data-details/(?P<data_id>[0-9]+)",
        DataDetailDeleteView.as_view(),
    ),
    re_path(
        r"^(?P<version>(v1))/pending-data/(?P<pending_data_id>[0-9]+)",
        PendingDataDetailDeleteView.as_view(),
    ),
    re_path(
        r"^(?P<version>(v1))/export/form/(?P<form_id>[0-9]+)", export_form_data
    ),
    re_path(r"^(?P<version>(v1))/health/check", health_check),
    re_path(r"^(?P<version>(v1))/config.js", get_config_file),
    re_path(r"^(?P<version>(v1))/email_template", email_template),
]
