import re
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Prefetch
from django.utils import timezone

from api.v1.v1_data.models import Answers
from api.v1.v1_forms.constants import (
    FORM_IMPORT_SUPPORTED_VERSIONS,
    FormStatus,
    FormTypes,
    QuestionTypes,
    _CAMEL_FIELDS,
    _SNAKE_TO_CAMEL,
    _TYPE_STR_TO_INT,
    _TYPE_INT_TO_STR,
)
from api.v1.v1_forms.models import (
    FormPublishedVersion,
    Forms,
    QuestionGroup,
    Questions,
    QuestionOptions,
)
from api.v1.v1_profile.models import Entity


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

    # Sync PK sequences: editor inserts use JS timestamp IDs directly,
    # leaving the PostgreSQL sequences far behind. Without this, auto-
    # created rows (editor IDs absent from the DB) collide with existing
    # small-integer PKs from seeded data.
    with connection.cursor() as cur:
        cur.execute(
            "SELECT setval(pg_get_serial_sequence('question_group', 'id'),"
            " COALESCE((SELECT MAX(id) FROM question_group), 1))"
        )
        cur.execute(
            "SELECT setval(pg_get_serial_sequence('question', 'id'),"
            " COALESCE((SELECT MAX(id) FROM question), 1))"
        )

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


# ---------------------------------------------------------------------------
# FB-007: Form Import/Export (normalize / validate / export / import)
# ---------------------------------------------------------------------------

def normalize_form_definition(raw):
    """Return canonical snake_case structure accepted by validate/import.

    Accepts:
      (a) FB-007 export — metadata envelope + editor camelCase keys
      (b) Bare editor/akvo-react-form payload — no metadata
      (c) Legacy seeder format — form/question_groups/questions keys

    Extra top-level keys on the return value:
      _meta       : metadata dict (None if absent)
      form_id     : int or None
      parent_hint : {id, name} | None
    """
    meta = raw.get("metadata")
    name = raw.get("name") or raw.get("form")

    raw_type = raw.get("type")
    if isinstance(raw_type, str):
        type_val = (
            FormTypes.registration
            if raw_type.lower() == "registration"
            else FormTypes.monitoring
        )
    else:
        type_val = raw_type

    parent_hint = raw.get("parent")
    if parent_hint and not isinstance(parent_hint, dict):
        parent_hint = None
    if parent_hint is None and raw.get("parent_id"):
        # Legacy seeder format carries a bare parent_id
        parent_hint = {"id": raw["parent_id"], "name": None}

    groups_raw = raw.get("question_group") or raw.get("question_groups") or []
    groups = []
    for g in groups_raw:
        questions_raw = g.get("question") or g.get("questions") or []
        questions = [_normalize_import_question(q) for q in questions_raw]
        groups.append({
            "id": g.get("id"),
            "name": g.get("name"),
            "label": g.get("label"),
            "description": g.get("description"),
            "order": g.get("order"),
            "repeatable": g.get("repeatable", False),
            "repeat_text": g.get("repeatText") or g.get("repeat_text"),
            "translations": g.get("translations"),
            "leading_question": (
                g.get("leading_question") or g.get("leadingQuestion")
            ),
            "question": questions,
        })

    return {
        "_meta": meta,
        "form_id": raw.get("id"),
        "name": name,
        "description": raw.get("description"),
        "type": type_val,
        "version": raw.get("version"),
        "parent_hint": parent_hint,
        "languages": raw.get("languages"),
        "default_language": (
            raw.get("defaultLanguage") or raw.get("default_language")
        ),
        "translations": raw.get("translations"),
        "approval_instructions": raw.get("approval_instructions"),
        "question_group": groups,
    }


def _normalize_import_question(q):
    """Return a single question dict in canonical snake_case form."""
    result = {}
    for key, val in q.items():
        result[_CAMEL_FIELDS.get(key, key)] = val

    q_type = result.get("type")
    if isinstance(q_type, int):
        result["type"] = _TYPE_INT_TO_STR.get(q_type, q_type)
    elif isinstance(q_type, str):
        result["type"] = q_type.lower()

    if "questionGroupId" in result:
        result["question_group_id"] = result.pop("questionGroupId")

    if "options" in result and "option" not in result:
        result["option"] = result.pop("options")

    return result


