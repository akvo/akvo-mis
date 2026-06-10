import logging
import os
import re
import zipfile
from datetime import datetime, time, timedelta
from dateutil import parser
from django_q.models import Task

import pandas as pd
from django.conf import settings
from django.utils import timezone
from django_q.tasks import async_task
from api.v1.v1_jobs.administrations_bulk_upload import (
    seed_administration_data,
    validate_administrations_bulk_upload,
)
from utils.upload_entities import (
    validate_entity_file,
    validate_entity_data,
)
from api.v1.v1_forms.models import (
    Forms,
    QuestionOptions,
)
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_data.models import FormData
from api.v1.v1_jobs.constants import JobStatus, JobTypes

from api.v1.v1_jobs.models import Jobs
from api.v1.v1_jobs.seed_data import seed_excel_data
from api.v1.v1_jobs.validate_upload import validate
from api.v1.v1_jobs.constants import DataDownloadTypes
from api.v1.v1_profile.models import Administration, EntityData
from api.v1.v1_users.models import SystemUser
from utils import storage
from utils.email_helper import send_email, EmailTypes
from utils.export_form import (
    generate_definition_sheet,
    get_question_names,
    blank_data_template,
    meta_columns,
    monitoring_meta_columns,
)
from utils.functions import update_date_time_format
from utils.storage import upload
from utils.custom_generator import generate_sqlite
from utils.report_generator import generate_datapoint_report

logger = logging.getLogger(__name__)


def _build_date_filter(date_from=None, date_to=None):
    """Build created__gte / created__lt filter kwargs from date strings."""
    date_filter = {}
    if date_from:
        start_date = parser.parse(date_from)
        start_datetime = datetime.combine(start_date, time.min)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
        date_filter["created__gte"] = start_datetime
    if date_to:
        end_date = parser.parse(date_to)
        end_datetime = datetime.combine(
            end_date + timedelta(days=1), time.min
        )
        if settings.USE_TZ:
            end_datetime = timezone.make_aware(end_datetime)
        date_filter["created__lt"] = end_datetime
    return date_filter


def download_data(
    form: Forms,
    administration_ids: list = None,
    download_type: str = DataDownloadTypes.recent,
    child_form_ids: list = None,
    date_from: str = None,
    date_to: str = None,
    selection_ids: list = None,
    filter_child_form_ids: list = None,
) -> list:
    if child_form_ids is None:
        child_form_ids = []
    # filter_child_form_ids controls which child forms are used when
    # computing the union for date-range filtering. Falls back to
    # child_form_ids when not provided (preserves existing behaviour).
    effective_filter_children = (
        filter_child_form_ids
        if filter_child_form_ids is not None
        else child_form_ids
    )

    if selection_ids:
        data = form.form_form_data.filter(
            id__in=selection_ids,
            is_pending=False,
            is_draft=False,
        ).order_by("id").all()
        data_items = []
        for d in data:
            item = d.to_data_frame
            for child_form in child_form_ids:
                dl = d.children.filter(
                    form_id=child_form,
                    is_pending=False,
                    is_draft=False,
                ).order_by("-created").first()
                if dl:
                    item = {**item, **dl.to_data_frame}
                    item["datapoint_name"] = d.name
                    item["created_at"] = d.to_data_frame.get("created_at")
                    item["created_by"] = d.created_by.get_full_name()
                    item["updated_at"] = dl.to_data_frame.get("created_at")
                    item["updated_by"] = dl.created_by.get_full_name()
            data_items.append(item)
        return data_items

    has_date_filter = date_from or date_to
    date_filter = _build_date_filter(date_from, date_to)

    filter_data = {
        "is_pending": False,
        "is_draft": False,
    }
    if administration_ids:
        filter_data["administration_id__in"] = administration_ids

    if has_date_filter and effective_filter_children:
        # Include parents with in-range children (by created date) OR
        # parents whose own created date is in range.
        child_filter = {
            "is_pending": False,
            "is_draft": False,
            "form_id__in": effective_filter_children,
            **date_filter,
        }
        if administration_ids:
            child_filter["administration_id__in"] = administration_ids
        matched_children = FormData.objects.filter(**child_filter)
        parent_ids_from_children = set(
            matched_children.values_list("parent_id", flat=True)
        )
        # Parents in date range themselves
        parent_date_filter = {**filter_data, **date_filter}
        parent_ids_in_range = set(
            form.form_form_data.filter(**parent_date_filter)
            .values_list("id", flat=True)
        )
        # Union: parents with in-range children OR in-range themselves
        all_parent_ids = parent_ids_from_children | parent_ids_in_range
        data = form.form_form_data.filter(
            id__in=all_parent_ids, **filter_data
        ).order_by("id").all()
    elif has_date_filter:
        # No child forms — filter parents directly by date
        filter_data.update(date_filter)
        data = form.form_form_data.filter(
            **filter_data
        ).order_by("id").all()
    else:
        # No date filter — existing behavior
        data = form.form_form_data.filter(
            **filter_data
        ).order_by("id").all()

    data_items = []
    for d in data:
        if download_type == DataDownloadTypes.recent:
            item = d.to_data_frame
            for child_form in child_form_ids:
                dl = d.children.filter(
                    form_id=child_form,
                    is_pending=False,
                    is_draft=False,
                    **date_filter,
                ).order_by("-created").first()
                if dl:
                    # merge parent and child data
                    item = {**item, **dl.to_data_frame}
                    # keep datapoint_name and created_at from parent
                    item["datapoint_name"] = d.name
                    item["created_at"] = d.to_data_frame.get("created_at")
                    item["created_by"] = d.created_by.get_full_name()
                    item["updated_at"] = dl.to_data_frame.get("created_at")
                    item["updated_by"] = dl.created_by.get_full_name()
            data_items.append(item)
        if download_type == DataDownloadTypes.all:
            has_children = False
            for child_form in child_form_ids:
                for dl in d.children.filter(
                    form_id=child_form,
                    is_pending=False,
                    is_draft=False,
                    **date_filter,
                ).order_by("created").all():
                    has_children = True
                    data_items.append({
                        **d.to_data_frame,
                        **dl.to_data_frame,
                        "datapoint_name": d.name,
                        "created_at": d.to_data_frame.get("created_at"),
                        "created_by": d.created_by.get_full_name(),
                        "updated_at": dl.to_data_frame.get("created_at"),
                        "updated_by": dl.created_by.get_full_name(),
                    })
            if not has_children:
                data_items.append(d.to_data_frame)
    return data_items


