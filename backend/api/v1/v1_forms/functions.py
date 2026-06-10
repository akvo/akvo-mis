import re

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from api.v1.v1_data.models import Answers
from api.v1.v1_forms.constants import FormStatus, FormTypes, QuestionTypes
from api.v1.v1_forms.models import (
    FormPublishedVersion,
    Forms,
    QuestionGroup,
    Questions,
    QuestionOptions,
)


def _parse_form_type(type_val):
    """Accept int (1/2) or string ('registration'/'monitoring')."""
    if isinstance(type_val, int):
        return type_val
    return (
        FormTypes.registration
        if type_val == "registration"
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


def _save_questions(
    group,
    questions_data,
    question_names,
    allow_delete=False,
    existing_questions=None,
    skip_option_delete=False,
):
    """Save questions for a group.

    existing_questions: pre-loaded {id: Questions} dict from in_bulk().
    skip_option_delete: when True, options were already batch-deleted by the
        caller — skip per-question delete to avoid a redundant query.
    """
    incoming_q_ids = {q["id"] for q in questions_data if q.get("id")}
    questions_to_remove = group.question_group_question.exclude(
        id__in=incoming_q_ids
    )
    if not allow_delete:
        for q in questions_to_remove:
            if Answers.objects.filter(question=q).exists():
                raise ValueError(
                    f"Can't delete question|Question {q.id} has answers"
                )
        questions_to_remove.hard_delete()
    else:
        questions_to_remove.soft_delete()

    for q_data in questions_data:
        q_name = q_data.get("name") or _generate_unique_name(
            q_data.get("label", "question"), question_names
        )
        if q_data.get("name"):
            question_names.add(q_name)

        q_type = getattr(QuestionTypes, q_data["type"].lower(), None)
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
            dependency_rule=q_data.get("dependency_rule") or "AND",
            api=q_data.get("api"),
            extra=q_data.get("extra"),
            tooltip=q_data.get("tooltip"),
            fn=q_data.get("fn") or None,
            pre=q_data.get("pre") or None,
            display_only=q_data.get("display_only") or False,
            variable_name=q_data.get("variable_name"),
            translations=q_data.get("translations"),
            hidden_string=q_data.get("hidden_string"),
            required_double_entry=q_data.get("required_double_entry") or False,
            disabled=q_data.get("disabled") or False,
            addon_before=q_data.get("addon_before"),
            addon_after=q_data.get("addon_after"),
            data_api_url=q_data.get("data_api_url"),
            center=q_data.get("center"),
            tree_option=q_data.get("tree_option"),
            limit=q_data.get("limit"),
            columns=q_data.get("columns"),
        )
        update_fields = {
            k: v for k, v in q_defaults.items()
            if k not in ("form", "question_group")
        }

        q_id = q_data.get("id")
        if q_id and existing_questions is not None:
            # Batch mode: use pre-loaded dict (NF-9).
            if q_id in existing_questions:
                q_obj = existing_questions[q_id]
                q_obj.deleted_at = None
                for k, v in update_fields.items():
                    setattr(q_obj, k, v)
                q_obj.save(
                    update_fields=["deleted_at"] + list(update_fields.keys())
                )
                question = q_obj
            else:
                question = Questions.objects.create(id=q_id, **q_defaults)
        elif q_id:
            qs = Questions.objects_with_deleted.filter(id=q_id)
            if qs.restore():
                qs.update(**update_fields)
                question = qs.get()
            else:
                question = Questions.objects.create(id=q_id, **q_defaults)
        else:
            question = Questions.objects.create(**q_defaults)

        if not skip_option_delete:
            question.options.all().delete()
        last_opt_order = 0
        for opt in q_data.get("option") or []:
            opt_label = opt.get("label", "")
            last_opt_order = opt.get("order") or (last_opt_order + 1)
            QuestionOptions.objects.create(
                question=question,
                order=last_opt_order,
                label=opt_label,
                value=opt.get("value") or re.sub(
                    r"\s+", "_", str(opt_label).lower()
                ),
                other=opt.get("other", False),
                color=opt.get("color"),
                translations=opt.get("translations"),
            )