def validate_form_definition(norm, check_entities=True):
    """Return [{code, path, message, level}] — empty list means valid.

    level = "error"   -> blocking; import must not proceed
    level = "warning" -> non-blocking; import proceeds but user is informed
    """
    issues = []

    meta = norm.get("_meta")
    if meta:
        fv = meta.get("format_version")
        if fv is not None and fv not in FORM_IMPORT_SUPPORTED_VERSIONS:
            issues.append({
                "code": "unsupported_format_version",
                "path": "metadata.format_version",
                "message": (
                    f"format_version {fv!r} is not supported; "
                    f"supported: {sorted(FORM_IMPORT_SUPPORTED_VERSIONS)}"
                ),
                "level": "error",
            })
            return issues

    if not norm.get("name"):
        issues.append({
            "code": "missing_name",
            "path": "name",
            "message": "name is required",
            "level": "error",
        })

    type_val = norm.get("type")
    if type_val not in (FormTypes.registration, FormTypes.monitoring):
        issues.append({
            "code": "invalid_type",
            "path": "type",
            "message": (
                f"type must be 1 (registration) or 2 (monitoring), "
                f"got {type_val!r}"
            ),
            "level": "error",
        })

    group_ids = {}
    question_ids = {}
    question_names = set()
    group_names = set()

    for gi, g in enumerate(norm.get("question_group", [])):
        g_path = f"question_group[{gi}]"
        g_id = g.get("id")
        g_name = g.get("name")

        if g_id is not None:
            if g_id in group_ids:
                issues.append({
                    "code": "duplicate_group_id",
                    "path": f"{g_path}.id",
                    "message": (
                        f"id {g_id} already used in {group_ids[g_id]}"
                    ),
                    "level": "error",
                })
            else:
                group_ids[g_id] = g_path

        if g_name:
            if g_name in group_names:
                issues.append({
                    "code": "duplicate_group_name",
                    "path": f"{g_path}.name",
                    "message": f"group name '{g_name}' used more than once",
                    "level": "error",
                })
            else:
                group_names.add(g_name)

        for qi, q in enumerate(g.get("question", [])):
            q_path = f"{g_path}.question[{qi}]"
            q_id = q.get("id")
            q_name = q.get("name")

            if q_id is not None:
                if q_id in question_ids:
                    issues.append({
                        "code": "duplicate_question_id",
                        "path": f"{q_path}.id",
                        "message": (
                            f"id {q_id} already used in {question_ids[q_id]}"
                        ),
                        "level": "error",
                    })
                else:
                    question_ids[q_id] = q_path

            if q_name:
                question_names.add(q_name)

    for gi, g in enumerate(norm.get("question_group", [])):
        g_path = f"question_group[{gi}]"

        lq = g.get("leading_question")
        if lq is not None and lq not in question_ids:
            issues.append({
                "code": "dangling_leading_question",
                "path": f"{g_path}.leading_question",
                "message": f"leading_question id {lq} not found in file",
                "level": "error",
            })

        for qi, q in enumerate(g.get("question", [])):
            q_path = f"{g_path}.question[{qi}]"
            q_type = q.get("type")

            if q_type not in _TYPE_STR_TO_INT:
                issues.append({
                    "code": "invalid_question_type",
                    "path": f"{q_path}.type",
                    "message": f"unknown question type {q_type!r}",
                    "level": "error",
                })

            qgid = q.get("question_group_id")
            if qgid is not None and qgid not in group_ids:
                issues.append({
                    "code": "dangling_question_group_id",
                    "path": f"{q_path}.question_group_id",
                    "message": f"questionGroupId {qgid} not found in file",
                    "level": "error",
                })

            for di, dep in enumerate(q.get("dependency") or []):
                dep_id = dep.get("id")
                if dep_id is not None and dep_id not in question_ids:
                    issues.append({
                        "code": "dangling_dependency_id",
                        "path": f"{q_path}.dependency[{di}].id",
                        "message": f"dependency id {dep_id} not found in file",
                        "level": "error",
                    })

            extra = q.get("extra") or {}
            if not isinstance(extra, dict):
                # Legacy seeder files use extra as a list of placement hints
                extra = {}
            parent_id_ref = extra.get("parentId")
            if parent_id_ref is not None and parent_id_ref not in question_ids:
                issues.append({
                    "code": "dangling_extra_parent_id",
                    "path": f"{q_path}.extra.parentId",
                    "message": (
                        f"extra.parentId {parent_id_ref} not found in file"
                    ),
                    "level": "error",
                })

            fn = q.get("fn") or {}
            if not isinstance(fn, dict):
                fn = {}
            fn_string = fn.get("fnString") or ""
            for ref_name in re.findall(r"#(\w+)#", fn_string):
                if ref_name not in question_names:
                    issues.append({
                        "code": "dangling_fn_ref",
                        "path": f"{q_path}.fn.fnString",
                        "message": (
                            f"#{ref_name}# references unknown question name "
                            f"'{ref_name}'"
                        ),
                        "level": "error",
                    })

            api = q.get("api") or {}
            if not isinstance(api, dict):
                api = {}
            endpoint = api.get("endpoint") or ""
            if endpoint:
                web_domain = getattr(settings, "WEBDOMAIN", "")
                if web_domain and web_domain.rstrip("/") not in endpoint:
                    issues.append({
                        "code": "foreign_api_endpoint",
                        "path": f"{q_path}.api.endpoint",
                        "message": (
                            f"api.endpoint '{endpoint}' points to a "
                            "different environment; fix in the form "
                            "editor before publishing"
                        ),
                        "level": "warning",
                    })

            # Entity cascade uses extra.type="entity" and its own rendering
            # path; it does not need api.list or api.initial.  All other
            # cascade questions with an endpoint do require both fields.
            if (
                q_type == "cascade"
                and endpoint
                and extra.get("type") != "entity"
            ):
                missing = [
                    f for f in ("list", "initial")
                    if not api.get(f)
                ]
                if missing:
                    issues.append({
                        "code": "incomplete_cascade_api",
                        "path": f"{q_path}.api",
                        "message": (
                            f"cascade question '{q.get('name')}' api "
                            "config is missing required field(s): "
                            f"{', '.join(missing)}; akvo-react-form "
                            "requires api.list and api.initial to "
                            "populate the cascade dropdown"
                        ),
                        "level": "error",
                    })

            if check_entities and q_type == "cascade":
                entity_name = extra.get("name")
                if extra.get("type") == "entity" and entity_name:
                    if not Entity.objects.filter(name=entity_name).exists():
                        issues.append({
                            "code": "unknown_entity_type",
                            "path": f"{q_path}.extra.name",
                            "message": (
                                f"entity '{entity_name}' not found in this "
                                "environment; seed entity data "
                                "before publishing"
                            ),
                            "level": "warning",
                        })

    return issues