def get_answer_label(answer_values, question_id):
    if answer_values is None or answer_values != answer_values:
        return answer_values
    answer_value = answer_values.split("|")
    answer_label = []
    for value in answer_value:
        options = QuestionOptions.objects.filter(
            question_id=question_id, value=value
        ).first()
        if options:
            answer_label.append(options.label)
    return "|".join(answer_label)


def generate_data_sheet(
    writer: pd.ExcelWriter,
    form: Forms,
    administration_ids: list = None,
    download_type: str = DataDownloadTypes.recent,
    use_label: bool = True,
    child_form_ids: list = None,
    date_from: str = None,
    date_to: str = None,
    selection_ids: list = None,
    filter_child_form_ids: list = None,
) -> None:
    if child_form_ids is None:
        child_form_ids = []
    questions = get_question_names(form=form)
    if len(child_form_ids):
        child_forms = form.children.filter(id__in=child_form_ids).all()
        for child_form in child_forms:
            questions.extend(get_question_names(form=child_form))
    data = download_data(
        form=form,
        administration_ids=administration_ids,
        download_type=download_type,
        child_form_ids=child_form_ids,
        date_from=date_from,
        date_to=date_to,
        selection_ids=selection_ids,
        filter_child_form_ids=filter_child_form_ids,
    )
    if len(data):
        df = pd.DataFrame(data)
        # Create a mapping of base question names to question info for lookup
        question_map = {}
        for question in questions:
            question_id, question_name, question_type = question
            question_map[question_name] = {
                'id': question_id,
                'type': question_type,
                'name': question_name
            }
        # Get all actual column names from the dataframe (including indexed)
        actual_columns = [col for col in df.columns if col not in meta_columns]
        # Ensure all question columns exist in dataframe (base and indexed)
        for question in questions:
            question_id, question_name, question_type = question
            if question_name not in df:
                df[question_name] = None

        # Process labels for option-type questions (including indexed columns)
        new_columns = {}
        if use_label:
            for col_name in actual_columns:
                # Check if this is an indexed column (contains underscore)
                base_question_name = (
                    col_name.split('_')[0] if '_' in col_name else col_name
                )
                if base_question_name in question_map:
                    question_info = question_map[base_question_name]
                    if question_info['type'] in [
                        QuestionTypes.option,
                        QuestionTypes.multiple_option,
                    ]:
                        new_columns[col_name] = df[col_name].apply(
                            lambda x: get_answer_label(x, question_info['id'])
                        )
        # Apply label transformations
        if use_label and new_columns:
            new_df = pd.DataFrame(new_columns)
            df.drop(columns=list(new_columns.keys()), inplace=True)
            df = pd.concat([df, new_df], axis=1)
        # Reorder columns: meta columns first, then all question columns
        available_question_columns = [
            col for col in df.columns if col not in meta_columns
        ]
        final_columns = meta_columns + available_question_columns
        df = df[final_columns]
        df.to_excel(writer, sheet_name="data", index=False)
        generate_definition_sheet(
            writer=writer,
            form=form,
            child_form_ids=child_form_ids,
        )
    else:
        blank_data_template(form=form, writer=writer)


