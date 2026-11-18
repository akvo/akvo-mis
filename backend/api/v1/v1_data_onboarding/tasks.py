import json
import logging

from django.conf import settings

from api.v1.v1_data_onboarding.apply import apply_proposal
from api.v1.v1_data_onboarding.constants import DataOnboardingStatus
from api.v1.v1_data_onboarding.models import DataOnboarding
from api.v1.v1_data_onboarding.profile import (
    OnboardingError,
    profile_sheets,
    read_sheets,
)
from api.v1.v1_data_onboarding.proposal import SCHEMA, validate_proposal
from utils.email_helper import EmailTypes, send_email
from utils.storage import download
from utils.tenant_host import tenant_web_url

logger = logging.getLogger(__name__)

INSTRUCTIONS = """\
You help load a spreadsheet into Akvo MIS, a data collection system.
You get a profile of the file: per sheet, its columns with an inferred
type, counts and a value shape. Only category-like columns list their
values; you never see other cell values.

Draft a Proposal:
- administration: level names from the root down, the sheet and columns
  that hold the location (one column per level below the root), units
  to add as paths of names below the root, and spelling aliases. Use
  only names that appear in the listed values.
- forms: one registration form per entity sheet, monitoring forms for
  repeated visits (parent = the registration form key). A registration
  form has exactly one administration question (type cascade, extra
  {"type": "administration"}) and at least one meta question that names
  the record. Question names are lowercase snake_case and unique in a
  form. Option and multiple_option questions list their options.
- data: per sheet, the form it loads, key columns that identify a
  record, administration columns, geo columns, the column feeding each
  question, value maps from raw values to option labels (only for
  columns whose values are listed), the date format (strptime) when
  dates are not ISO, the multi-select separator, and every column not
  loaded with the reason.
- notes: the decisions you made, in plain words for a non-technical
  reader.
"""


def _ask_openai(profile):
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise OnboardingError("OpenAI is not configured.")
    from openai import OpenAI
    import httpx

    client = OpenAI(api_key=api_key, timeout=httpx.Timeout(300.0))
    response = client.chat.completions.create(
        model=settings.DATA_ONBOARDING_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": json.dumps(profile)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "proposal", "schema": SCHEMA, "strict": True,
            },
        },
        temperature=0.2,
        max_tokens=16000,
    )
    return response.choices[0].message.content


def draft_proposal(onboarding_id):
    onboarding = DataOnboarding.objects.get(id=onboarding_id)
    try:
        onboarding.profile = profile_sheets(
            read_sheets(download(onboarding.file), onboarding.file_name)
        )
        try:
            proposal = json.loads(_ask_openai(onboarding.profile) or "")
        except ValueError:
            raise OnboardingError("OpenAI did not return a Proposal.")
        errors = validate_proposal(proposal, onboarding.profile)
        if errors:
            raise OnboardingError(
                "The draft did not match the Proposal format: "
                + "; ".join(errors[:10])
            )
        onboarding.proposal = proposal
        onboarding.status = DataOnboardingStatus.proposed
    except OnboardingError as exc:
        onboarding.status = DataOnboardingStatus.failed
        onboarding.error = str(exc)
    except Exception:
        logger.exception("Data Onboarding %s: drafting failed", onboarding_id)
        onboarding.status = DataOnboardingStatus.failed
        onboarding.error = "The Proposal could not be drafted. Try again."
    onboarding.save()


def draft_proposal_result(task):
    # The task itself records failures; this catches a killed or crashed
    # worker, which would otherwise leave the record drafting forever.
    if not task.success:
        DataOnboarding.objects.filter(
            id=task.args[0], status=DataOnboardingStatus.drafting
        ).update(
            status=DataOnboardingStatus.failed,
            error="The Proposal could not be drafted. Try again.",
        )


def apply_onboarding(onboarding_id):
    onboarding = DataOnboarding.objects.get(id=onboarding_id)
    try:
        onboarding.report = apply_proposal(
            onboarding.proposal, download(onboarding.file),
            onboarding.file_name, onboarding.tenant, onboarding.created_by,
        )
        onboarding.status = DataOnboardingStatus.applied
    except OnboardingError as exc:
        onboarding.status = DataOnboardingStatus.failed
        onboarding.error = str(exc)
    except Exception:
        logger.exception("Data Onboarding %s: Apply failed", onboarding_id)
        onboarding.status = DataOnboardingStatus.failed
        onboarding.error = "The Proposal could not be applied."
    onboarding.save()
    if onboarding.status == DataOnboardingStatus.applied:
        _email_report(onboarding)


def _email_report(onboarding):
    report = onboarding.report
    issues = report["issues"]
    user = onboarding.created_by
    url = (
        f"{tenant_web_url(onboarding.tenant)}"
        f"/control-center/data-onboarding/{onboarding.id}"
    )
    send_email(
        context={
            "send_to": [user.email],
            "user": user,
            "tenant": onboarding.tenant,
            "file_name": onboarding.file_name,
            "listing": [
                {"name": f["name"], "value": f["loaded"]}
                for f in report["forms"]
            ] + [
                {"name": "Skipped rows", "value": len(
                    {(i["sheet"], i["row"]) for i in issues
                     if i["kind"] == "skipped"}
                )},
                {"name": "Dropped answers", "value": sum(
                    i["kind"] == "warning" for i in issues
                )},
            ],
            "button": True,
            "button_url": url,
            "button_text": "View the Onboarding Report",
        },
        type=EmailTypes.data_onboarding_applied,
    )


def apply_onboarding_result(task):
    # As draft_proposal_result: a killed worker must not leave it applying.
    if not task.success:
        DataOnboarding.objects.filter(
            id=task.args[0], status=DataOnboardingStatus.applying
        ).update(
            status=DataOnboardingStatus.failed,
            error="The Proposal could not be applied.",
        )