@transaction.atomic
def save_form(data, instance=None, user=None):
    """Create or update a DRAFT form.

    On create (instance=None): name is required; type defaults to registration.
    On update: only fields present in data are changed; question_group is only
    processed when the key is explicitly included in the payload.
    allow_delete=True skips the answered-question guard, allowing deletion
    of questions/groups that have existing answers (answers cascade).
    user: sets created_by on create, updated_by + updated on update.
    """
    allow_delete = bool(data.get("allow_delete", False))
    type_val = data.get("type")

    if instance is None:
        parent_id = data.get("parent")
        if type_val is not None:
            resolved_type = _parse_form_type(type_val)
        elif parent_id:
            resolved_type = FormTypes.monitoring
        else:
            resolved_type = FormTypes.registration
        form_create_kwargs = dict(
            name=data["name"],
            type=resolved_type,
            status=FormStatus.draft,
            description=data.get("description"),
            approval_instructions=data.get("approval_instructions"),
            parent_id=parent_id,
            languages=data.get("languages"),
            default_language=data.get("default_language"),
            translations=data.get("translations"),
            created_by=user,
        )
        form_id = data.get("id")
        if form_id:
            form_create_kwargs["id"] = form_id
        form = Forms.objects.create(**form_create_kwargs)
    else:
        if "name" in data:
            instance.name = data["name"]
        if type_val is not None:
            instance.type = _parse_form_type(type_val)
        if "description" in data:
            instance.description = data["description"]
        if "approval_instructions" in data:
            instance.approval_instructions = data["approval_instructions"]
        if "parent" in data:
            instance.parent_id = data["parent"]
        if "languages" in data:
            instance.languages = data["languages"]
        if "default_language" in data:
            instance.default_language = data["default_language"]
        if "translations" in data:
            instance.translations = data["translations"]
        instance.updated_by = user
        instance.updated = timezone.now()
        instance.save()
        form = instance

    # Only touch question groups when explicitly included in the payload.
    if instance is None or "question_group" in data:
        incoming_group_ids = {
            g["id"] for g in data.get("question_group", []) if g.get("id")
        }
        groups_to_remove = form.form_question_group.exclude(
            id__in=incoming_group_ids
        )
        if not allow_delete:
            for grp in groups_to_remove:
                q_ids = list(
                    grp.question_group_question.values_list("id", flat=True)
                )
                if q_ids and Answers.objects.filter(
                    question_id__in=q_ids
                ).exists():
                    raise ValueError(
                        f"Can't delete question group|"
                        f"Question in group {grp.id} has answers"
                    )
            groups_to_remove.hard_delete()
        else:
            for grp in groups_to_remove:
                grp.question_group_question.soft_delete()
            groups_to_remove.soft_delete()

        # Batch-load all existing groups and questions (NF-9: one query each).
        all_group_ids = [
            g["id"] for g in data.get("question_group", []) if g.get("id")
        ]
        all_question_ids = [
            q["id"]
            for g in data.get("question_group", [])
            for q in g.get("question", [])
            if q.get("id")
        ]
        existing_groups = (
            QuestionGroup.objects_with_deleted.filter(
                id__in=all_group_ids
            ).in_bulk()
            if all_group_ids else {}
        )
        existing_questions = (
            Questions.objects_with_deleted.filter(
                id__in=all_question_ids
            ).in_bulk()
            if all_question_ids else {}
        )
        # Batch-delete options for all existing questions in payload (NF-9).
        existing_payload_q_ids = [
            qid for qid in all_question_ids if qid in existing_questions
        ]
        if existing_payload_q_ids:
            QuestionOptions.objects.filter(
                question_id__in=existing_payload_q_ids
            ).delete()

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
                translations=group_data.get("translations"),
            )
            grp_update = {
                k: v for k, v in group_defaults.items() if k != "form"
            }
            g_id = group_data.get("id")
            if g_id and g_id in existing_groups:
                g_obj = existing_groups[g_id]
                g_obj.deleted_at = None
                for k, v in grp_update.items():
                    setattr(g_obj, k, v)
                g_obj.save(
                    update_fields=["deleted_at"] + list(grp_update.keys())
                )
                group = g_obj
            elif g_id:
                group = QuestionGroup.objects.create(id=g_id, **group_defaults)
            else:
                group = QuestionGroup.objects.create(**group_defaults)

            _save_questions(
                group,
                group_data.get("question", []),
                question_names,
                allow_delete=allow_delete,
                existing_questions=existing_questions,
                skip_option_delete=True,
            )

    return form