def download_monitoring_data(
    parent_form: Forms,
    child_form: Forms,
    administration_ids: list = None,
    download_type: str = DataDownloadTypes.recent,
    date_from: str = None,
    date_to: str = None,
    selection_ids: list = None,
) -> list:
    date_filter = _build_date_filter(date_from, date_to)
    filter_data = {
        "form": child_form,
        "parent__form": parent_form,
        "parent__isnull": False,
        "is_pending": False,
        "is_draft": False,
    }
    if selection_ids:
        filter_data["parent_id__in"] = selection_ids
    if administration_ids:
        filter_data["parent__administration_id__in"] = administration_ids
    filter_data.update(date_filter)

    queryset = FormData.objects.filter(
        **filter_data
    ).select_related("parent", "parent__administration", "created_by")

    if download_type == DataDownloadTypes.recent:
        # Get latest monitoring submission per parent
        seen_parents = {}
        for fd in queryset.order_by("parent_id", "-created"):
            if fd.parent_id not in seen_parents:
                seen_parents[fd.parent_id] = fd
        monitoring_records = list(seen_parents.values())
    else:
        monitoring_records = list(
            queryset.order_by("parent_id", "created").all()
        )

    data_items = []
    for fd in monitoring_records:
        item = fd.to_data_frame
        item["parent_id"] = fd.parent_id
        item["datapoint_name"] = fd.parent.name
        parent_admin = fd.parent.administration
        item["administration"] = (
            parent_admin.administration_column if parent_admin else None
        )
        data_items.append(item)
    return data_items


def generate_monitoring_data_sheet(
    writer: pd.ExcelWriter,
    parent_form: Forms,
    child_form: Forms,
    administration_ids: list = None,
    download_type: str = DataDownloadTypes.recent,
    use_label: bool = True,
    date_from: str = None,
    date_to: str = None,
    selection_ids: list = None,
) -> None:
    questions = get_question_names(form=child_form)
    data = download_monitoring_data(
        parent_form=parent_form,
        child_form=child_form,
        administration_ids=administration_ids,
        download_type=download_type,
        date_from=date_from,
        date_to=date_to,
        selection_ids=selection_ids,
    )
    if len(data):
        df = pd.DataFrame(data)
        question_map = {}
        for question in questions:
            question_id, question_name, question_type = question
            question_map[question_name] = {
                'id': question_id,
                'type': question_type,
                'name': question_name
            }
        actual_columns = [
            col for col in df.columns
            if col not in monitoring_meta_columns
        ]
        for question in questions:
            question_id, question_name, question_type = question
            if question_name not in df:
                df[question_name] = None

        new_columns = {}
        if use_label:
            for col_name in actual_columns:
                base_question_name = (
                    col_name.split('_')[0]
                    if '_' in col_name else col_name
                )
                if base_question_name in question_map:
                    question_info = question_map[base_question_name]
                    if question_info['type'] in [
                        QuestionTypes.option,
                        QuestionTypes.multiple_option,
                    ]:
                        new_columns[col_name] = df[col_name].apply(
                            lambda x: get_answer_label(
                                x, question_info['id']
                            )
                        )
        if use_label and new_columns:
            new_df = pd.DataFrame(new_columns)
            df.drop(columns=list(new_columns.keys()), inplace=True)
            df = pd.concat([df, new_df], axis=1)

        available_question_columns = [
            col for col in df.columns
            if col not in monitoring_meta_columns
        ]
        final_columns = monitoring_meta_columns + available_question_columns
        # Only include columns that exist in the dataframe
        final_columns = [c for c in final_columns if c in df.columns]
        df = df[final_columns]
        df.to_excel(writer, sheet_name="data", index=False)
        generate_definition_sheet(
            writer=writer,
            form=child_form,
        )
    else:
        blank_data_template(form=child_form, writer=writer)


def _sanitize_form_name(name: str, form_id: int = None) -> str:
    safe = re.sub(r'[^a-z0-9_-]', '_', name.lower())
    safe = re.sub(r'_+', '_', safe).strip('_')
    if form_id is not None:
        safe = f"{safe}_{form_id}"
    return safe


