from django.urls import re_path

from api.v1.v1_forms.views import (
    web_form_details,
    list_form,
    list_published_forms,
    form_data,
    check_form_approver,
    form_approver,
    FormBuilderViewSet,
)


urlpatterns = [
    # Existing read-only (unchanged)
    re_path(r"^(?P<version>(v1))/forms/published$", list_published_forms),
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
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/archive$",
        FormBuilderViewSet.as_view({"post": "archive"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/restore$",
        FormBuilderViewSet.as_view({"post": "restore"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)"
        r"/versions/(?P<version_id>[0-9]+)$",
        FormBuilderViewSet.as_view({"get": "version_detail"}),
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
    # FB-007 & FB-014: Form Import/Export
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/export$",
        FormBuilderViewSet.as_view({"get": "export_definition"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/export-xlsform$",
        FormBuilderViewSet.as_view({"get": "export_xlsform"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)/administration-csv$",
        FormBuilderViewSet.as_view({"get": "export_administration_csv"}),
    ),
    # FB-016: XLSForm Import
    re_path(
        r"^(?P<version>(v1))/manage/forms/import/xlsform/preflight$",
        FormBuilderViewSet.as_view({"post": "import_xlsform_preflight"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/import/xlsform$",
        FormBuilderViewSet.as_view({"post": "import_xlsform"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/import/preflight$",
        FormBuilderViewSet.as_view({"post": "import_preflight"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/import/status/(?P<task_id>[^/.]+)$",
        FormBuilderViewSet.as_view({"get": "import_status"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/forms/import$",
        FormBuilderViewSet.as_view({"post": "import_definition"}),
    ),
]
