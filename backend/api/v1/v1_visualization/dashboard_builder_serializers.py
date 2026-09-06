# =========================================================
# Dashboard builder: output shapes (VIZ-005)
# =========================================================
# Output only. Input is validated by
# dashboard_functions.validate_dashboard_payload(), which can return
# the widget index a DRF error dict has no room for.
#
# These shapes are the contract the merged builder (VIZ-004, VIZ-006)
# was written against, down to two asymmetries worth naming:
# root_form goes out as {id, name} but comes in as a plain int, and
# widget form/question are plain ints in both directions.

from django.db.models import Prefetch

from rest_framework import serializers

from api.v1.v1_forms.constants import FormTypes, QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionOptions
from api.v1.v1_visualization.constants import (
    DashboardKind,
    DashboardStatus,
    SUPPORTED_QUESTION_TYPES,
    WidgetTypes,
)
from api.v1.v1_visualization.models import Dashboard, DashboardWidget


class DashboardWidgetSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()

    class Meta:
        model = DashboardWidget
        fields = [
            "id",
            "order",
            "type",
            "col_span",
            "title",
            "color",
            "form",
            "question",
            "config",
        ]

    def get_type(self, instance):
        return WidgetTypes.FieldStr.get(instance.type)


class DashboardListSerializer(serializers.ModelSerializer):
    kind = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    root_form = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    widgets = serializers.SerializerMethodField()

    class Meta:
        model = Dashboard
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "kind",
            "status",
            "is_public",
            "root_form",
            "created",
            "updated",
            "created_by",
            "widgets",
        ]

    def get_kind(self, instance):
        return DashboardKind.FieldStr.get(instance.kind)

    def get_status(self, instance):
        return DashboardStatus.FieldStr.get(instance.status)

    def get_root_form(self, instance):
        form = instance.root_form
        # None for an embed: it has no root_form to describe.
        if form is None:
            return None
        return {"id": form.id, "name": form.name}

    def get_created_by(self, instance):
        user = instance.created_by
        if user is None:
            return None
        return {"id": user.id, "name": user.name}

    def get_widgets(self, instance):
        # Stubs, not full widgets: WidgetThumbnailStrip renders a
        # miniature layout from type + col_span alone.
        return [
            {
                "type": WidgetTypes.FieldStr.get(w.type),
                "col_span": w.col_span,
            }
            for w in instance.widgets.all()
        ]


class DashboardDetailSerializer(DashboardListSerializer):
    widgets = DashboardWidgetSerializer(many=True, read_only=True)

    class Meta(DashboardListSerializer.Meta):
        # embed_snippet lives here rather than on the list: it is up to
        # 20KB a row and the list has no reader for it — DashboardList
        # and the builder's slug lookup both use `kind` alone, and the
        # builder fetches this detail before it needs the snippet.
        fields = DashboardListSerializer.Meta.fields + [
            "embed_snippet",
            "default_filters",
            "published_at",
        ]


def serialize_question(question):
    row = {
        "id": question.id,
        "label": question.label,
        # "Multiple_Option" -> "multiple_option". BuilderInspector
        # compares against lowercase literals, so the map is lowercased
        # at the boundary rather than duplicated.
        "type": QuestionTypes.FieldStr.get(question.type, "").lower(),
    }
    if question.type in (
        QuestionTypes.option,
        QuestionTypes.multiple_option,
    ):
        # .all(), not .order_by(): chaining a fresh filter/order call on
        # a prefetched related manager clones the queryset and drops
        # its cached results, which would silently reintroduce the
        # one-query-per-question cost prefetch_related below exists to
        # remove. The ordering is baked into that Prefetch instead.
        row["options"] = [
            {"value": option.value, "label": option.label}
            for option in question.options.all()
        ]
    return row


def serialize_source_form(form, is_root):
    row = {
        "id": form.id,
        "name": form.name,
        "type": FormTypes.FieldStr.get(form.type, "").lower(),
    }
    if not is_root:
        row["parent"] = form.parent_id
    row["questions"] = [
        serialize_question(question)
        for question in form.form_questions.filter(
            type__in=SUPPORTED_QUESTION_TYPES
        ).order_by("order", "id").prefetch_related(
            Prefetch(
                "options",
                queryset=QuestionOptions.objects.order_by("order", "id"),
            )
        )
    ]
    return row


def serialize_sources(dashboard, user):
    """The dashboard's form family, as the inspector needs it.

    No form-status filter: the family is a structural fact, and §4.5
    imposes no status rule. Filtering to published here would make a
    dashboard's own root_form vanish from its source list the moment
    someone unpublished it.

    Children are resolved through the same Forms.objects.for_user(user)
    the validator uses (dashboard_functions.validate_dashboard_payload)
    rather than the plain `root.children` reverse relation, so this
    endpoint and the save-time rule draw the family line identically —
    "two barriers, one rule".
    """
    root = dashboard.root_form
    forms = [serialize_source_form(root, is_root=True)]
    children = Forms.objects.for_user(user).filter(
        parent=root
    ).order_by("id")
    forms.extend(
        serialize_source_form(child, is_root=False) for child in children
    )
    return {"forms": forms}