def _write_context_sheet(
    writer, form, monitoring_forms, job,
    administration_name, date_from, date_to,
):
    context = [
        {"context": "Form Name", "value": form.name},
        {
            "context": "Monitoring Form(s)",
            "value": ", ".join(
                [f.name for f in monitoring_forms]
            ) if len(monitoring_forms) else "-"
        },
        {
            "context": "Download Date",
            "value": update_date_time_format(job.created),
        },
        {
            "context": "Administration",
            "value": (
                ",".join(administration_name)
                if isinstance(administration_name, list)
                else administration_name
            ),
        },
    ]
    if date_from or date_to:
        date_range_str = (
            f"{date_from or 'beginning'} to {date_to or 'present'}"
        )
        context.append(
            {"context": "Date Range Filter", "value": date_range_str}
        )
    context = (
        pd.DataFrame(context)
        .groupby(["context", "value"], sort=False)
        .first()
    )
    context.to_excel(writer, sheet_name="context", startrow=0, header=False)
    workbook = writer.book
    worksheet = writer.sheets["context"]
    fmt = workbook.add_format(
        {
            "align": "left",
            "bold": False,
            "border": 0,
        }
    )
    worksheet.set_column("A:A", 20, fmt)
    worksheet.set_column("B:B", 30, fmt)
    merge_format = workbook.add_format(
        {
            "bold": True,
            "border": 1,
            "align": "center",
            "valign": "vcenter",
            "fg_color": "#45add9",
            "color": "#ffffff",
        }
    )
    worksheet.merge_range("A1:B1", "Context", merge_format)


def _resolve_administration(kwargs):
    administration_ids = False
    administration_name = "All Administration Level"
    if kwargs.get("administration"):
        administration = Administration.objects.get(
            pk=kwargs.get("administration")
        )
        if administration.path:
            filter_path = "{0}{1}.".format(
                administration.path, administration.id
            )
        else:
            filter_path = f"{administration.id}."
        administration_ids = list(
            Administration.objects.filter(
                path__startswith=filter_path
            ).values_list("id", flat=True)
        )
        administration_ids.append(administration.id)
        administration_name = list(
            Administration.objects.filter(
                path__startswith=filter_path
            ).values_list("name", flat=True)
        )
    return administration_ids, administration_name


def _generate_excel_download(job, **kwargs):
    file_path = "./tmp/{0}".format(job.result)
    if os.path.exists(file_path):
        os.remove(file_path)
    administration_ids, administration_name = _resolve_administration(kwargs)
    form = Forms.objects.get(pk=job.info.get("form_id"))
    download_type = kwargs.get("download_type", DataDownloadTypes.recent)
    use_label = kwargs.get("use_label", True)
    child_form_ids = job.info.get("child_form_ids", [])
    selection_ids = job.info.get("selection_ids", [])
    date_from = kwargs.get("date_from")
    date_to = kwargs.get("date_to")

    with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
        generate_data_sheet(
            writer=writer,
            form=form,
            administration_ids=administration_ids,
            download_type=download_type,
            use_label=use_label,
            child_form_ids=child_form_ids,
            date_from=date_from,
            date_to=date_to,
            selection_ids=selection_ids or None,
        )
        monitoring_forms = form.children.filter(pk__in=child_form_ids).all()
        _write_context_sheet(
            writer, form, monitoring_forms, job,
            administration_name, date_from, date_to,
        )
    url = upload(file=file_path, folder="download")
    return url


def _generate_zip_download(job, **kwargs):
    zip_path = "./tmp/{0}".format(job.result)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    administration_ids, administration_name = _resolve_administration(kwargs)
    form = Forms.objects.get(pk=job.info.get("form_id"))
    download_type = kwargs.get("download_type", DataDownloadTypes.recent)
    use_label = kwargs.get("use_label", True)
    child_form_ids = job.info.get("child_form_ids", [])
    child_forms = form.children.filter(pk__in=child_form_ids).all()
    selection_ids = job.info.get("selection_ids", [])
    date_from = kwargs.get("date_from")
    date_to = kwargs.get("date_to")

    tmp_files = []
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Registration Excel
            reg_name = _sanitize_form_name(form.name)
            reg_path = f"./tmp/reg_{job.id}.xlsx"
            tmp_files.append(reg_path)
            with pd.ExcelWriter(reg_path, engine="xlsxwriter") as rw:
                generate_data_sheet(
                    writer=rw,
                    form=form,
                    administration_ids=administration_ids,
                    download_type=download_type,
                    use_label=use_label,
                    child_form_ids=[],
                    date_from=date_from,
                    date_to=date_to,
                    selection_ids=selection_ids or None,
                    # Pass child_form_ids so registrations whose monitoring
                    # falls within the date range are included even when the
                    # registration itself was created before date_from.
                    filter_child_form_ids=child_form_ids,
                )
                _write_context_sheet(
                    rw, form, child_forms, job,
                    administration_name, date_from, date_to,
                )
            zf.write(reg_path, f"{reg_name}.xlsx")

            # One Excel per monitoring form
            for child_form in child_forms:
                child_name = _sanitize_form_name(
                    child_form.name, form_id=child_form.id
                )
                child_path = (
                    f"./tmp/child_{child_form.id}_{job.id}.xlsx"
                )
                tmp_files.append(child_path)
                with pd.ExcelWriter(
                    child_path, engine="xlsxwriter"
                ) as cw:
                    generate_monitoring_data_sheet(
                        writer=cw,
                        parent_form=form,
                        child_form=child_form,
                        administration_ids=administration_ids,
                        download_type=download_type,
                        use_label=use_label,
                        date_from=date_from,
                        date_to=date_to,
                        selection_ids=selection_ids or None,
                    )
                zf.write(child_path, f"{child_name}.xlsx")

        url = upload(file=zip_path, folder="download")
        return url
    finally:
        for f in tmp_files:
            if os.path.exists(f):
                os.remove(f)


