import json
import os

from mis.settings import PROD
from django.core.management import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction

from api.v1.v1_forms.constants import AttributeTypes, FormStatus
from api.v1.v1_forms.functions import (
    _build_schema_snapshot,
    import_form_definition,
    normalize_form_definition,
    validate_form_definition,
)
from api.v1.v1_forms.models import (
    Forms, Questions,
    QuestionAttribute as QA)
from api.v1.v1_data.models import (
    Answers, AnswerHistory, FormData)
from utils.tenant_command import resolve_tenant


def migrate_question_answers(question, target_form_id, tenant=None):
    """Migrate answers from source form data to target monitoring form data.

    When a question moves from registration to monitoring form,
    redistribute its answers to the corresponding monitoring FormData
    children. If no children exist, keep the answer on the source data.

    Scoped by tenant: the target id comes from the file, and moving
    answers towards another workspace's form would be a silent
    cross-tenant write. Defaults to None -- the tenant-less space -- so
    the helper keeps its original two-argument signature for callers
    that predate workspaces.
    """
    target_form = Forms.objects.filter(
        id=target_form_id, tenant=tenant
    ).first()
    if not target_form:
        return

    answers = Answers.objects.filter(question=question)
    for answer in answers:
        source_data = answer.data
        valid_children = source_data.children.filter(
            is_pending=False,
            is_draft=False,
        )
        if not valid_children.exists():
            continue  # No valid children to migrate to
        for child in valid_children.all():
            Answers.objects.create(
                data=child,
                question=question,
                name=answer.name,
                value=answer.value,
                options=answer.options,
                created_by=answer.created_by,
                updated=answer.updated,
                index=answer.index,
            )
        answer.delete()

    # Handle AnswerHistory the same way
    histories = AnswerHistory.objects.filter(question=question)
    for history in histories:
        source_data = history.data
        children = FormData.objects.filter(
            parent=source_data, form=target_form
        )
        if children.exists():
            for child in children:
                AnswerHistory.objects.create(
                    data=child,
                    question=question,
                    name=history.name,
                    value=history.value,
                    options=history.options,
                    created_by=history.created_by,
                    updated=history.updated,
                )
            history.delete()