@transaction.atomic
def duplicate_form(original_form, user=None):
    """Create a DRAFT deep copy of any form."""
    new_form = Forms.objects.create(
        name=f"{original_form.name} (Copy)",
        type=original_form.type,
        status=FormStatus.draft,
        version=1,
        description=original_form.description,
        approval_instructions=original_form.approval_instructions,
        parent_id=original_form.parent_id,
        languages=original_form.languages,
        default_language=original_form.default_language,
        translations=original_form.translations,
        created_by=user,
    )
    for group in original_form.form_question_group.all().order_by("order"):
        new_group = QuestionGroup.objects.create(
            form=new_form,
            name=group.name,
            label=group.label,
            order=group.order,
            repeatable=group.repeatable,
            repeat_text=group.repeat_text,
            translations=group.translations,
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
                variable_name=q.variable_name,
                translations=q.translations,
                hidden_string=q.hidden_string,
                required_double_entry=q.required_double_entry,
                disabled=q.disabled,
                addon_before=q.addon_before,
                addon_after=q.addon_after,
                data_api_url=q.data_api_url,
                center=q.center,
            )
            for opt in q.options.all().order_by("order"):
                QuestionOptions.objects.create(
                    question=new_q,
                    order=opt.order,
                    label=opt.label,
                    value=opt.value,
                    other=opt.other,
                    color=opt.color,
                    translations=opt.translations,
                )
    return new_form


@transaction.atomic
def restore_from_snapshot(form, pv):
    """Restore the live form structure to match a published version snapshot.

    Two passes:
    Pass 1 — soft-delete active rows absent from the snapshot.
    Pass 2 — restore rows present in the snapshot. Rows found in the DB are
             updated (cleared deleted_at + synced fields). Rows with IDs not
             in the DB (editor-generated timestamp IDs from PUT snapshots) are
             created fresh (D-5).

    Batch pre-loads all groups and questions in 2 queries before the loop,
    then bulk-deletes and bulk-creates options (NFR-5).
    """
    schema = pv.schema
    snapshot_group_ids = {
        g["id"] for g in schema.get("question_group", [])
    }
    snapshot_q_ids = {
        q["id"]
        for g in schema.get("question_group", [])
        for q in g.get("question", [])
    }

    # Pass 1: soft-delete active rows not in this snapshot.
    Questions.objects.filter(form=form).exclude(
        id__in=snapshot_q_ids
    ).soft_delete()
    form.form_question_group.exclude(
        id__in=snapshot_group_ids
    ).soft_delete()

    # Batch pre-load existing rows (NFR-5: 2 queries before the loop).
    group_db = {
        g.id: g
        for g in QuestionGroup.objects_with_deleted.filter(form=form)
    }
    question_db = {
        q.id: q
        for q in Questions.objects_with_deleted.filter(
            question_group__form=form
        )
    }

    # Bulk-delete all options for snapshot questions (NFR-5: 1 query).
    if snapshot_q_ids:
        QuestionOptions.objects.filter(
            question_id__in=snapshot_q_ids
        ).delete()

    new_options = []

    # Pass 2: restore snapshot rows, syncing all fields.
    for group_data in schema.get("question_group", []):
        g_id = group_data["id"]
        grp_fields = dict(
            deleted_at=None,
            name=group_data["name"],
            label=group_data.get("label"),
            order=group_data.get("order"),
            repeatable=group_data.get("repeatable", False),
            repeat_text=group_data.get("repeat_text"),
            translations=group_data.get("translations"),
        )
        if g_id in group_db:
            g_obj = group_db[g_id]
            for k, v in grp_fields.items():
                setattr(g_obj, k, v)
            g_obj.save(update_fields=list(grp_fields.keys()))
        else:
            g_obj = QuestionGroup.objects.create(form=form, **grp_fields)
            group_db[g_obj.id] = g_obj

        for q_data in group_data.get("question", []):
            q_id = q_data["id"]
            q_type = getattr(QuestionTypes, q_data["type"].lower(), None)
            if q_type is None:
                continue
            q_fields = dict(
                deleted_at=None,
                order=q_data["order"],
                label=q_data["label"],
                short_label=q_data.get("short_label"),
                name=q_data["name"],
                type=q_type,
                meta=q_data.get("meta", False),
                required=q_data.get("required", True),
                rule=q_data.get("rule"),
                dependency=q_data.get("dependency"),
                dependency_rule=q_data.get("dependency_rule") or "AND",
                api=q_data.get("api"),
                extra=q_data.get("extra"),
                tooltip=q_data.get("tooltip"),
                fn=q_data.get("fn"),
                pre=q_data.get("pre"),
                display_only=q_data.get("display_only") or False,
                variable_name=q_data.get("variable_name"),
                translations=q_data.get("translations"),
                hidden_string=q_data.get("hidden_string"),
                required_double_entry=(
                    q_data.get("required_double_entry") or False
                ),
                disabled=q_data.get("disabled") or False,
                addon_before=q_data.get("addon_before"),
                addon_after=q_data.get("addon_after"),
                data_api_url=q_data.get("data_api_url"),
                center=q_data.get("center"),
            )
            if q_id in question_db:
                q_obj = question_db[q_id]
                for k, v in q_fields.items():
                    setattr(q_obj, k, v)
                q_obj.save(update_fields=list(q_fields.keys()))
                live_q_id = q_id
            else:
                # Editor-generated ID not in DB: create fresh row (D-5).
                q_obj = Questions.objects.create(
                    form=form, question_group=g_obj, **q_fields
                )
                question_db[q_obj.id] = q_obj
                live_q_id = q_obj.id

            for opt in q_data.get("option", []):
                new_options.append(QuestionOptions(
                    question_id=live_q_id,
                    order=opt["order"],
                    label=opt["label"],
                    value=opt.get("value") or re.sub(
                        r"\s+", "_", str(opt["label"]).lower()
                    ),
                    other=opt.get("other", False),
                    color=opt.get("color"),
                    translations=opt.get("translations"),
                ))

    if new_options:
        QuestionOptions.objects.bulk_create(new_options)

    form.name = schema.get("name", form.name)
    form.description = schema.get("description")
    form.approval_instructions = schema.get("approval_instructions")
    form.languages = schema.get("languages")
    form.default_language = schema.get("default_language")
    form.translations = schema.get("translations")
    form.active_version = pv
    form.version = pv.version
    form.save(update_fields=[
        "name",
        "description",
        "approval_instructions",
        "languages",
        "default_language",
        "translations",
        "active_version",
        "version",
    ])