def job_generate_data_download(job_id, **kwargs):
    job = Jobs.objects.get(pk=job_id)
    child_form_ids = job.info.get("child_form_ids", [])
    if child_form_ids:
        return _generate_zip_download(job, **kwargs)
    else:
        return _generate_excel_download(job, **kwargs)


def transform_form_data_for_report(
    form: Forms, selection_ids: list = None, child_form_ids: list = []
):
    """
    Transform form data from database into the format expected by the
    report generator, supporting repeatable question groups by cloning
    the group for each repeat instance and mapping answers by index.

    When selection_ids is provided, FormData is queried by ID only
    (without form filter) to support selection of child form data directly.
    This ensures all available answers for each selection_id are included.
    """
    try:
        forms = [form]
        child_forms = list(form.children.all())
        if child_form_ids and len(child_form_ids):
            child_forms = [f for f in child_forms if f.id in child_form_ids]
            forms.extend(child_forms)

        # When selection_ids is provided, query by ID only (no form filter)
        # This allows child form data IDs to be included directly
        if selection_ids and len(selection_ids):
            main_form_data_queryset = FormData.objects.filter(
                id__in=selection_ids, is_pending=False
            )
            # Also include forms from the selected FormData to ensure
            # all relevant question groups are processed
            selected_form_ids = set(
                main_form_data_queryset.values_list("form_id", flat=True)
            )
            for form_id in selected_form_ids:
                if form_id != form.id and form_id not in [f.id for f in forms]:
                    try:
                        additional_form = Forms.objects.get(pk=form_id)
                        forms.append(additional_form)
                    except Forms.DoesNotExist:
                        pass
                        # If a referenced form no longer exists, skip it
        else:
            main_form_data_queryset = FormData.objects.filter(
                form=form, is_pending=False
            )
        main_form_data = main_form_data_queryset.order_by("id").all()
        form_data_instances = list(main_form_data)

        question_groups = []
        for f in forms:
            form_question_groups = f.form_question_group.order_by(
                "order"
            ).all()
            question_groups.extend(form_question_groups)

        result = []

        for question_group in question_groups:
            questions = question_group.question_group_question.order_by(
                "order"
            ).all()
            is_repeatable = getattr(question_group, "repeatable", False)

            if is_repeatable:
                # For each parent FormData,
                # find max repeat index for this group
                max_repeats = 0
                # Map: parent_form_data_id -> max index for this group
                parent_max_index = {}
                for main_fd in form_data_instances:
                    # Get all answers for this group and parent
                    answers = []
                    for q in questions:
                        answers.extend(
                            q.question_answer.filter(data=main_fd).all()
                        )
                        # Also check child FormData for this group
                        for child_form in child_forms:
                            for child_fd in main_fd.children.filter(
                                form=child_form, is_pending=False
                            ).all():
                                answers.extend(
                                    q.question_answer.filter(
                                        data=child_fd
                                    ).all()
                                )
                    # Find max index for this parent
                    indices = [
                        a.index
                        for a in answers
                        if hasattr(a, "index") and a.index is not None
                    ]
                    max_idx = max(indices) if indices else 0
                    parent_max_index[main_fd.id] = max_idx
                    if max_idx > max_repeats:
                        max_repeats = max_idx
                # For each repeat index, clone the group
                for repeat_idx in range(max_repeats + 1):
                    group_data = {
                        "name": (
                            f"{question_group.label or question_group.name} "
                            f"[{repeat_idx + 1}]"
                        ),
                        "questions": [],
                    }
                    for question in questions:
                        answer_values = [""] * len(form_data_instances)
                        # For each parent FormData,
                        # get answer for this repeat index
                        for fd_idx, main_fd in enumerate(form_data_instances):
                            # Check parent and children
                            answer = question.question_answer.filter(
                                data=main_fd, index=repeat_idx
                            ).first()
                            if not answer:
                                # Search ALL children, not just the last one
                                for child_form in child_forms:
                                    for child_fd in main_fd.children.filter(
                                        form=child_form, is_pending=False
                                    ).all():
                                        answer = (
                                            question.question_answer.filter(
                                                data=child_fd, index=repeat_idx
                                            ).first()
                                        )
                                        if answer:
                                            break
                                    if answer:
                                        break
                            if answer:
                                # Format answer as before
                                if question.type == QuestionTypes.geo:
                                    value = ",".join(map(str, answer.options))
                                elif question.type in [
                                    QuestionTypes.option,
                                    QuestionTypes.multiple_option,
                                ]:
                                    options = answer.question.options.filter(
                                        value__in=answer.options
                                    ).all()
                                    value = (
                                        "|".join(
                                            [opt.label for opt in options]
                                        )
                                        if options
                                        else ""
                                    )
                                elif question.type == QuestionTypes.date:
                                    value = ""
                                    if (
                                        isinstance(answer.name, str)
                                        and answer.name
                                    ):
                                        try:
                                            date_obj = parser.parse(
                                                answer.name
                                            )
                                            value = date_obj.strftime(
                                                "%B %d, %Y"
                                            )
                                        except (
                                            ImportError,
                                            ValueError,
                                            TypeError,
                                        ):
                                            value = str(answer.name)
                                elif question.type in [
                                    QuestionTypes.input,
                                    QuestionTypes.text,
                                    QuestionTypes.image,
                                    QuestionTypes.autofield,
                                    QuestionTypes.cascade,
                                    QuestionTypes.attachment,
                                    QuestionTypes.signature,
                                ]:
                                    value = answer.name or ""
                                else:
                                    value = (
                                        answer.value
                                        if answer.value is not None
                                        else ""
                                    )
                                answer_values[fd_idx] = str(value)
                        if any(
                            value.strip() for value in answer_values if value
                        ):
                            question_data = {
                                "question": question.label,
                                "answers": answer_values,
                            }
                            group_data["questions"].append(question_data)
                    if group_data["questions"]:
                        result.append(group_data)
            else:
                # Non-repeatable group: original logic
                group_data = {
                    "name": question_group.label or question_group.name,
                    "questions": [],
                }
                for question in questions:
                    answer_values = [""] * len(form_data_instances)
                    all_form_data_ids = []
                    for main_fd in main_form_data:
                        all_form_data_ids.append(main_fd.id)
                        for child_form in child_forms:
                            # Include ALL children, not just the last one
                            for child_fd in main_fd.children.filter(
                                form=child_form, is_pending=False
                            ).all():
                                all_form_data_ids.append(child_fd.id)
                    answers = question.question_answer.filter(
                        data__id__in=all_form_data_ids
                    ).select_related("data")
                    # Build mapping from FormData ID to index
                    # Include both the FormData IDs and their parent IDs
                    # to support both direct child selection and parent lookup
                    fd_id_to_index = {
                        fd.id: idx
                        for idx, fd in enumerate(form_data_instances)
                    }
                    for answer in answers:
                        # First try direct lookup by answer's FormData ID
                        form_data_index = fd_id_to_index.get(answer.data.id)
                        # If not found and answer has parent, try parent lookup
                        if form_data_index is None and answer.data.parent:
                            form_data_index = fd_id_to_index.get(
                                answer.data.parent.id
                            )
                        if form_data_index is None:
                            continue
                        if question.type == QuestionTypes.geo:
                            value = ",".join(map(str, answer.options))
                        elif question.type in [
                            QuestionTypes.option,
                            QuestionTypes.multiple_option,
                        ]:
                            options = answer.question.options.filter(
                                value__in=answer.options
                            ).all()
                            value = (
                                "|".join([opt.label for opt in options])
                                if options
                                else ""
                            )
                        elif question.type == QuestionTypes.date:
                            value = ""
                            if isinstance(answer.name, str) and answer.name:
                                try:
                                    date_obj = parser.parse(answer.name)
                                    value = date_obj.strftime("%B %d, %Y")
                                except (
                                    ImportError, ValueError, TypeError
                                ):  # pragma: no cover
                                    value = str(answer.name)
                        elif question.type in [
                            QuestionTypes.input,
                            QuestionTypes.text,
                            QuestionTypes.image,
                            QuestionTypes.autofield,
                            QuestionTypes.cascade,
                            QuestionTypes.attachment,
                            QuestionTypes.signature,
                        ]:
                            value = answer.name or ""
                        elif question.type == QuestionTypes.cascade:
                            if answer.value:
                                admin = Administration.objects.filter(
                                    pk=answer.value
                                ).first()
                                value = (
                                    admin.name if admin else str(answer.value)
                                )
                            else:
                                value = ""
                        else:
                            value = (
                                answer.value
                                if answer.value is not None
                                else ""
                            )
                        answer_values[form_data_index] = str(value)
                    if any(value.strip() for value in answer_values if value):
                        question_data = {
                            "question": question.label,
                            "answers": answer_values,
                        }
                        group_data["questions"].append(question_data)
                if group_data["questions"]:
                    result.append(group_data)
        return result
    except Exception as e:
        logger.error(
            f"Error transforming form data: {str(e)}"
        )  # pragma: no cover
        return []