def structure_fingerprint(form):
    """Comparable view of a form's live structure.

    Used to decide whether a re-seed actually changed anything. The
    snapshot builder already walks groups → questions → options in a
    fixed order, so comparing two of them answers "did this file change
    the form?" without hand-maintaining a field list that would drift
    every time a column is added.

    The `version` pop is purely defensive: _build_schema_snapshot does not
    emit a version key today, and it must never leak into the comparison
    if that ever changes, since the version is the thing being decided.

    `type` and `parent_id` are folded in by hand because the snapshot
    builder covers only the structure below the form row, yet both are
    columns the seeder writes from the file. Without them a definition
    that only retypes a form — registration to monitoring, or a
    re-parenting — would never bump the version and so would never reach
    a mobile device, which re-downloads on version change alone.
    """
    schema = _build_schema_snapshot(form)
    schema.pop("version", None)
    schema["type"] = form.type
    schema["parent_id"] = form.parent_id
    return json.dumps(schema, sort_keys=True, default=str)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("-t",
                            "--test",
                            nargs="?",
                            const=1,
                            default=False,
                            type=int)
        parser.add_argument("-f",
                            "--file",
                            nargs="?",
                            default=False,
                            type=str)
        parser.add_argument("-s",
                            "--source",
                            nargs="?",
                            default=None,
                            type=str)
        # No short flag: -t is already --test on this command, and two
        # flags one keystroke apart is how a form id ends up in --tenant.
        parser.add_argument("--tenant",
                            default=None,
                            type=str,
                            help=("Workspace subdomain to seed the forms "
                                  "into. Omit to seed into the "
                                  "tenant-less space."))

    def handle(self, *args, **options):
        TEST = options.get("test")
        # Optional: omitting it seeds into the tenant-less space, which
        # is how seeder.sh, reset_forms and 138 test call sites run.
        tenant = resolve_tenant(options.get("tenant"))
        JSON_FILE = options.get("file")
        # Form source. Overridable via --source so tests can point the
        # seeder at an isolated copy of the fixtures instead of mutating
        # the shared repo fixtures (which races under --parallel).
        source_folder = options.get("source") or './source/forms/'
        if not source_folder.endswith(os.sep):
            source_folder = f"{source_folder}{os.sep}"
        source_files = [
            f"{source_folder}{json_file}"
            for json_file in os.listdir(source_folder)
            if (os.path.isfile(os.path.join(source_folder, json_file))
                and json_file.endswith('.json'))
        ]
        # --test narrows to the bundled example fixtures. Without it every
        # JSON in the folder is seeded: a real deployment drops its own form
        # definitions here and should not have to encode "not an example" in
        # the filename. The old `else` branch did exactly that, and since the
        # folder holds nothing but example-* files it made a plain run seed
        # nothing at all and exit 0.
        if TEST:
            source_files = [f for f in source_files if "example" in f]
        if PROD:
            source_files = list(filter(lambda x: "prod" in x, source_files))
        if JSON_FILE:
            source_files = [f"{source_folder}{JSON_FILE}.prod.json"]

        # Parse every file through the shared FB-007 parser (D-8) and
        # sort: forms without a parent hint first, then children.
        norms = {}
        parent_forms = []
        child_forms = []

        for source in source_files:
            with open(source, 'r') as f:
                raw = json.load(f)
            norm = normalize_form_definition(raw)
            # Legacy files may omit order fields; default them by position
            # (same fallback the legacy seeder applied).
            for gi, g in enumerate(norm["question_group"]):
                if not g.get("order"):
                    g["order"] = gi + 1
                for qi, q in enumerate(g["question"]):
                    if not q.get("order"):
                        q["order"] = qi + 1
            norms[source] = norm
            if norm.get("parent_hint"):
                child_forms.append(source)
            else:
                parent_forms.append(source)

        # Build global question-to-form map from all form files
        # {question_id: target_form_id}
        question_target_map = {}
        for source in parent_forms + child_forms:
            norm = norms[source]
            for g in norm["question_group"]:
                for q in g["question"]:
                    question_target_map[q["id"]] = norm["form_id"]

        # Process all form sources in the correct order
        # (parents first, then children)
        failed_sources = []
        with transaction.atomic():
            for source in parent_forms + child_forms:
                norm = norms[source]

                issues = validate_form_definition(norm, check_entities=False)
                errors = [i for i in issues if i.get("level") == "error"]
                if errors:
                    # Report every problem in every file rather than
                    # stopping at the first, so one pass tells the operator
                    # everything that needs fixing.
                    for e in errors:
                        self.stderr.write(
                            f"{source}: [{e['code']}] "
                            f"{e['path']}: {e['message']}"
                        )
                    failed_sources.append(source)
                    continue

                # Scope by tenant only when one was named. Omitting
                # --tenant means "behave as before workspaces existed":
                # find the form by id whatever it belongs to, and update
                # it in place. Scoping unconditionally would treat every
                # already-owned form as new and then refuse to create it.
                matches = Forms.objects.filter(id=norm["form_id"])
                if tenant is not None:
                    matches = matches.filter(tenant=tenant)
                form = matches.first()
                created = form is None

                if created and tenant is not None:
                    # Form ids come from the file and `id` IS the primary
                    # key, so the same definition cannot be seeded into two
                    # workspaces. Without this check the unscoped lookup
                    # this replaced would find the other tenant's row and
                    # silently rewrite it -- handing their form to whoever
                    # ran the seeder last. objects_with_deleted because a
                    # soft-deleted form still occupies its id.
                    clash = Forms.objects_with_deleted.filter(
                        id=norm["form_id"]
                    ).first()
                    if clash is not None:
                        owner = (
                            clash.tenant.subdomain if clash.tenant
                            else "the tenant-less space"
                        )
                        raise CommandError(
                            f"{source}: form id {norm['form_id']} already "
                            f"belongs to {owner}. Form ids are global, so "
                            "a definition can only be seeded once per "
                            "install -- give this file its own id."
                        )

                parent = None
                hint = norm.get("parent_hint")
                if hint and hint.get("id"):
                    parents_qs = Forms.objects.filter(id=hint["id"])
                    if tenant is not None:
                        parents_qs = parents_qs.filter(tenant=tenant)
                    parent = parents_qs.first()

                if created:
                    # The shared import path creates drafts (FR-11); the
                    # seeder pre-creates the row so it can keep its legacy
                    # publish-on-seed behaviour, then lets the update path
                    # write the structure.
                    form = Forms.objects.create(
                        id=norm["form_id"],
                        name=norm["name"],
                        version=1,
                        approval_instructions=norm.get(
                            "approval_instructions"
                        ),
                        type=norm.get("type"),
                        status=FormStatus.published,
                        parent=parent,
                        # import_form_definition stamps tenant from the
                        # `user` it is given, and the seeder has none. The
                        # row is pre-created here anyway, and the update
                        # path's explicit update_fields never include
                        # tenant, so setting it once here is permanent.
                        tenant=tenant,
                    )
                    # A form that did not exist has nothing to compare
                    # against; it is new, so its version stands at 1.
                    before_fingerprint = None
                else:
                    # Snapshot before anything is written, so the
                    # post-import comparison can tell a real edit from a
                    # no-op re-run. It has to happen ahead of the save
                    # below: that save applies the file's parent/type, and
                    # those are part of the fingerprint, so capturing
                    # afterwards would compare the new values against
                    # themselves and hide the change.
                    before_fingerprint = structure_fingerprint(form)
                    if parent:
                        form.parent = parent
                    if norm.get("type"):
                        form.type = norm.get("type")
                    form.save()

                # Collect IDs from the file before processing
                list_of_question_ids = []
                for g in norm["question_group"]:
                    list_of_question_ids += [
                        q["id"] for q in g["question"]
                    ]

                # A question this form no longer declares is left alone as
                # long as it carries answers: deleting it would cascade to
                # them, and a re-seed must never cost a submission. An
                # unanswered one is still pruned by the import writer's
                # never_delete pass, which has nothing to protect and needs
                # the freed (form, name) slot. The one exception to leaving
                # answered questions alone is a question moving to another
                # form. `claim_foreign_questions` reassigns the row by
                # primary key, so without this its answers would stay bound
                # to submissions of the form it left. The migration helper
                # below copies them down to the monitoring children first
                # and only then drops the originals — it deletes strictly
                # what it has already copied.
                removed_qs = Questions.objects.filter(
                    form=form
                ).exclude(id__in=list_of_question_ids)
                for question in removed_qs:
                    target_form_id = question_target_map.get(question.id)
                    if target_form_id and target_form_id != form.id:
                        migrate_question_answers(
                            question, target_form_id, tenant
                        )

                # Shared write path (D-8): groups/questions/options upsert
                # by exported id; cross-form moves claimed by PK so answers
                # stay linked.
                import_form_definition(
                    norm,
                    None,
                    mode="create_or_update",
                    require_parent=False,
                    claim_foreign_questions=True,
                    never_delete=True,
                )

                # Question attributes stay a seeder concern (not part of
                # the FB-007 export format). Reconcile rather than wipe and
                # rebuild, and only for questions this file declares —
                # attributes of any other question are none of its business.
                #
                # Dropping an attribute here is not a data-loss exception:
                # QuestionAttribute rows are form metadata, nothing
                # references them, and no answer depends on one.
                qa_rows = []
                for g in norm["question_group"]:
                    for q in g["question"]:
                        db_q = Questions.objects.filter(
                            form=form, name=q["name"]
                        ).first()
                        if not db_q:
                            continue
                        declared = set()
                        for a in q.get("attributes") or []:
                            declared.add(getattr(AttributeTypes, a))
                        current = set(
                            QA.objects.filter(
                                question=db_q
                            ).values_list("attribute", flat=True)
                        )
                        QA.objects.filter(question=db_q).exclude(
                            attribute__in=declared
                        ).delete()
                        qa_rows += [
                            QA(attribute=a, question=db_q)
                            for a in declared - current
                        ]
                if qa_rows:
                    QA.objects.bulk_create(qa_rows)

                # Bump only for a definition that actually differs. See
                # structure_fingerprint for why this matters to mobile.
                if before_fingerprint is not None:
                    form.refresh_from_db()
                    if structure_fingerprint(form) != before_fingerprint:
                        form.version += 1
                        form.save(update_fields=["version"])

                if not TEST:
                    verb = "Created" if created else "Updated"
                    self.stdout.write(
                        f"Form {verb} | {norm['name']} V{form.version}")

            # A file that failed validation must not be a silent skip.
            # seeder.sh calls this command bare and reports success on
            # exit 0, so without this a client's real form could go
            # missing while the install looks clean.
            #
            # The raise sits inside the atomic block on purpose. Every
            # file was still attempted, so the operator gets the complete
            # list of failures in one run — but the run as a whole is
            # rolled back rather than committed half-applied. That matters
            # because question_target_map is built from all files
            # including the invalid ones: committing here could leave
            # answers migrated towards a form that was never written.
            if failed_sources:
                raise CommandError(
                    "form_seeder failed to load {0} of {1} definition(s): "
                    "{2}. See the errors above; no forms were written."
                    .format(
                        len(failed_sources),
                        len(source_files),
                        ", ".join(failed_sources),
                    )
                )
