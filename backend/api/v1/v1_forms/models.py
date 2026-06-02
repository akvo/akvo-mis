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


class Forms(models.Model):
    name = models.TextField()
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

    def __str__(self):
        return self.name

    class Meta:
        db_table = "form"


class QuestionGroup(models.Model):
    form = models.ForeignKey(
        to=Forms, on_delete=models.CASCADE, related_name="form_question_group"
    )
    name = models.CharField(max_length=255)
    label = models.TextField(null=True, default=None)
    order = models.BigIntegerField(null=True, default=None)
    repeatable = models.BooleanField(default=False)
    repeat_text = models.CharField(max_length=255, default=None, null=True)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ("form", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["form", "name"], name="unique_form_question_group"
            )
        ]
        db_table = "question_group"


class Questions(models.Model):
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
        unique_together = ("form", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["form", "name"], name="unique_form_question"
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
