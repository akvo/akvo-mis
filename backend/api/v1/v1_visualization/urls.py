from django.urls import re_path
from api.v1.v1_visualization.views import (
    formdata_stats,
    monitoring_stats,
    GeolocationListView,
    visualization_values_formula,
)
from api.v1.v1_visualization.dashboard_views import (
    visualization_values,
    visualization_escalation,
)
from api.v1.v1_visualization.dashboard_builder_views import (
    DashboardBuilderViewSet,
)
from api.v1.v1_visualization.dashboard_read_views import (
    DashboardReadViewSet,
)
from api.v1.v1_visualization.embed_views import serve_embed

urlpatterns = [
    re_path(
        r"^(?P<version>(v1))/visualization/monitoring-stats",
        monitoring_stats,
    ),
    re_path(
        r"^(?P<version>(v1))/visualization/formdata-stats/(?P<form_id>[0-9]+)",
        formdata_stats,
    ),
    re_path(
        r"^(?P<version>(v1))/maps/geolocation/(?P<form_id>[0-9]+)",
        GeolocationListView.as_view(),
    ),
    re_path(
        r"^(?P<version>(v1))/visualization/values/formula$",
        visualization_values_formula,
    ),
    re_path(
        r"^(?P<version>(v1))/visualization/values",
        visualization_values,
    ),
    re_path(
        r"^(?P<version>(v1))/visualization/escalation/(?P<form_id>[0-9]+)",
        visualization_escalation,
    ),
    # Dashboard builder CRUD (sub-resource routes before generic)
    re_path(
        r"^(?P<version>(v1))/manage/dashboards/(?P<pk>[0-9]+)/sources$",
        DashboardBuilderViewSet.as_view({"get": "sources"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/dashboards/(?P<pk>[0-9]+)/publish$",
        DashboardBuilderViewSet.as_view({"post": "publish"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/dashboards/(?P<pk>[0-9]+)/"
        r"unpublish$",
        DashboardBuilderViewSet.as_view({"post": "unpublish"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/dashboards/(?P<pk>[0-9]+)/"
        r"visibility$",
        DashboardBuilderViewSet.as_view({"post": "visibility"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/dashboards/(?P<pk>[0-9]+)/"
        r"duplicate$",
        DashboardBuilderViewSet.as_view({"post": "duplicate"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/dashboards/(?P<pk>[0-9]+)/"
        r"embed-preview$",
        DashboardBuilderViewSet.as_view({"post": "embed_preview"}),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/dashboards/(?P<pk>[0-9]+)$",
        DashboardBuilderViewSet.as_view(
            {"get": "retrieve", "put": "update", "delete": "destroy"}
        ),
    ),
    re_path(
        r"^(?P<version>(v1))/manage/dashboards$",
        DashboardBuilderViewSet.as_view(
            {"get": "list", "post": "create"}
        ),
    ),
    # The embed document, served on EMBED_HOST only. `[^/]+` rather than a
    # character class: a Django signing token carries ":" separators.
    re_path(
        r"^(?P<version>(v1))/embed/(?P<token>[^/]+)$",
        serve_embed,
    ),
    # The anonymous-capable read namespace (slug before collection)
    re_path(
        r"^(?P<version>(v1))/dashboards/(?P<slug>[-a-z0-9]+)$",
        DashboardReadViewSet.as_view({"get": "retrieve"}),
    ),
    re_path(
        r"^(?P<version>(v1))/dashboards$",
        DashboardReadViewSet.as_view({"get": "list"}),
    ),
]