def job_generate_data_report(job_id: int, **kwargs):
    try:
        job = Jobs.objects.get(pk=job_id)
        form_id = kwargs.get("form_id")
        selection_ids = kwargs.get("selection_ids", [])  # noqa: F841
        child_form_ids = kwargs.get("child_form_ids", [])

        # Get the form
        form = Forms.objects.get(pk=form_id)
        form_data = form.form_form_data.filter(
            is_pending=False,
            pk__in=selection_ids
        ).order_by("id").all()

        display_names = [
            fd.name for fd in form_data
        ]
        device_identifiers = [
            "Mobile Device" if fd.submitter else "Webform"
            for fd in form_data
        ]
        submission_dates = [
            update_date_time_format(fd.created) for fd in form_data
        ]
        submitters = [
            fd.submitter if fd.submitter else fd.created_by.get_full_name()
            for fd in form_data
        ]
        # form_version is an array of form.version based on number of form_data
        form_versions = [form.version] * len(form_data)

        # Clean up any existing file
        temp_file_path = f"./tmp/{job.result}"
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        # Generate dynamic data from database
        form_data = transform_form_data_for_report(
            form=form,
            selection_ids=selection_ids,
            child_form_ids=child_form_ids,
        )

        # Fallback to empty list if no data found
        if not form_data:
            logger.warning(f"No data found for form_id {form_id}")
            form_data = []
        # Add Datapoint information
        datapoint_info = {
            "questions": [
                {"question": "Display Name", "answers": display_names},
                {
                    "question": "Device identifier",
                    "answers": device_identifiers
                },
                {
                    "question": "Submission Date",
                    "answers": submission_dates,
                },
                {"question": "Submitter", "answers": submitters},
                {"question": "Form version", "answers": form_versions},
            ],
        }
        form_data.insert(0, datapoint_info)

        # Generate the report file
        file_path = generate_datapoint_report(
            form_data,
            file_path=temp_file_path,
            form_name=form.name,
            display_names=display_names,
        )
        url = upload(file=file_path, folder="download_datapoint_report")
        return url
    except Forms.DoesNotExist:
        logger.error(f"Form with ID {form_id} not found")
        return []


