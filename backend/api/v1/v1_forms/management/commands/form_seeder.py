import json
import os

from mis.settings import PROD
from django.core.management import BaseCommand
from django.db import transaction

from api.v1.v1_forms.constants import AttributeTypes, FormStatus
from api.v1.v1_forms.functions import (
    import_form_definition,
    normalize_form_definition,
    validate_form_definition,
)
from api.v1.v1_forms.models import (
    Forms, Questions,
    QuestionAttribute as QA)
from api.v1.v1_data.models import (
    Answers, AnswerHistory, FormData)


def migrate_question_answers(question, target_form_id):
    """Migrate answers from source form data to target monitoring form data.

    When a question moves from registration to monitoring form,
    redistribute its answers to the corresponding monitoring FormData
    children. If no children exist, keep the answer on the source data.
    """
    target_form = Forms.objects.filter(id=target_form_id).first()
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

    def handle(self, *args, **options):
        TEST = options.get("test")
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
        with transaction.atomic():
            for source in parent_forms + child_forms:
                norm = norms[source]

                issues = validate_form_definition(norm, check_entities=False)
                errors = [i for i in issues if i.get("level") == "error"]
                if errors:
                    for e in errors:
                        self.stderr.write(
                            f"{source}: [{e['code']}] "
                            f"{e['path']}: {e['message']}"
                        )
                    continue

                form = Forms.objects.filter(id=norm["form_id"]).first()
                created = form is None

                parent = None
                hint = norm.get("parent_hint")
                if hint and hint.get("id"):
                    parent = Forms.objects.filter(id=hint["id"]).first()

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
                    )
                else:
                    form.version += 1
                    if parent:
                        form.parent = parent
                    if norm.get("type"):
                        form.type = norm.get("type")
                    form.save()

                # Collect IDs from the file before processing
                list_of_question_ids = []
                list_of_question_group_ids = []
                for g in norm["question_group"]:
                    list_of_question_group_ids.append(g["id"])
                    list_of_question_ids += [
                        q["id"] for q in g["question"]
                    ]

                # A question this form no longer declares is left alone:
                # deleting it would cascade to its answers, and a re-seed
                # must never cost a submission. The one exception is a
                # question moving to another form. `claim_foreign_questions`
                # reassigns the row by primary key, so without this its
                # answers would stay bound to submissions of the form it
                # left. migrate_question_answers copies them down to the
                # monitoring children first and only then drops the
                # originals — it deletes strictly what it has already
                # copied.
                removed_qs = Questions.objects.filter(
                    form=form
                ).exclude(id__in=list_of_question_ids)
                for question in removed_qs:
                    target_form_id = question_target_map.get(question.id)
                    if target_form_id and target_form_id != form.id:
                        migrate_question_answers(question, target_form_id)

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

                if not TEST:
                    verb = "Created" if created else "Updated"
                    self.stdout.write(
                        f"Form {verb} | {norm['name']} V{form.version}")