def validate_form_payload(data, partial=False):
    """Return list of error strings, empty if valid.

    partial=True: name and type are optional (used for PUT updates).
    """
    errors = []
    if not partial and not data.get("name"):
        errors.append("name is required")

    type_val = data.get("type")
    if type_val is not None:
        valid_ints = {FormTypes.registration, FormTypes.monitoring}
        valid_strs = {"registration", "monitoring"}
        if type_val not in valid_ints and type_val not in valid_strs:
            errors.append("type must be 1 (registration) or 2 (monitoring)")

    for gi, group in enumerate(data.get("question_group", [])):
        for qi, q in enumerate(group.get("question", [])):
            q_type = q.get("type", "")
            if getattr(QuestionTypes, q_type, None) is None:
                errors.append(
                    f"question_group[{gi}].question[{qi}].type: "
                    f"Invalid question type: {q_type!r}"
                )
    return errors


def _build_schema_snapshot(form):
    """Build the immutable schema JSON stored in FormPublishedVersion.schema.

    Uses prefetch_related to load groups → questions → options in 3 queries
    regardless of form size (NF-7).
    """
    groups_qs = (
        form.form_question_group
        .filter(deleted_at__isnull=True)
        .prefetch_related(
            Prefetch(
                "question_group_question",
                queryset=Questions.objects.filter(
                    deleted_at__isnull=True
                ).prefetch_related("options").order_by("order"),
            )
        )
        .order_by("order")
    )
    groups = []
    for group in groups_qs:
        questions = []
        for q in group.question_group_question.all():
            questions.append({
                "id": q.id,
                "order": q.order,
                "name": q.name,
                "label": q.label,
                "short_label": q.short_label,
                "type": QuestionTypes.FieldStr.get(q.type),
                "meta": q.meta,
                "required": q.required,
                "rule": q.rule,
                "dependency": q.dependency,
                "dependency_rule": q.dependency_rule,
                "api": q.api,
                "extra": q.extra,
                "tooltip": q.tooltip,
                "fn": q.fn,
                "pre": q.pre,
                "display_only": q.display_only,
                "variable_name": q.variable_name,
                "translations": q.translations,
                "hidden_string": q.hidden_string,
                "required_double_entry": q.required_double_entry,
                "disabled": q.disabled,
                "addon_before": q.addon_before,
                "addon_after": q.addon_after,
                "data_api_url": q.data_api_url,
                "center": q.center,
                "tree_option": q.tree_option,
                "limit": q.limit,
                "columns": q.columns,
                "option": [
                    {
                        "order": opt.order,
                        "label": opt.label,
                        "value": opt.value,
                        "other": opt.other,
                        "color": opt.color,
                        "translations": opt.translations,
                    }
                    for opt in q.options.all()
                ],
            })
        groups.append({
            "id": group.id,
            "name": group.name,
            "label": group.label,
            "order": group.order,
            "repeatable": group.repeatable,
            "repeat_text": group.repeat_text,
            "translations": group.translations,
            "question": questions,
        })
    return {
        "name": form.name,
        "description": form.description,
        "approval_instructions": form.approval_instructions,
        "languages": form.languages,
        "default_language": form.default_language,
        "translations": form.translations,
        "question_group": groups,
    }