def job_generate_data_download_result(task):
    job = Jobs.objects.get(task_id=task.id)
    job.attempt = job.attempt + 1
    if task.success:
        job.status = JobStatus.done
        job.available = timezone.now()
    else:
        job.status = JobStatus.failed
    job.save()


def seed_data_job(job_id):
    try:
        job = Jobs.objects.get(pk=job_id)
        seed_excel_data(job)
    except (ValueError, OSError, NameError, TypeError):
        print("Error seed data job")
        return False
    except Exception as unknown_error:
        print("Unknown error seed data job", unknown_error)
        return False
    return True


def seed_data_job_result(task):
    job = Jobs.objects.get(task_id=task.id)
    job.attempt = job.attempt + 1
    is_super_admin = job.user.is_superuser
    if task.result:
        job.status = JobStatus.done
        job.available = timezone.now()
        form_id = job.info.get("form")
        form = Forms.objects.filter(pk=int(form_id)).first()
        file = job.info.get("file")
        storage.download(f"upload/{file}")
        df = pd.read_excel(f"./tmp/{file}", sheet_name="data")
        subject = (
            "New Data Uploaded"
            if is_super_admin
            else "New Request @{0}".format(job.user.get_full_name())
        )
        data = {
            "subject": subject,
            "title": "New Data Submission",
            "send_to": [job.user.email],
            "listing": [
                {
                    "name": "Upload Date",
                    "value": job.created.strftime("%m-%d-%Y, %H:%M:%S"),
                },
                {"name": "Questionnaire", "value": form.name},
                {"name": "Number of Records", "value": df.shape[0]},
            ],
            "is_super_admin": is_super_admin,
        }
        send_email(context=data, type=EmailTypes.new_request)
    else:
        job.status = JobStatus.failed
    job.save()


def validate_excel(job_id):
    job = Jobs.objects.get(pk=job_id)
    storage.download(f"upload/{job.info.get('file')}")
    data = validate(
        job.info.get("form"),
        job.info.get("administration"),
        f"./tmp/{job.info.get('file')}",
    )

    if len(data):
        form_id = job.info.get("form")
        form = Forms.objects.filter(pk=int(form_id)).first()
        file = job.info.get("file")
        df = pd.read_excel(f"./tmp/{file}", sheet_name="data")
        error_list = pd.DataFrame(data)
        error_list = error_list[
            list(filter(lambda x: x != "error", list(error_list)))
        ]
        error_file = f"./tmp/error-{job_id}.csv"
        error_list.to_csv(error_file, index=False)
        data = {
            "send_to": [job.user.email],
            "listing": [
                {
                    "name": "Upload Date",
                    "value": job.created.strftime("%m-%d-%Y, %H:%M:%S"),
                },
                {"name": "Questionnaire", "value": form.name},
                {"name": "Number of Records", "value": df.shape[0]},
            ],
        }
        send_email(
            context=data,
            type=EmailTypes.upload_error,
            path=error_file,
            content_type="text/csv",
        )
        return False
    return True


