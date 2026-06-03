import os
import uuid
import json
from django.db import models
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.models import (
    Administration,
    UserRole,
    DataAccessTypes,
)
from api.v1.v1_users.models import SystemUser
from utils.soft_deletes_model import SoftDeletes
from utils.draft_model import Draft, DraftSoftDeletesManager
from utils import storage


class FormData(SoftDeletes, Draft):
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    name = models.TextField()
    form = models.ForeignKey(
        to=Forms, on_delete=models.CASCADE, related_name="form_form_data"
    )
    administration = models.ForeignKey(
        to=Administration,
        on_delete=models.PROTECT,
        related_name="administration_form_data",
    )
    geo = models.JSONField(null=True, default=None)
    uuid = models.CharField(max_length=255, default=uuid.uuid4, null=True)
    created_by = models.ForeignKey(
        to=SystemUser,
        on_delete=models.CASCADE,
        related_name="form_data_created",
    )
    updated_by = models.ForeignKey(
        to=SystemUser,
        on_delete=models.CASCADE,
        related_name="form_data_updated",
        default=None,
        null=True,
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(default=None, null=True)
    duration = models.IntegerField(default=0)
    submitter = models.CharField(max_length=255, default=None, null=True)
    is_pending = models.BooleanField(default=False)
    # Snapshot active at submission time. Null for submissions collected
    # before schema versioning was deployed (backward compat).
    published_version = models.ForeignKey(
        "v1_forms.FormPublishedVersion",
        on_delete=models.SET_NULL,
        related_name="form_data",
        null=True,
        blank=True,
        default=None,
    )

    # Custom managers
    objects = DraftSoftDeletesManager()
    objects_deleted = DraftSoftDeletesManager(only_deleted=True)
    objects_draft = DraftSoftDeletesManager(only_draft=True)

    def __str__(self):
        return self.name

    @property
    def to_data_frame(self):
        administration = self.administration
        data = {
            "id": self.id,
            "datapoint_name": self.name,
            "administration": (
                administration.administration_column
                if administration
                else None
            ),
            "uuid": self.uuid,
            "geolocation": (
                f"{self.geo[0]}, {self.geo[1]}" if self.geo else None
            ),
            "created_by": self.created_by.get_full_name(),
            "updated_by": (
                self.updated_by.get_full_name() if self.updated_by else None
            ),
            "created_at": self.created.strftime("%B %d, %Y %I:%M %p"),
            "updated_at": (
                self.updated.strftime("%B %d, %Y %I:%M %p")
                if self.updated
                else None
            ),
        }
        for a in self.data_answer.order_by(
            "question__question_group_id", "question__order", "index"
        ).all():
            data.update(a.to_data_frame)
        return data

    @property
    def save_to_file(self):
        # If the data is a child of another form, do not save to file
        if self.form.parent:
            return None
        admin_id = self.administration_id
        if isinstance(admin_id, Administration):
            admin_id = admin_id.id
        data = {
            "id": self.id,
            "datapoint_name": self.name,
            "administration": admin_id,
            "uuid": str(self.uuid),
            "geolocation": self.geo,
        }
        answers = {}

        for a in self.data_answer.order_by(
            "question__question_group_id", "question__order"
        ).all():
            answers.update(a.to_key)
        data.update({"answers": answers})
        json_data = json.dumps(data)
        file_name = f"{str(self.uuid)}.json"
        # write to json file
        with open(file_name, "w") as f:
            f.write(json_data)
        storage.upload(file=file_name, folder="datapoints")
        # delete file
        os.remove(file_name)
        return data

    @property
    def loc(self):
        return self.administration.name

    @property
    def has_approval(self):
        # Use administration_id to avoid lazy loading issues with draft manager
        # Get the actual ID value, not the related object
        admin_id = self.administration_id
        if isinstance(admin_id, Administration):
            admin_id = admin_id.id
        administration = Administration.objects.select_related('parent').get(
            id=admin_id
        )
        administrations = [administration]
        if administration.parent:
            ancestors = administration.ancestors.all()
            administrations = list(ancestors) + [administration]
        # Check if there are any user roles with approve access
        # for this form and administration
        forms = [self.form]
        # if the form has a parent, add the parent form
        if self.form.parent:
            forms.append(self.form.parent)
        approvers = UserRole.objects.filter(
            administration__in=administrations,
            user__user_form__form__in=forms,
            role__role_role_access__data_access=DataAccessTypes.approve,
        ).exclude(
            user__password__exact=""
        ).exists()
        return approvers

    class Meta:
        db_table = "data"


class Answers(models.Model):
    data = models.ForeignKey(
        to=FormData, on_delete=models.CASCADE, related_name="data_answer"
    )
    question = models.ForeignKey(
        to=Questions, on_delete=models.CASCADE, related_name="question_answer"
    )
    name = models.TextField(null=True, default=None)
    value = models.FloatField(null=True, default=None)
    options = models.JSONField(default=None, null=True)
    created_by = models.ForeignKey(
        to=SystemUser, on_delete=models.CASCADE, related_name="answer_created"
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(default=None, null=True)
    # store the order of the repeatable question
    index = models.IntegerField(default=0)

    def __str__(self):
        return self.data.name

    @property
    def to_data_frame(self) -> dict:
        q = self.question
        qname = f"{self.question.name}"
        if q.type in [
            QuestionTypes.geo,
            QuestionTypes.option,
            QuestionTypes.multiple_option,
        ]:
            answer = "|".join(map(str, self.options))
        elif q.type in [
            QuestionTypes.input,
            QuestionTypes.text,
            QuestionTypes.image,
            QuestionTypes.date,
            QuestionTypes.autofield,
            QuestionTypes.cascade,
            QuestionTypes.attachment,
            QuestionTypes.signature,
        ]:
            answer = self.name
        elif q.type == QuestionTypes.administration:
            answer = Administration.objects.filter(pk=self.value).first()
            if answer:
                answer = answer.administration_column
        else:
            answer = self.value
        if self.index:
            return {f"{qname}_{self.index + 1}": answer}
        if not self.index and q.question_group.repeatable:
            return {f"{qname}_1": answer}
        return {qname: answer}

    @property
    def to_key(self) -> dict:
        q = self.question
        if q.type in [
            QuestionTypes.geo,
            QuestionTypes.option,
            QuestionTypes.multiple_option,
        ]:
            answer = self.options
        elif q.type in [
            QuestionTypes.input,
            QuestionTypes.text,
            QuestionTypes.image,
            QuestionTypes.date,
            QuestionTypes.autofield,
            QuestionTypes.cascade,
            QuestionTypes.attachment,
            QuestionTypes.signature,
        ]:
            answer = self.name
        else:
            answer = self.value
        if self.index:
            return {f"{q.id}-{self.index}": answer}
        return {q.id: answer}

    class Meta:
        db_table = "answer"


class AnswerHistory(models.Model):
    data = models.ForeignKey(
        to=FormData,
        on_delete=models.CASCADE,
        related_name="data_answer_history",
    )
    question = models.ForeignKey(
        to=Questions,
        on_delete=models.CASCADE,
        related_name="question_answer_history",
    )
    name = models.TextField(null=True, default=None)
    value = models.FloatField(null=True, default=None)
    options = models.JSONField(default=None, null=True)
    created_by = models.ForeignKey(
        to=SystemUser,
        on_delete=models.CASCADE,
        related_name="answer_history_created",
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(default=None, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "answer_history"
