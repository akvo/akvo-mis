from django.urls import re_path

from api.v1.v1_forms.views import (
    web_form_details,
    list_form,
    form_data,
    check_form_approver,
    form_approver,
    form_detail,
    publish_form,
    duplicate_form_view,
    form_versions,
)


urlpatterns = [
    # Existing read-only (unchanged)
    re_path(
        r"^(?P<version>(v1))/form/web/(?P<form_id>[0-9]+)",
        web_form_details,
    ),
    re_path(r"^(?P<version>(v1))/form/(?P<form_id>[0-9]+)", form_data),
    re_path(r"^(?P<version>(v1))/form/approver", form_approver),
    re_path(
        r"^(?P<version>(v1))/form/check-approver/(?P<form_id>[0-9]+)",
        check_form_approver,
    ),

    # CRUD: sub-resource routes first (more specific before generic)
    re_path(
        r"^(?P<version>(v1))/forms/(?P<pk>[0-9]+)/publish$",
        publish_form,
    ),
    re_path(
        r"^(?P<version>(v1))/forms/(?P<pk>[0-9]+)/duplicate$",
        duplicate_form_view,
    ),
    re_path(
        r"^(?P<version>(v1))/forms/(?P<pk>[0-9]+)/versions$",
        form_versions,
    ),
    re_path(r"^(?P<version>(v1))/forms/(?P<pk>[0-9]+)$", form_detail),
    re_path(r"^(?P<version>(v1))/forms$", list_form),
]
