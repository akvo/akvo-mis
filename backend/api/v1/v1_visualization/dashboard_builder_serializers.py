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

from rest_framework import serializers

from api.v1.v1_forms.constants import FormTypes, QuestionTypes
from api.v1.v1_visualization.constants import (
    DashboardStatus,
    WidgetTypes,
)
from api.v1.v1_visualization.models import Dashboard, DashboardWidget


def form_ref(form):
    if form is None:
        return None
    return {"id": form.id, "name": form.name}


def user_ref(user):
    if user is None:
        return None
    return {"id": user.id, "name": user.name}


def lower_form_type(form):
    return FormTypes.FieldStr.get(form.type, "").lower()


def lower_question_type(question):
    # "Multiple_Option" -> "multiple_option". BuilderInspector compares
    # against lowercase literals, so the map is lowercased at the
    # boundary rather than duplicated.
    return QuestionTypes.FieldStr.get(question.type, "").lower()


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
            "status",
            "root_form",
            "created",
            "updated",
            "created_by",
            "widgets",
        ]

    def get_status(self, instance):
        return DashboardStatus.FieldStr.get(instance.status)

    def get_root_form(self, instance):
        return form_ref(instance.root_form)

    def get_created_by(self, instance):
        return user_ref(instance.created_by)

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
        fields = DashboardListSerializer.Meta.fields + [
            "default_filters",
            "published_at",
        ]
