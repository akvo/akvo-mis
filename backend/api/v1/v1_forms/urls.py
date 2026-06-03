from django.urls import re_path

from api.v1.v1_forms.views import (
    web_form_details,
    list_form,
    form_data,
    check_form_approver,
    form_approver,
    FormBuilderViewSet,
)


urlpatterns = [
    # Existing read-only (unchanged)
    re_path(r"^(?P<version>(v1))/forms$", list_form),
    re_path(r"^(?P<version>(v1))/form/(?P<form_id>[0-9]+)", form_data),
    re_path(
        r"^(?P<version>(v1))/form/web/(?P<form_id>[0-9]+)", web_form_details
    ),
    re_path(r"^(?P<version>(v1))/form/approver", form_approver),
    re_path(
        r"^(?P<version>(v1))/form/check-approver/(?P<form_id>[0-9]+)",
        check_form_approver,
    ),

    # Form Builder CRUD (sub-resource routes before generic)
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/publish$",
        FormBuilderViewSet.as_view({"post": "publish"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/unpublish$",
        FormBuilderViewSet.as_view({"post": "unpublish"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/duplicate$",
        FormBuilderViewSet.as_view({"post": "duplicate"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/versions$",
        FormBuilderViewSet.as_view({"get": "versions"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)"
        r"/activate/(?P<version_id>[0-9]+)$",
        FormBuilderViewSet.as_view({"post": "activate"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)$",
        FormBuilderViewSet.as_view(
            {"get": "retrieve", "put": "update", "delete": "destroy"}
        ),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms$",
        FormBuilderViewSet.as_view({"get": "list", "post": "create"}),
    ),
]