def validate_excel_result(task):
    job = Jobs.objects.get(task_id=task.id)
    job.attempt = job.attempt + 1
    job_info = job.info
    if task.result:
        job.status = JobStatus.done
        job.available = timezone.now()
        job.save()
        job_info.update({"ref_job_id": job.id})
        new_job = Jobs.objects.create(
            result=job.info.get("file"),
            type=JobTypes.seed_data,
            status=JobStatus.on_progress,
            user=job.user,
            info=job_info,
        )
        task_id = async_task(
            "api.v1.v1_jobs.job.seed_data_job",
            new_job.id,
            hook="api.v1.v1_jobs.job.seed_data_job_result",
        )
        new_job.task_id = task_id
        new_job.save()
    else:
        job.status = JobStatus.failed
        job.save()


def handle_administrations_bulk_upload(filename, user_id, upload_time):
    user = SystemUser.objects.get(id=user_id)
    storage.download(f"upload/{filename}")
    file_path = f"./tmp/{filename}"
    errors = validate_administrations_bulk_upload(file_path)
    xlsx = pd.ExcelFile(file_path)
    if "data" not in xlsx.sheet_names:
        logger.error(f"Sheet 'data' not found in {filename}")
        send_email(
            context={
                "send_to": [user.email],
                "listing": [
                    {
                        "name": "Upload Date",
                        "value": upload_time.strftime("%m-%d-%Y, %H:%M:%S"),
                    },
                    {
                        "name": "Questionnaire",
                        "value": "Administrative List",
                    },
                    {
                        "name": "Error",
                        "value": 'Sheet "data" not found',
                    },
                ],
            },
            type=EmailTypes.upload_error,
        )
        return
    df = pd.read_excel(file_path, sheet_name="data")
    email_context = {
        "send_to": [user.email],
        "listing": [
            {
                "name": "Upload Date",
                "value": upload_time.strftime("%m-%d-%Y, %H:%M:%S"),
            },
            {
                "name": "Questionnaire",
                "value": "Administrative List",
            },
            {"name": "Number of Records", "value": df.shape[0]},
        ],
    }
    if len(errors):
        logger.error(errors)
        error_file = (
            "./tmp/administration-error-"
            f"{upload_time.strftime('%Y%m%d%H%M%S')}-{user.id}.csv"
        )
        error_list = pd.DataFrame(errors)
        error_list.to_csv(error_file, index=False)
        send_email(
            context=email_context,
            type=EmailTypes.upload_error,
            path=error_file,
            content_type="text/csv",
        )
        return
    seed_administration_data(file_path)
    generate_sqlite(Administration)
    send_email(context=email_context, type=EmailTypes.administration_upload)


def handle_master_data_bulk_upload_failure(task: Task):
    if task.success:
        return
    logger.error(
        {
            "error": "Failed running background job",
            "id": task.id,
            "name": task.name,
            "started": task.started,
            "stopped": task.stopped,
            "args": task.args,
            "kwargs": task.kwargs,
            "body": task.result,
        }
    )


def handle_entities_error_upload(
    errors: list,
    email_context: dict,
    user: SystemUser,
    upload_time: timezone.datetime,
):
    logger.error(errors)
    error_file = (
        "./tmp/entity-error-"
        f"{upload_time.strftime('%Y%m%d%H%M%S')}-{user.id}.csv"
    )
    error_list = pd.DataFrame(errors)
    error_list.to_csv(error_file, index=False)
    send_email(
        context=email_context,
        type=EmailTypes.upload_error,
        path=error_file,
        content_type="text/csv",
    )


def handle_entities_bulk_upload(filename, user_id, upload_time):
    user = SystemUser.objects.get(id=user_id)
    storage.download(f"upload/{filename}")
    file_path = f"./tmp/{filename}"
    errors = validate_entity_file(file_path)
    email_context = {
        "send_to": [user.email],
        "listing": [
            {
                "name": "Upload Date",
                "value": upload_time.strftime("%m-%d-%Y, %H:%M:%S"),
            },
            {
                "name": "Questionnaire",
                "value": "Entity List",
            },
        ],
    }
    if len(errors):
        handle_entities_error_upload(errors, email_context, user, upload_time)
        return
    errors = validate_entity_data(file_path)
    if len(errors):
        handle_entities_error_upload(errors, email_context, user, upload_time)
        return
    generate_sqlite(EntityData)
