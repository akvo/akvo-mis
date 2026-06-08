import uuid

from django.db import models

# Create your models here.
from api.v1.v1_forms.constants import (
    QuestionTypes,
    AttributeTypes,
    FormTypes,
    FormStatus,
)
from api.v1.v1_users.models import SystemUser
from utils.soft_deletes_model import SoftDeletes


class Forms(models.Model):
    name = models.TextField()
    description = models.TextField(default=None, null=True)
    version = models.IntegerField(default=1)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    approval_instructions = models.JSONField(default=None, null=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    type = models.IntegerField(
        choices=FormTypes.FieldStr.items(),
        default=FormTypes.registration,
    )
    status = models.IntegerField(
        choices=FormStatus.FieldStr.items(),
        default=FormStatus.draft,
    )
    published_at = models.DateTimeField(null=True, blank=True, default=None)
    previous_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="next_versions",
        null=True,
        blank=True,
    )
    languages = models.JSONField(default=None, null=True)
    default_language = models.CharField(
        max_length=255, null=True, default=None
    )
    translations = models.JSONField(default=None, null=True)
    # Points to the snapshot currently used for new data collections.
    # Null while the form is a draft (no published version yet).
    # Updated by publish (auto) and activate (manual rollback).
    active_version = models.ForeignKey(
        "FormPublishedVersion",
        on_delete=models.SET_NULL,
        related_name="active_for_forms",
        null=True,
        blank=True,
        default=None,
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "form"


class QuestionGroup(SoftDeletes):
    form = models.ForeignKey(
        to=Forms, on_delete=models.CASCADE, related_name="form_question_group"
    )
    name = models.CharField(max_length=255)
    label = models.TextField(null=True, default=None)
    order = models.BigIntegerField(null=True, default=None)
    repeatable = models.BooleanField(default=False)
    repeat_text = models.CharField(
        max_length=255, default=None, null=True
    )
    translations = models.JSONField(default=None, null=True)

    def __str__(self):
        return self.name

    class Meta:
        # Only active (non-deleted) groups must be unique per form.
        # A soft-deleted group may share its name with a new active group
        # so the editor can recreate a group after a soft-delete (FB-002A).
        constraints = [
            models.UniqueConstraint(
                fields=["form", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_form_question_group",
            )
        ]
        db_table = "question_group"


class Questions(SoftDeletes):
    form = models.ForeignKey(
        to=Forms, on_delete=models.CASCADE, related_name="form_questions"
    )
    question_group = models.ForeignKey(
        to=QuestionGroup,
        on_delete=models.CASCADE,
        related_name="question_group_question",
    )
    order = models.BigIntegerField(null=True, default=None)
    label = models.TextField()
    short_label = models.TextField(null=True, default=None)
    name = models.CharField(max_length=255, default=None, null=True)
    type = models.IntegerField(choices=QuestionTypes.FieldStr.items())
    meta = models.BooleanField(default=False)
    required = models.BooleanField(default=True)
    rule = models.JSONField(default=None, null=True)
    dependency = models.JSONField(default=None, null=True)
    dependency_rule = models.CharField(
        max_length=3,
        choices=[('AND', 'AND'), ('OR', 'OR')],
        null=True,
        blank=True,
        help_text=(
            'Dependency evaluation rule: AND or OR.'
            ' Defaults to AND in client logic if not specified.'
        )
    )
    api = models.JSONField(default=None, null=True)
    extra = models.JSONField(default=None, null=True)
    tooltip = models.JSONField(default=None, null=True)
    fn = models.JSONField(default=None, null=True)
    pre = models.JSONField(default=None, null=True)
    display_only = models.BooleanField(default=False, null=True)
    variable_name = models.CharField(max_length=255, null=True, default=None)
    translations = models.JSONField(default=None, null=True)
    hidden_string = models.BooleanField(default=None, null=True)
    required_double_entry = models.BooleanField(default=False)
    disabled = models.BooleanField(default=False, null=True)
    addon_before = models.CharField(max_length=50, null=True, default=None)
    addon_after = models.CharField(max_length=50, null=True, default=None)
    data_api_url = models.CharField(max_length=255, null=True, default=None)
    center = models.JSONField(default=None, null=True)

    def __str__(self):
        return f"[TYPE: {self.type}] {self.label}"

    def to_definition(self):
        options = self.options.values("label", "value")
        return {
            "id": self.id,
            "qg_id": self.question_group.id,
            "order": (self.order or 0) + 1,
            "name": self.name,
            "label": self.label,
            "short_label": self.short_label,
            "type": QuestionTypes.FieldStr.get(self.type),
            "required": self.required,
            "rule": self.rule,
            "dependency": self.dependency,
            "dependency_rule": (self.dependency_rule or "AND").upper(),
            "options": options,
            "extra": self.extra,
            "tooltip": self.tooltip,
            "fn": self.fn,
            "pre": self.pre,
            "display_only": self.display_only,
            "form_name": self.form.name,
        }

    class Meta:
        # Conditional unique: soft-deleted questions may share a name with a
        # new active question on the same form (same reasoning as
        # QuestionGroup — see FB-002A).
        constraints = [
            models.UniqueConstraint(
                fields=["form", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_form_question",
            )
        ]
        db_table = "question"


class QuestionOptions(models.Model):
    question = models.ForeignKey(
        to=Questions, on_delete=models.CASCADE, related_name="options"
    )
    order = models.BigIntegerField(null=True, default=None)
    label = models.TextField(default=None, null=True)
    value = models.CharField(max_length=255, default=None, null=True)
    other = models.BooleanField(default=False)
    color = models.TextField(default=None, null=True)
    translations = models.JSONField(default=None, null=True)

    def __str__(self):
        return self.value

    class Meta:
        unique_together = ("question", "value")
        constraints = [
            models.UniqueConstraint(
                fields=["question", "value"], name="unique_question_option"
            )
        ]
        db_table = "option"


class UserForms(models.Model):
    user = models.ForeignKey(
        to=SystemUser, on_delete=models.CASCADE, related_name="user_form"
    )
    form = models.ForeignKey(
        to=Forms, on_delete=models.CASCADE, related_name="form_user"
    )

    def __str__(self):
        return self.user.email

    class Meta:
        unique_together = ("user", "form")
        db_table = "user_form"


class QuestionAttribute(models.Model):
    name = models.TextField(null=True, default=None)
    question = models.ForeignKey(
        to=Questions,
        on_delete=models.CASCADE,
        related_name="question_question_attribute",
    )
    attribute = models.IntegerField(choices=AttributeTypes.FieldStr.items())
    options = models.JSONField(default=None, null=True)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ("name", "question", "attribute", "options")
        db_table = "question_attribute"


class FormPublishedVersion(models.Model):
    """Immutable snapshot of a form's question structure at publish time.

    Created by POST /manage/forms/{id}/publish. Never modified after creation.
    FormData.published_version references this to enable rendering historical
    submissions against the exact schema used at collection time (FB-002A).
    """
    form = models.ForeignKey(
        Forms,
        on_delete=models.CASCADE,
        related_name="published_versions",
    )
    # Auto-incremented per form by the publish action (not a global counter).
    version = models.IntegerField()
    # Full JSON snapshot of question_group[] at publish time.
    # Includes all active (deleted_at__isnull=True) groups and questions.
    schema = models.JSONField()
    published_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(
        SystemUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="published_form_versions",
    )

    class Meta:
        unique_together = ("form", "version")
        ordering = ["form", "version"]
        db_table = "form_published_version"