def export_form_definition(form):
    """Return the FB-007 JSON export envelope for the given form.

    Builds from live rows via the same 3-query strategy as
    _build_schema_snapshot, then applies the editor key convention
    (snake -> camelCase) and wraps in the metadata envelope.
    """
    snapshot = _build_schema_snapshot(form)

    groups = []
    for g in snapshot.get("question_group", []):
        questions = []
        for q in g.get("question", []):
            questions.append(_export_question_to_editor_keys(q, g["id"]))
        groups.append({
            "id": g["id"],
            "name": g["name"],
            "label": g.get("label"),
            "description": g.get("description"),
            "order": g.get("order"),
            "repeatable": g.get("repeatable", False),
            "repeatText": g.get("repeat_text"),
            "translations": g.get("translations"),
            "question": questions,
        })

    parent_hint = None
    if form.parent_id:
        try:
            parent_hint = {"id": form.parent.id, "name": form.parent.name}
        except Exception:
            pass

    return {
        "metadata": {
            "format_version": 1,
            "exported_at": datetime.now(tz=dt_timezone.utc).isoformat(
                timespec="seconds"
            ),
            "source": getattr(settings, "WEBDOMAIN", ""),
        },
        "id": form.id,
        "name": snapshot["name"],
        "description": snapshot.get("description"),
        "type": form.type,
        "version": form.version,
        "parent": parent_hint,
        "languages": snapshot.get("languages"),
        "defaultLanguage": snapshot.get("default_language"),
        "translations": snapshot.get("translations"),
        "approval_instructions": snapshot.get("approval_instructions"),
        "question_group": groups,
    }


def _export_question_to_editor_keys(q, group_id):
    """Translate a snapshot question dict to editor/akvo-react-form keys."""
    result = {}
    for key, val in q.items():
        result[_SNAKE_TO_CAMEL.get(key, key)] = val
    result["questionGroupId"] = group_id
    if "type" in result and isinstance(result["type"], str):
        result["type"] = result["type"].lower()
    return result