@transaction.atomic
def store_version_snapshot(form, data, user):
    """Store a normalized PUT payload as a FormPublishedVersion snapshot.

    Called by update() when the form is published. Does NOT modify any live
    Forms, QuestionGroup, Questions, or QuestionOptions rows. active_version
    and Forms.version remain unchanged.

    Missing top-level fields inherit from the current active version's schema
    so the snapshot is always complete.
    """
    last = form.published_versions.order_by("-version").first()
    next_version = (last.version + 1) if last else 1

    active_schema = (
        form.active_version.schema if form.active_version else {}
    )
    schema = {
        "version": next_version,
        "name": (
            data["name"] if "name" in data
            else active_schema.get("name", form.name)
        ),
        "description": (
            data["description"] if "description" in data
            else active_schema.get("description", form.description)
        ),
        "approval_instructions": (
            data["approval_instructions"]
            if "approval_instructions" in data
            else active_schema.get(
                "approval_instructions", form.approval_instructions
            )
        ),
        "languages": (
            data["languages"] if "languages" in data
            else active_schema.get("languages", form.languages)
        ),
        "default_language": (
            data["default_language"] if "default_language" in data
            else active_schema.get("default_language", form.default_language)
        ),
        "translations": (
            data["translations"] if "translations" in data
            else active_schema.get("translations", form.translations)
        ),
        "question_group": (
            data["question_group"]
            if "question_group" in data
            else active_schema.get("question_group", [])
        ),
    }

    pv = FormPublishedVersion.objects.create(
        form=form,
        version=next_version,
        schema=schema,
        published_by=user,
    )
    form.updated_by = user
    form.updated = timezone.now()
    form.save(update_fields=["updated_by", "updated"])
    return pv


@transaction.atomic
def create_published_version(form, user, activate=False):
    """Create a FormPublishedVersion snapshot from the current live DB rows.

    activate=True (explicit first publish): also sets form.active_version,
    form.version, form.status=published, and form.published_at.

    activate=False is kept for backward compatibility but is no longer called
    by update() — PUT on a published form uses store_version_snapshot instead.

    published_at is written once (first-ever publish). Guard uses
    form.published_at is None — not form.status — so that re-publishing after
    a disable does not overwrite published_at.
    """
    last = form.published_versions.order_by("-version").first()
    next_version = (last.version + 1) if last else 1
    schema = _build_schema_snapshot(form)
    schema["version"] = next_version

    pv = FormPublishedVersion.objects.create(
        form=form,
        version=next_version,
        schema=schema,
        published_by=user,
    )

    is_first_publish = form.published_at is None
    if is_first_publish or activate:
        form.active_version = pv
        form.version = next_version
        update_fields = ["active_version", "version"]
        if is_first_publish:
            form.status = FormStatus.published
            form.published_at = pv.published_at
            update_fields.extend(["status", "published_at"])
        elif activate and form.status != FormStatus.published:
            # Re-publish after unpublish: restore visibility without touching
            # published_at (already set from the first-ever publish).
            form.status = FormStatus.published
            update_fields.append("status")
        form.save(update_fields=update_fields)

    return pv
