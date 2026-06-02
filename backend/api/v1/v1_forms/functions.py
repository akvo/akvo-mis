import re

from django.db import transaction

from api.v1.v1_forms.constants import FormStatus, FormTypes, QuestionTypes
from api.v1.v1_forms.models import (
    Forms,
    QuestionGroup,
    Questions,
    QuestionOptions,
)


def _type_str_to_int(type_str):
    return getattr(QuestionTypes, type_str.lower(), None)


def _form_type_str_to_int(type_str):
    return (
        FormTypes.registration
        if type_str == "registration"
        else FormTypes.monitoring
    )


def _generate_unique_name(base, existing_names):
    """Return a slug derived from base, appending _1 _2 … until unique."""
    slug = re.sub(r"[^a-z0-9_]", "_", base.lower()).strip("_") or "question"
    name = slug
    counter = 1
    while name in existing_names:
        name = f"{slug}_{counter}"
        counter += 1
    existing_names.add(name)
    return name


def _save_questions(group, questions_data, question_names):
    """Create/update questions for a group; protect answered questions."""
    from api.v1.v1_data.models import Answers

    incoming_q_ids = {q["id"] for q in questions_data if q.get("id")}

    questions_to_delete = group.question_group_question.exclude(
        id__in=incoming_q_ids
    )
    for q in questions_to_delete:
        if Answers.objects.filter(question=q).exists():
            raise ValueError(
                f"Can't delete question|Question {q.id} has answers"
            )
    questions_to_delete.delete()

    for q_data in questions_data:
        q_name = q_data.get("name") or _generate_unique_name(
            q_data.get("label", "question"), question_names
        )
        if q_data.get("name"):
            question_names.add(q_name)

        q_type = _type_str_to_int(q_data["type"])
        if q_type is None:
            qtype_str = q_data["type"]
            raise ValueError(
                f"Invalid question type|"
                f"Invalid question type: {qtype_str}"
            )

        q_defaults = dict(
            form=group.form,
            question_group=group,
            order=q_data["order"],
            label=q_data["label"],
            short_label=q_data.get("short_label"),
            name=q_name,
            type=q_type,
            meta=q_data.get("meta", False),
            required=q_data.get("required", True),
            rule=q_data.get("rule"),
            dependency=q_data.get("dependency"),
            dependency_rule=q_data.get("dependency_rule", "AND"),
            api=q_data.get("api"),
            extra=q_data.get("extra"),
            tooltip=q_data.get("tooltip"),
            fn=q_data.get("fn"),
            pre=q_data.get("pre"),
            display_only=q_data.get("display_only", False),
        )

        q_id = q_data.get("id")
        if q_id:
            Questions.objects.filter(id=q_id).update(
                **{k: v for k, v in q_defaults.items()
                   if k not in ("form", "question_group")}
            )
            question = Questions.objects.get(id=q_id)
        else:
            question = Questions.objects.create(**q_defaults)

        question.options.all().delete()
        for opt in q_data.get("option", []):
            QuestionOptions.objects.create(
                question=question,
                order=opt["order"],
                label=opt["label"],
                value=opt.get("value") or re.sub(
                    r"\s+", "_", str(opt["label"]).lower()
                ),
                other=opt.get("other", False),
                color=opt.get("color"),
            )