@transaction.atomic
def import_form_definition(
    norm,
    user,
    *,
    mode,
    parent_id=None,
    require_parent=True,
    claim_foreign_questions=False,
):
    """Create or update a form from a normalized definition.

    Parameters
    ----------
    norm      : output of normalize_form_definition()
    user      : SystemUser performing the import
    mode      : "create_or_update" | "create_copy"
    parent_id : int | None — overrides/satisfies parent hint for monitoring
    require_parent : bool — when False, an unresolvable parent on a
        monitoring form is tolerated instead of raising (seeder/CLI only;
        the API always requires a resolvable parent — FR-10)
    claim_foreign_questions : bool — when True, the update path matches
        file question ids globally and reassigns rows attached to another
        form (cross-form question moves, seeder/CLI only). The API must
        keep this False so an import can never steal questions from an
        unrelated form.

    Returns
    -------
    (form, action) where action in {"created", "updated", "copied"}
    """
    file_form_id = norm.get("form_id")
    form_type = norm.get("type", FormTypes.registration)

    parent_form = _resolve_import_parent(
        norm, parent_id, form_type, required=require_parent
    )

    existing_form = None
    if mode != "create_copy" and file_form_id is not None:
        existing_form = Forms.objects.filter(id=file_form_id).first()

    if existing_form is not None:
        _apply_import_update_path(
            existing_form, norm, user,
            claim_foreign_questions=claim_foreign_questions,
        )
        return existing_form, "updated"
    else:
        new_form = _apply_import_create_path(
            norm, user, parent_form,
            force_new_id=(mode == "create_copy"),
        )
        action = "copied" if mode == "create_copy" else "created"
        return new_form, action


def _resolve_import_parent(norm, override_parent_id, form_type, required=True):
    """Return the parent Forms instance, or None if not required."""
    if form_type != FormTypes.monitoring:
        return None

    if override_parent_id:
        try:
            return Forms.objects.get(id=override_parent_id)
        except Forms.DoesNotExist:
            raise ValueError(
                f"parent_id {override_parent_id} not found"
            )

    hint = norm.get("parent_hint")
    if hint and hint.get("id"):
        parent = Forms.objects.filter(id=hint["id"]).first()
        if parent:
            return parent

    if not required:
        return None

    raise ValueError(
        "Monitoring form requires a parent registration form; "
        "provide parent_id or ensure the parent exists in this environment"
    )


def _sync_import_pk_sequences():
    """Sync PK sequences for form, question_group, question tables.

    Without this, auto-created rows with auto-increment IDs collide with
    existing large editor-generated timestamp IDs already in the DB.
    """
    with connection.cursor() as cur:
        for table in ("form", "question_group", "question"):
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'),"
                f" COALESCE((SELECT MAX(id) FROM {table}), 1))"
            )


def _build_import_id_remap(norm):
    """Return (group_id_remap, question_id_remap) for ids already in the DB."""
    file_group_ids = [
        g["id"] for g in norm.get("question_group", [])
        if g.get("id") is not None
    ]
    file_q_ids = [
        q["id"]
        for g in norm.get("question_group", [])
        for q in g.get("question", [])
        if q.get("id") is not None
    ]

    taken_group_ids = set(
        QuestionGroup.objects_with_deleted.filter(
            id__in=file_group_ids
        ).values_list("id", flat=True)
    )
    taken_q_ids = set(
        Questions.objects_with_deleted.filter(
            id__in=file_q_ids
        ).values_list("id", flat=True)
    )

    group_remap = {
        gid: None for gid in file_group_ids if gid in taken_group_ids
    }
    q_remap = {
        qid: None for qid in file_q_ids if qid in taken_q_ids
    }
    return group_remap, q_remap


