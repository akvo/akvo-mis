"""
Seeder Data Processing Module

This module provides data processing functionality for Flow Complete Seeder.
"""

import logging
from typing import Dict, Optional, Any, List, Tuple

import pandas as pd

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import QuestionTypes, Forms

from .seeder_config import (
    CsvColumns,
    SeederConfig,
    FLOW_PREFIX,
)
from .seeder_answer_processor import AnswerProcessor

logger = logging.getLogger(__name__)


# =============================================================================
# Data Processing - UNIFIED GENERIC METHODS
# =============================================================================


def process_data_rows(
    df: pd.DataFrame,
    config: SeederConfig,
    questions: Dict[int, Any],
    administration_id: int,
    parent: Optional[FormData] = None,
    is_parent: bool = True,
    existing_records: Optional[Dict[int, int]] = [],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generic method to process data rows (parent or child).

    This unified method eliminates code duplication by handling both parent
    and child record processing with parameterization.

    Args:
        df: DataFrame containing rows to process
        config: SeederConfig instance
        questions: Dictionary mapping question ID to Question object
        administration_id: Administration ID for all rows
        parent: Parent FormData (for child records only)
        is_parent: Whether processing parent records
        existing_records: Dict mapping flow_data_id to mis_data_id

    Returns:
        List of dictionaries containing flow_data_id and mis_data_id
    """
    answer_processor = AnswerProcessor()
    seeded_records = []
    invalid_answers = []

    for _, row in df.iterrows():
        try:
            # Prepare and create answers
            answers, row_invalid_answers = prepare_answer_data(
                row=row,
                questions=questions,
                administration_id=administration_id,
                answer_processor=answer_processor,
            )

            # Create child FormData
            datapoint_id = str(row[CsvColumns.DATAPOINT_ID])
            parent_pk = parent.pk if parent else None

            # Find matching existing record
            matching = [
                er for er in (existing_records or [])
                if datapoint_id in er.name and er.parent_id == parent_pk
            ]

            existing_record = matching[0] if matching else None
            form_data = create_form_data(
                row=row,
                user=config.user,
                administration_id=administration_id,
                parent=parent,
                existing_record=existing_record,
            )

            if not form_data:
                continue

            is_incomplete = True
            if len(answers):
                # Pass row_invalid_answers to
                # filter out records with existing answers
                bulk_create_answers(
                    form_data, answers, config.user, row_invalid_answers
                )
                is_incomplete = False

            # Extend invalid_answers after filtering by bulk_create_answers
            invalid_answers.extend(row_invalid_answers)

            seeded_records.append(
                {
                    "flow_data_id": row[CsvColumns.DATAPOINT_ID],
                    "mis_data_id": form_data.pk,
                    "is_new": existing_record is None,
                    "is_incomplete": is_incomplete,
                }
            )

        except Exception as e:
            logger.error(
                f"Error processing {'parent' if is_parent else 'child'} "
                f"row {row[CsvColumns.DATAPOINT_ID]}: {e}"
            )
            logger.exception(
                f"Error processing {'parent' if is_parent else 'child'} "
                f"row {row[CsvColumns.DATAPOINT_ID]}"
            )
            continue

    return seeded_records, invalid_answers


def process_child_data_for_parent(
    parent_row: pd.Series,
    config: SeederConfig,
    parent_form_data: FormData,
    child_data_groups_dict: Dict[int, pd.core.groupby.DataFrameGroupBy],
    child_questions_dict: Dict[int, Dict[int, Any]],
    existing_records: Optional[List[FormData]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Process all child rows for a given parent across multiple child forms.

    Supports multiple child forms where each child form has its own grouped
    DataFrame and questions.

    Args:
        parent_row: Parent row containing datapoint_id
        config: SeederConfig instance
        parent_form_data: Parent FormData instance
        child_data_groups_dict: Dict mapping form_id to grouped child dataframe
        child_questions_dict: Dict mapping form_id to questions
        existing_records: Optional list of existing child records

    Returns:
        Tuple of (results_list, invalid_answers_list)
    """
    # Use parent's datapoint_id to match children to parent
    # In Akvo Flow, monitoring submissions reference parent via
    # the 'parent' column (parent's datapoint_id), not identifier
    parent_datapoint_id = parent_row[CsvColumns.DATAPOINT_ID]
    all_results = []
    all_invalid = []

    for form_id, child_data_groups in child_data_groups_dict.items():
        child_questions = child_questions_dict.get(form_id, {})

        try:
            child_rows = child_data_groups.get_group(parent_datapoint_id)
        except KeyError:
            # No child rows for this parent in this form
            continue

        # Filter existing records for this form
        form_existing_records = [
            r for r in (existing_records or [])
            if r.form_id == form_id
        ] if existing_records else None

        # Use generic process_data_rows method
        results, invalid = process_data_rows(
            df=child_rows,
            config=config,
            questions=child_questions,
            administration_id=parent_form_data.administration_id,
            parent=parent_form_data,
            is_parent=False,
            existing_records=form_existing_records,
        )

        # Add form_id to results for tracking
        for result in results:
            result['form_id'] = form_id

        all_results.extend(results)
        all_invalid.extend(invalid)

    return all_results, all_invalid


# =============================================================================
# Form Data Creation - GENERIC METHOD
# =============================================================================


def create_form_data(
    row: pd.Series,
    user,
    administration_id: int,
    parent: Optional[FormData] = None,
    existing_record: Optional[FormData] = None,
) -> Optional[FormData]:
    """Generic method to create FormData instance (parent or child).

    Args:
        row: Pandas Series containing row data
        user: User creating the record
        administration_id: Administration ID
        parent: Parent FormData (for child records only)

    Returns:
        Created or updated FormData instance or None if failed
    """
    try:
        geo_value = None
        uuid_value = row[CsvColumns.IDENTIFIER]
        if CsvColumns.GEO in row and pd.notna(row[CsvColumns.GEO]):
            geo_value = [
                float(g) for g in
                str(row[CsvColumns.GEO]).split("|")
            ]
        if parent and not geo_value:
            geo_value = parent.geo
            uuid_value = parent.uuid

        flow_data_id = int(row[CsvColumns.DATAPOINT_ID])

        # Sanitize name by replacing pipe characters
        dp_name = row[CsvColumns.NAME].replace("|", " - ")
        # Add FLOW-{flow_data_id} prefix to name
        dp_name = f"{FLOW_PREFIX}{flow_data_id} - {dp_name}"

        # Check if record already exists
        if existing_record:
            # Update existing record
            existing_record.name = dp_name
            existing_record.administration_id = administration_id
            existing_record.geo = geo_value
            existing_record.submitter = row.get(CsvColumns.SUBMITTER, None)
            if parent:
                existing_record.parent = parent
            existing_record.save()
            logger.info(
                f"Updated existing FormData {existing_record.pk} "
                f"for flow_data_id {flow_data_id}"
            )
            return existing_record

        # Create new record
        new_data_id = None
        if not parent and flow_data_id:
            new_data_id = flow_data_id
        data = FormData.objects.create(
            id=new_data_id,
            form_id=row[CsvColumns.FORM_ID],
            uuid=uuid_value,
            name=dp_name,
            administration_id=administration_id,
            geo=geo_value,
            created_by=user,
            parent=parent,
            submitter=row.get(CsvColumns.SUBMITTER, None),
        )
        # Set created timestamp from source data
        data.created = row[CsvColumns.CREATED_AT]
        data.save()
        logger.info(
            f"Created new FormData {data.pk} "
            f"for flow_data_id {flow_data_id}"
        )
        # Save to datapoint json file if parent is None (Registration)
        if data.parent is None:
            data.save_to_file
        return data
    except Exception as e:
        logger.error(
            f"Error creating/updating FormData for row "
            f"{row[CsvColumns.DATAPOINT_ID]}: {e}"
        )
        return None


# =============================================================================
# Form Data Deletion (Reverting) - GENERIC METHODS
# =============================================================================

def revert_form_data(
    form: Forms
) -> int:
    """Generic method to revert all FormData for a given form.

    Args:
        form: Forms instance
    """
    form_data = form.form_form_data.filter(
        name__startswith=FLOW_PREFIX,
    )
    total_data = form_data.count()
    for data in form_data.all():
        data.children.all().delete(hard=True)
        data.delete(hard=True)
    return total_data + sum([d.children.count() for d in form_data.all()])

# =============================================================================
# Answer Processing - GENERIC METHODS
# =============================================================================


def prepare_answer_data(
    row: pd.Series,
    questions: Dict[int, Any],
    administration_id: Optional[int],
    answer_processor: AnswerProcessor,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generic method to prepare answer data from a data row.

    This method works for both parent and child data without modification.

    Args:
        row: Pandas Series containing row data
        questions: Dictionary mapping question ID to Question object
        administration_id: Administration ID for admin-type questions
        answer_processor: AnswerProcessor instance

    Returns:
        List of dictionaries containing answer data
    """
    answer_records = []
    invalid_answers = []

    for question_id, question in questions.items():
        column_name = str(question_id)

        # Skip if value is NaN
        if pd.isna(row.get(column_name)):
            continue

        row_value = row[column_name]

        # Process answer based on question type
        opt_list = []
        if question.type in [
            QuestionTypes.option,
            QuestionTypes.multiple_option,
        ]:
            opt_list = question.options.values_list("value", flat=True)
            opt_list = list(opt_list)

        name, value, options = answer_processor.process(
            question_type=question.type,
            row_value=row_value,
            administration_id=administration_id,
            opt_list=opt_list,
            extra=question.extra,
        )

        if name is None and value is None and options is None:
            invalid_answers.append({
                "mis_form_id": question.form_id,
                "mis_question_id": question.pk,
                "mis_question_type": QuestionTypes.FieldStr[question.type],
                "flow_data_id": row[CsvColumns.DATAPOINT_ID],
                "value": row_value,
            })
            # Skip invalid answer
            continue

        answer_records.append(
            {
                "question_id": question.pk,
                "name": name,
                "value": value,
                "options": options,
            }
        )

    return answer_records, invalid_answers


def bulk_create_answers(
    data: FormData,
    answer_records: List[Dict[str, Any]],
    user,
    invalid_records: Optional[List[Dict[str, Any]]] = None,
):
    """Generic method to bulk create or update answer records.

    Works for both parent and child FormData instances.
    Updates existing answers instead of deleting them to preserve
    manual input answers that are not in the seeder data.

    Args:
        data: FormData instance (parent or child)
        answer_records: List of answer data dictionaries
        user: User creating the answers
        invalid_records: Optional list of invalid answers to filter.
            Records are removed if the question already has an existing answer.
            Expected format: {"mis_question_id": int, ...}
    """
    # Get existing answers indexed by question_id
    existing_answers = {
        answer.question_id: answer
        for answer in data.data_answer.all()
    }

    # Filter out invalid_records if question already has existing answer
    if invalid_records is not None:
        invalid_records[:] = [
            r for r in invalid_records
            if r.get("mis_question_id") not in existing_answers
        ]

    if not answer_records:
        return

    AnswerModel = data.data_answer.model

    answers_to_create = []
    answers_to_update = []

    for a in answer_records:
        question_id = a["question_id"]

        if question_id in existing_answers:
            # Update existing answer
            existing = existing_answers[question_id]
            existing.value = a["value"]
            existing.options = a["options"]
            existing.name = a["name"]
            existing.created_by = user
            answers_to_update.append(existing)
        else:
            # Create new answer
            answers_to_create.append(
                AnswerModel(
                    data=data,
                    question_id=question_id,
                    value=a["value"],
                    options=a["options"],
                    name=a["name"],
                    created_by=user,
                )
            )

    # Bulk update existing answers
    if answers_to_update:
        AnswerModel.objects.bulk_update(
            answers_to_update,
            fields=["value", "options", "name", "created_by"]
        )

    # Bulk create new answers
    if answers_to_create:
        data.data_answer.bulk_create(answers_to_create)
