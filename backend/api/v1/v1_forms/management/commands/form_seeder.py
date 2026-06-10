import json
import os
import re

from mis.settings import PROD
from django.core.management import BaseCommand
from django.db import transaction

from api.v1.v1_forms.constants import (
    QuestionTypes,
    AttributeTypes,
    FormStatus,
)
from api.v1.v1_forms.models import (
    Forms, Questions,
    QuestionGroup as QG,
    QuestionOptions as QO,
    QuestionAttribute as QA)
from api.v1.v1_data.models import (
    Answers, AnswerHistory, FormData)


def clean_string(input_string):
    stripped_string = input_string.strip()
    lowercase_string = stripped_string.lower()
    no_special_chars_string = re.sub(r'[^a-z0-9 ]', '', lowercase_string)
    underscore_string = no_special_chars_string.replace(' ', '_')
    final_string = underscore_string.strip('_')
    return final_string


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
        source_files = list(
            filter(lambda x: "example" in x
                   if TEST else "example" not in x, source_files))
        if PROD:
            source_files = list(filter(lambda x: "prod" in x, source_files))
        if JSON_FILE:
            source_files = [f"{source_folder}{JSON_FILE}.prod.json"]

        # Sort forms based on parent_id: forms without parent_id first,
        # then forms with parent_id
        parent_forms = []
        child_forms = []

        for source in source_files:
            with open(source, 'r') as f:
                json_form = json.load(f)
                if json_form.get("parent_id"):
                    child_forms.append(source)
                else:
                    parent_forms.append(source)

        # Build global question-to-form map from all form JSONs
        # {question_id: target_form_id}
        question_target_map = {}
        for source in parent_forms + child_forms:
            with open(source, 'r') as f:
                json_form = json.load(f)
            for qg in json_form["question_groups"]:
                for q in qg["questions"]:
                    question_target_map[q["id"]] = json_form["id"]

        # Process all form sources in the correct order
        # (parents first, then children)
        all_question_group_ids = []
        all_form_ids = []
        with transaction.atomic():
            for source in parent_forms + child_forms:
                with open(source, 'r') as f:
                    json_form = json.load(f)

                form = Forms.objects.filter(id=json_form["id"]).first()
                QA.objects.filter(question__form=form).all().delete()
                if not form:
                    form = Forms.objects.create(
                        id=json_form["id"],
                        name=json_form["form"],
                        version=1,
                        approval_instructions=json_form.get(
                            'approval_instructions'
                        ),
                        type=json_form.get("type"),
                        status=FormStatus.published,
                    )
                    if json_form.get("parent_id"):
                        parent = Forms.objects.filter(
                            id=json_form["parent_id"]).first()
                        if parent:
                            form.parent = parent
                            form.save()
                    if not TEST:
                        self.stdout.write(
                            f"Form Created | {form.name} V{form.version}")
                else:
                    form.name = json_form["form"]
                    form.version += 1
                    if json_form.get("parent_id"):
                        parent = Forms.objects.filter(
                            id=json_form["parent_id"]).first()
                        if parent:
                            form.parent = parent
                    if json_form.get("approval_instructions"):
                        form.approval_instructions = json_form.get(
                            "approval_instructions"
                        )
                    else:
                        form.approval_instructions = None
                    if json_form.get("type"):
                        form.type = json_form.get("type")
                    form.save()
                    if not TEST:
                        self.stdout.write(
                            f"Form Updated | {form.name} V{form.version}")
                # Collect IDs from JSON before processing
                list_of_question_ids = []
                list_of_question_group_ids = []
                all_form_ids.append(json_form["id"])
                for qg in json_form["question_groups"]:
                    list_of_question_group_ids.append(qg["id"])
                    list_of_question_ids += [
                        q["id"] for q in qg["questions"]
                    ]
                all_question_group_ids += list_of_question_group_ids

                # Handle removed questions BEFORE processing
                # to avoid unique constraint violations
                removed_qs = Questions.objects.filter(
                    form=form
                ).exclude(id__in=list_of_question_ids)
                for question in removed_qs:
                    target_form_id = question_target_map.get(question.id)
                    if target_form_id and target_form_id != form.id:
                        # Question is moving to another form;
                        # migrate answers before it gets reassigned
                        migrate_question_answers(
                            question, target_form_id)
                    else:
                        # Question truly removed — delete it
                        question.delete()

                # question group loop
                for qgi, qg in enumerate(json_form["question_groups"]):
                    question_group = QG.objects.filter(pk=qg["id"]).first()
                    if not question_group:
                        question_group = QG.objects.create(
                            id=qg["id"],
                            name=qg["name"],
                            label=qg["label"],
                            form=form,
                            order=qg["order"],
                            repeatable=qg.get("repeatable", False),
                            repeat_text=qg.get("repeatText"),
                        )
                    else:
                        question_group.name = qg["name"]
                        question_group.label = qg["label"]
                        question_group.order = qg["order"]
                        question_group.repeatable = qg.get(
                            "repeatable", False)
                        question_group.repeat_text = qg.get("repeatText")
                        question_group.save()
                    for qi, q in enumerate(qg["questions"]):
                        question = Questions.objects.filter(
                            pk=q["id"]).first()
                        if not question:
                            question = Questions.objects.create(
                                id=q.get("id"),
                                name=q["name"],
                                label=q["label"],
                                short_label=q.get("short_label"),
                                form=form,
                                order=q.get("order") or qi + 1,
                                meta=q.get("meta"),
                                question_group=question_group,
                                rule=q.get("rule"),
                                required=q.get("required"),
                                dependency=q.get("dependency"),
                                dependency_rule=q.get("dependency_rule"),
                                api=q.get("api"),
                                type=getattr(QuestionTypes, q["type"]),
                                tooltip=q.get("tooltip"),
                                fn=q.get("fn"),
                                pre=q.get("pre"),
                                display_only=q.get("displayOnly"),
                                extra=q.get("extra"),
                            )
                        else:
                            question.form = form
                            question.question_group = question_group
                            question.name = q["name"]
                            question.label = q["label"]
                            question.short_label = q.get("short_label")
                            question.order = q.get("order") or qi + 1
                            question.meta = q.get("meta")
                            question.rule = q.get("rule")
                            question.required = q.get("required")
                            question.dependency = q.get("dependency")
                            question.dependency_rule = q.get(
                                "dependency_rule")
                            question.type = getattr(
                                QuestionTypes, q["type"])
                            question.api = q.get("api")
                            question.extra = q.get("extra")
                            question.tooltip = q.get("tooltip")
                            question.fn = q.get("fn")
                            question.display_only = q.get("displayOnly")
                            question.pre = q.get("pre")
                            question.save()
                        QO.objects.filter(
                            question=question).all().delete()
                        if q.get("options"):
                            QO.objects.bulk_create([
                                QO(
                                    label=o["label"].strip(),
                                    value=o["value"] if o.get("value")
                                    else clean_string(
                                        o["label"]
                                    ),
                                    question=question,
                                    order=o["order"] if o.get("order")
                                    else io + 1,
                                    color=o.get("color")
                                ) for io, o in enumerate(q.get("options"))
                            ])
                        QA.objects.filter(
                            question=question).all().delete()
                        if q.get("attributes"):
                            QA.objects.bulk_create([
                                QA(
                                    attribute=getattr(
                                        AttributeTypes, a),
                                    question=question,
                                ) for a in q.get("attributes")
                            ])

            # Final cleanup: delete question groups not present in any
            # JSON and with no remaining questions. This catches groups
            # emptied by cross-form question moves.
            QG.objects.filter(
                form_id__in=all_form_ids
            ).exclude(
                id__in=all_question_group_ids
            ).filter(
                question_group_question__isnull=True
            ).delete()
