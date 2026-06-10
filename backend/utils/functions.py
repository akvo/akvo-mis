import json
import os

from django.utils import timezone
from api.v1.v1_data.models import Answers, AnswerHistory
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_profile.models import Administration


def atomic_write(path: str, content: str) -> None:
    """Write content to path atomically via tmp+rename.

    Prevents concurrent readers from seeing a zero-byte file during the
    truncate/write window of `open(path, "w")`.
    """
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as f:
        f.write(content)
    os.replace(tmp, path)


def atomic_write_json(path: str, obj) -> None:
    atomic_write(path, json.dumps(obj, indent=2))


def update_date_time_format(date):
    if date:
        # date = timezone.datetime.strptime(date, "%Y-%m-%d").date()
        if not timezone.is_naive(date):
            return timezone.localtime(date).strftime("%Y-%m-%d %I:%M %p")
        return date.strftime("%Y-%m-%d %I:%M %p")
    return None


def get_answer_value(answer: Answers, webform: bool = False):
    if answer.question.type in [
        QuestionTypes.geo,
        QuestionTypes.option,
        QuestionTypes.multiple_option,
        QuestionTypes.tree,
    ]:
        return answer.options
    elif answer.question.type == QuestionTypes.number:
        return answer.value
    elif answer.question.type == QuestionTypes.cascade:
        extra_type = (answer.question.extra or {}).get("type")
        if extra_type == "entity" or answer.value is None:
            return answer.name
        if webform:
            adm = Administration.objects.filter(id=answer.value).first()
            if adm:
                return [
                    a.id
                    for a in adm.ancestors.exclude(parent__isnull=True).all()
                ] + [adm.id]
            return answer.value
        return int(float(answer.value))
    else:
        return answer.name


def get_answer_history(answer_history: AnswerHistory):
    value = None
    created = update_date_time_format(answer_history.created)
    created_by = answer_history.created_by.get_full_name()
    if answer_history.question.type in [
        QuestionTypes.geo,
        QuestionTypes.option,
        QuestionTypes.multiple_option,
        QuestionTypes.tree,
    ]:
        value = answer_history.options
    elif answer_history.question.type == QuestionTypes.number:
        value = answer_history.value
    elif answer_history.question.type == QuestionTypes.cascade:
        if answer_history.value is not None:
            value = int(float(answer_history.value))
        else:
            value = answer_history.name
    else:
        value = answer_history.name
    return {"value": value, "created": created, "created_by": created_by}