@transaction.atomic
def save_form(data, instance=None):
    """Create or fully replace a DRAFT form.

    Callers must not pass a PUBLISHED instance — use version_on_edit instead.
    """
    from api.v1.v1_data.models import Answers

    form_type = _form_type_str_to_int(data["type"])

    if instance is None:
        form = Forms.objects.create(
            name=data["name"],
            type=form_type,
            status=FormStatus.draft,
            approval_instructions=data.get("approval_instructions"),
            parent_id=data.get("parent"),
        )
    else:
        instance.name = data["name"]
        instance.type = form_type
        instance.approval_instructions = data.get("approval_instructions")
        instance.parent_id = data.get("parent")
        instance.save()
        form = instance

    incoming_group_ids = {
        g["id"] for g in data.get("question_group", []) if g.get("id")
    }
    groups_to_delete = form.form_question_group.exclude(
        id__in=incoming_group_ids
    )
    for grp in groups_to_delete:
        q_ids = list(grp.question_group_question.values_list("id", flat=True))
        if q_ids and Answers.objects.filter(question_id__in=q_ids).exists():
            raise ValueError(
                f"Can't delete question group|"
                f"Question in group {grp.id} has answers"
            )
    groups_to_delete.delete()

    group_names = set()
    question_names = set()

    for group_data in data.get("question_group", []):
        g_name = group_data.get("name") or _generate_unique_name(
            group_data.get("label", "group"), group_names
        )
        if group_data.get("name"):
            group_names.add(g_name)

        group_defaults = dict(
            form=form,
            name=g_name,
            label=group_data.get("label"),
            order=group_data.get("order"),
            repeatable=group_data.get("repeatable", False),
            repeat_text=group_data.get("repeat_text"),
        )
        g_id = group_data.get("id")
        if g_id:
            QuestionGroup.objects.filter(id=g_id).update(
                **{k: v for k, v in group_defaults.items() if k != "form"}
            )
            group = QuestionGroup.objects.get(id=g_id)
        else:
            group = QuestionGroup.objects.create(**group_defaults)

        _save_questions(group, group_data.get("question", []), question_names)

    return form


@transaction.atomic
def version_on_edit(original_form, data):
    """Create a new DRAFT version of a PUBLISHED form with changes applied."""
    new_form = Forms.objects.create(
        name=data.get("name", original_form.name),
        type=_form_type_str_to_int(data["type"]),
        status=FormStatus.draft,
        version=original_form.version + 1,
        previous_version=original_form,
        approval_instructions=data.get(
            "approval_instructions", original_form.approval_instructions
        ),
        parent_id=data.get("parent", original_form.parent_id),
    )
    return save_form(data, instance=new_form)


@transaction.atomic
def duplicate_form(original_form):
    """Create a DRAFT deep copy of any form."""
    new_form = Forms.objects.create(
        name=f"{original_form.name} (Copy)",
        type=original_form.type,
        status=FormStatus.draft,
        version=1,
        approval_instructions=original_form.approval_instructions,
        parent_id=original_form.parent_id,
    )
    for group in original_form.form_question_group.all().order_by("order"):
        new_group = QuestionGroup.objects.create(
            form=new_form,
            name=group.name,
            label=group.label,
            order=group.order,
            repeatable=group.repeatable,
            repeat_text=group.repeat_text,
        )
        for q in group.question_group_question.all().order_by("order"):
            new_q = Questions.objects.create(
                form=new_form,
                question_group=new_group,
                order=q.order,
                label=q.label,
                short_label=q.short_label,
                name=q.name,
                type=q.type,
                meta=q.meta,
                required=q.required,
                rule=q.rule,
                dependency=q.dependency,
                dependency_rule=q.dependency_rule,
                api=q.api,
                extra=q.extra,
                tooltip=q.tooltip,
                fn=q.fn,
                pre=q.pre,
                display_only=q.display_only,
            )
            for opt in q.options.all().order_by("order"):
                QuestionOptions.objects.create(
                    question=new_q,
                    order=opt.order,
                    label=opt.label,
                    value=opt.value,
                    other=opt.other,
                    color=opt.color,
                )
    return new_form


def validate_form_payload(data):
    """Return list of error strings, empty if valid."""
    errors = []
    if not data.get("name"):
        errors.append("name is required")
    if data.get("type") not in ("registration", "monitoring"):
        errors.append("type must be 'registration' or 'monitoring'")
    for gi, group in enumerate(data.get("question_group", [])):
        for qi, q in enumerate(group.get("question", [])):
            q_type = q.get("type", "")
            if getattr(QuestionTypes, q_type, None) is None:
                errors.append(
                    f"question_group[{gi}].question[{qi}].type: "
                    f"Invalid question type: {q_type!r}"
                )
    return errors