def _apply_import_create_path(norm, user, parent_form, force_new_id):
    """Create a new draft form, preserving file IDs when free."""
    file_form_id = norm.get("form_id")
    form_type = norm.get("type", FormTypes.registration)

    if not force_new_id and file_form_id is not None:
        form_id_taken = Forms.objects_with_deleted.filter(
            id=file_form_id
        ).exists()
        use_file_form_id = not form_id_taken
    else:
        use_file_form_id = False

    group_remap, q_remap = _build_import_id_remap(norm)
    _sync_import_pk_sequences()

    create_kwargs = dict(
        name=norm["name"],
        description=norm.get("description"),
        type=form_type,
        status=FormStatus.draft,
        parent=parent_form,
        languages=norm.get("languages"),
        default_language=norm.get("default_language"),
        translations=norm.get("translations"),
        approval_instructions=norm.get("approval_instructions"),
        created_by=user,
        updated_by=user,
    )
    if use_file_form_id:
        create_kwargs["id"] = file_form_id

    form = Forms.objects.create(**create_kwargs)

    if use_file_form_id:
        _sync_import_pk_sequences()

    final_q_id_map = {}
    new_options = []

    for g in norm.get("question_group", []):
        g_id = g.get("id")
        use_g_id = (
            not force_new_id
            and g_id is not None
            and g_id not in group_remap
        )

        grp_kwargs = dict(
            form=form,
            name=g["name"],
            label=g.get("label"),
            order=g.get("order"),
            repeatable=g.get("repeatable", False),
            repeat_text=g.get("repeat_text"),
            translations=g.get("translations"),
        )
        if use_g_id:
            grp_kwargs["id"] = g_id

        grp = QuestionGroup.objects.create(**grp_kwargs)
        if g_id is not None:
            group_remap[g_id] = grp.id

        for q in g.get("question", []):
            q_id = q.get("id")
            use_q_id = (
                not force_new_id
                and q_id is not None
                and q_id not in q_remap
            )

            q_type = _TYPE_STR_TO_INT.get(q.get("type") or "")
            if q_type is None:
                continue

            q_kwargs = dict(
                form=form,
                question_group=grp,
                order=q.get("order"),
                name=q["name"],
                label=q.get("label", q["name"]),
                short_label=q.get("short_label"),
                type=q_type,
                meta=q.get("meta", False),
                required=q.get("required", True),
                rule=q.get("rule"),
                dependency=q.get("dependency"),
                dependency_rule=q.get("dependency_rule") or "AND",
                api=q.get("api"),
                extra=q.get("extra"),
                tooltip=q.get("tooltip"),
                fn=q.get("fn"),
                pre=q.get("pre"),
                display_only=q.get("display_only") or False,
                variable_name=q.get("variable_name"),
                translations=q.get("translations"),
                hidden_string=q.get("hidden_string"),
                required_double_entry=q.get("required_double_entry") or False,
                disabled=q.get("disabled") or False,
                addon_before=q.get("addon_before"),
                addon_after=q.get("addon_after"),
                data_api_url=q.get("data_api_url"),
                center=q.get("center"),
                tree_option=q.get("tree_option"),
                limit=q.get("limit"),
                columns=q.get("columns"),
            )
            if use_q_id:
                q_kwargs["id"] = q_id

            q_obj = Questions.objects.create(**q_kwargs)
            if q_id is not None:
                final_q_id_map[q_id] = q_obj.id

            for opt in q.get("option") or []:
                new_options.append(QuestionOptions(
                    question_id=q_obj.id,
                    order=opt.get("order", 1),
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

    _fixup_import_dependency_refs(form, final_q_id_map)
    return form


def _fixup_import_dependency_refs(form, final_q_id_map):
    """Update dependency[].id refs for questions whose ids were remapped."""
    changed = {old: new for old, new in final_q_id_map.items() if old != new}
    if not changed:
        return

    for q_obj in Questions.objects.filter(form=form):
        deps = q_obj.dependency
        if not deps:
            continue
        updated = False
        for dep in deps:
            old_id = dep.get("id")
            if old_id in changed:
                dep["id"] = changed[old_id]
                updated = True
        if updated:
            q_obj.save(update_fields=["dependency"])


def _apply_import_update_path(form, norm, user, claim_foreign_questions=False):
    """Update an existing form's live structure to match the normalized def.

    Semantics identical to restore_from_snapshot:
    - Pass 1: soft-delete groups/questions absent from the file.
    - Pass 2: upsert by exported id; create new rows for unknown ids.
    - Options are recreated wholesale.
    - status and active_version are NOT touched (D-6).

    With claim_foreign_questions=True (seeder/CLI only), file question ids
    are matched globally and rows currently attached to another form are
    reassigned to this form (cross-form question moves keep their PK so
    answers stay linked).
    """
    snapshot_group_ids = {
        g["id"]
        for g in norm.get("question_group", [])
        if g.get("id") is not None
    }
    snapshot_q_ids = {
        q["id"]
        for g in norm.get("question_group", [])
        for q in g.get("question", [])
        if q.get("id") is not None
    }

    Questions.objects.filter(form=form).exclude(
        id__in=snapshot_q_ids
    ).soft_delete()
    form.form_question_group.exclude(
        id__in=snapshot_group_ids
    ).soft_delete()

    group_db = {
        g.id: g
        for g in QuestionGroup.objects_with_deleted.filter(form=form)
    }
    if claim_foreign_questions:
        question_db = {
            q.id: q
            for q in Questions.objects_with_deleted.filter(
                id__in=snapshot_q_ids
            )
        }
    else:
        question_db = {
            q.id: q
            for q in Questions.objects_with_deleted.filter(
                question_group__form=form
            )
        }

    if snapshot_q_ids:
        QuestionOptions.objects.filter(
            question_id__in=snapshot_q_ids
        ).delete()

    _sync_import_pk_sequences()

    new_options = []

    for g in norm.get("question_group", []):
        g_id = g.get("id")
        grp_fields = dict(
            deleted_at=None,
            name=g["name"],
            label=g.get("label"),
            order=g.get("order"),
            repeatable=g.get("repeatable", False),
            repeat_text=g.get("repeat_text"),
            translations=g.get("translations"),
        )
        if g_id is not None and g_id in group_db:
            g_obj = group_db[g_id]
            for k, v in grp_fields.items():
                setattr(g_obj, k, v)
            g_obj.save(update_fields=list(grp_fields.keys()))
        else:
            # Preserve the exported id when free (FR-7/R-2) so later
            # re-imports keep matching this group by id
            if g_id is not None and not QuestionGroup.objects_with_deleted\
                    .filter(id=g_id).exists():
                grp_fields["id"] = g_id
            g_obj = QuestionGroup.objects.create(form=form, **grp_fields)
            if g_id is not None:
                group_db[g_id] = g_obj

        for q in g.get("question", []):
            q_id = q.get("id")
            q_type = _TYPE_STR_TO_INT.get(q.get("type") or "")
            if q_type is None:
                continue
            q_fields = dict(
                deleted_at=None,
                order=q.get("order"),
                label=q.get("label", q.get("name", "")),
                short_label=q.get("short_label"),
                name=q["name"],
                type=q_type,
                meta=q.get("meta", False),
                required=q.get("required", True),
                rule=q.get("rule"),
                dependency=q.get("dependency"),
                dependency_rule=q.get("dependency_rule") or "AND",
                api=q.get("api"),
                extra=q.get("extra"),
                tooltip=q.get("tooltip"),
                fn=q.get("fn"),
                pre=q.get("pre"),
                display_only=q.get("display_only") or False,
                variable_name=q.get("variable_name"),
                translations=q.get("translations"),
                hidden_string=q.get("hidden_string"),
                required_double_entry=q.get("required_double_entry") or False,
                disabled=q.get("disabled") or False,
                addon_before=q.get("addon_before"),
                addon_after=q.get("addon_after"),
                data_api_url=q.get("data_api_url"),
                center=q.get("center"),
                tree_option=q.get("tree_option"),
                limit=q.get("limit"),
                columns=q.get("columns"),
            )
            if q_id is not None and q_id in question_db:
                q_obj = question_db[q_id]
                if claim_foreign_questions:
                    # Cross-form move: reassign the row, keeping its PK so
                    # existing answers stay linked (seeder semantics)
                    q_fields["form"] = form
                    q_fields["question_group"] = g_obj
                for k, v in q_fields.items():
                    setattr(q_obj, k, v)
                q_obj.save(update_fields=list(q_fields.keys()))
                live_q_id = q_id
            else:
                # Preserve the exported id when free (FR-7/R-2) so later
                # re-imports keep matching this question by id
                if q_id is not None and not Questions.objects_with_deleted\
                        .filter(id=q_id).exists():
                    q_fields["id"] = q_id
                q_obj = Questions.objects.create(
                    form=form, question_group=g_obj, **q_fields
                )
                if q_id is not None:
                    question_db[q_id] = q_obj
                live_q_id = q_obj.id

            for opt in q.get("option") or []:
                new_options.append(QuestionOptions(
                    question_id=live_q_id,
                    order=opt.get("order", 1),
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

    # Explicit-ID inserts above may have left the sequences behind
    _sync_import_pk_sequences()

    form.name = norm.get("name", form.name)
    form.description = norm.get("description")
    form.approval_instructions = norm.get("approval_instructions")
    form.languages = norm.get("languages")
    form.default_language = norm.get("default_language")
    form.translations = norm.get("translations")
    form.updated_by = user
    form.save(update_fields=[
        "name",
        "description",
        "approval_instructions",
        "languages",
        "default_language",
        "translations",
        "updated_by",
    ])
