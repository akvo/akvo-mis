import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from api.v1.v1_data_onboarding.ambiguity import blocked_forms
from api.v1.v1_data_onboarding.apply import apply_proposal, check_hierarchy
from api.v1.v1_data_onboarding.constants import DataOnboardingStatus
from api.v1.v1_data_onboarding.models import DataOnboarding
from api.v1.v1_data_onboarding.places import drop_invented_aliases
from api.v1.v1_data_onboarding.profile import (
    OnboardingError,
    profile_sheets,
    read_sheets,
)
from api.v1.v1_data_onboarding.proposal import SCHEMA, validate_proposal
from api.v1.v1_users.models import SystemUser
from utils.email_helper import EmailTypes, send_email
from utils import storage
from utils.tenant_host import tenant_web_url

logger = logging.getLogger(__name__)

DRAFT_FAILED = "The Proposal could not be drafted. Try again."
REVISION_FAILED = "The Proposal could not be revised. Try again."
APPLY_FAILED = "The Proposal could not be applied."

INSTRUCTIONS = """\
You help load a spreadsheet into Akvo MIS, a data collection system.
You get a profile of the file: per sheet, its columns with an inferred
type, counts and a value shape. Only category-like columns list their
values; you never see other cell values.

Draft a Proposal:
- administration: level names from the root down, the sheet and columns
  that hold the location (one column per level below the root, top
  level first), and aliases from a misspelt unit name to the correct
  one, both among the listed values (not column names; you do not see
  the tenant's units, so never rename a place). MIS reads the units to
  add from the location columns.
- forms: one registration form per entity sheet, monitoring forms for
  repeated visits (parent = the registration form key). A registration
  form has exactly one administration question (type cascade, extra
  {"type": "administration"}) and at least one meta question that names
  the record. Question names are lowercase snake_case and unique in a
  form. Option and multiple_option questions list their options.
- data: per sheet, the form it loads, key columns that identify a
  record (for a visit sheet, these include the visit date), for a visit
  sheet the parent key columns that hold its registration record's key
  (empty otherwise), administration columns (the location columns, top
  level first; empty for visit sheets: visits take the location from
  their parent), geo columns, the column feeding each other question
  (never the administration question: it is fed by the administration
  columns), value maps from raw values to option labels (only for
  columns whose values are listed), the date format (strptime) when
  dates are not ISO, the characters that separate choices in a
  multi-select cell (each character splits on its own, e.g. ";,"), and
  every column not loaded with the reason.
- notes: the decisions you made, in plain words for a non-technical
  reader.
"""


REVISE = """
You now revise a Proposal you drafted. You get the profile, the current
Proposal and the user's instruction. Apply the instruction, keep the
rest of the Proposal as it is, and return the whole revised Proposal.
"""


def _ask_openai(instructions, content):
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise OnboardingError("OpenAI is not configured.")
    from openai import OpenAI
    import httpx

    client = OpenAI(api_key=api_key, timeout=httpx.Timeout(300.0))
    response = client.chat.completions.create(
        model=settings.DATA_ONBOARDING_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": json.dumps(content)},
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
    try:
        return json.loads(response.choices[0].message.content or "")
    except ValueError:
        raise OnboardingError("OpenAI did not return a Proposal.")


def store_proposal(onboarding, proposal, sheets, what, user,
                   resolutions=None):
    """Check the Proposal and keep it with its blocked forms (unsaved).

    Every draft, revision and edit goes through here, so the checks
    always run on what is stored, for the user acting now. resolutions
    replace the stored ones when given; a revision keeps them.
    """
    if resolutions is None:
        resolutions = onboarding.resolutions
    errors = validate_proposal(proposal, onboarding.profile)
    if errors:
        raise OnboardingError(
            f"The {what} did not match the Proposal format: "
            + "; ".join(errors[:10])
        )
    drop_invented_aliases(proposal, onboarding.profile, onboarding.tenant)
    refusal = check_hierarchy(proposal, onboarding.tenant, user)
    if refusal:
        raise OnboardingError(refusal)
    onboarding.blocked = blocked_forms(
        proposal, sheets, onboarding.tenant, user, resolutions,
    )
    onboarding.proposal, onboarding.resolutions = proposal, resolutions


def read_upload(onboarding):
    if not onboarding.file:
        raise OnboardingError(
            "The uploaded file has been deleted. Upload it again."
        )
    return read_sheets(
        storage.download(onboarding.file), onboarding.file_name
    )


def draft_proposal(onboarding_id):
    onboarding = DataOnboarding.objects.get(id=onboarding_id)
    try:
        sheets = read_upload(onboarding)
        onboarding.profile = profile_sheets(sheets)
        store_proposal(
            onboarding, _ask_openai(INSTRUCTIONS, onboarding.profile),
            sheets, "draft", onboarding.created_by,
        )
        onboarding.status = DataOnboardingStatus.proposed
    except OnboardingError as exc:
        onboarding.status = DataOnboardingStatus.failed
        onboarding.error = str(exc)
    except Exception:
        logger.exception("Data Onboarding %s: drafting failed", onboarding_id)
        onboarding.status = DataOnboardingStatus.failed
        onboarding.error = DRAFT_FAILED
    onboarding.save()


def revise_proposal(onboarding_id, instruction, user_id):
    # A failed revision keeps the previous Proposal and stays proposed.
    onboarding = DataOnboarding.objects.get(id=onboarding_id)
    user = SystemUser.objects.get(id=user_id)
    try:
        sheets = read_upload(onboarding)
        # Only the profile and the Proposal: resolutions and the blocked
        # findings hold file values and never go to OpenAI.
        store_proposal(onboarding, _ask_openai(INSTRUCTIONS + REVISE, {
            "profile": onboarding.profile,
            "proposal": onboarding.proposal,
            "instruction": instruction,
        }), sheets, "revision", user)
    except OnboardingError as exc:
        onboarding.error = str(exc)
    except Exception:
        logger.exception("Data Onboarding %s: revision failed", onboarding_id)
        onboarding.error = REVISION_FAILED
    onboarding.status = DataOnboardingStatus.proposed
    onboarding.save()


def revise_proposal_result(task):
    if not task.success:
        DataOnboarding.objects.filter(
            id=task.args[0], status=DataOnboardingStatus.drafting
        ).update(status=DataOnboardingStatus.proposed, error=REVISION_FAILED)


def draft_proposal_result(task):
    # The task itself records failures; this catches a killed or crashed
    # worker, which would otherwise leave the record drafting forever.
    if not task.success:
        DataOnboarding.objects.filter(
            id=task.args[0], status=DataOnboardingStatus.drafting
        ).update(
            status=DataOnboardingStatus.failed,
            error=DRAFT_FAILED,
        )


def apply_onboarding(onboarding_id, user_id, forms=None):
    # Checks, scope and the new data are the applying user's.
    onboarding = DataOnboarding.objects.get(id=onboarding_id)
    try:
        onboarding.report = apply_proposal(
            onboarding.proposal, storage.download(onboarding.file),
            onboarding.file_name, onboarding.tenant,
            SystemUser.objects.get(id=user_id),
            forms=forms, resolutions=onboarding.resolutions,
        )
        onboarding.status = DataOnboardingStatus.applied
    except OnboardingError as exc:
        onboarding.status = DataOnboardingStatus.failed
        onboarding.error = str(exc)
    except Exception:
        logger.exception("Data Onboarding %s: Apply failed", onboarding_id)
        onboarding.status = DataOnboardingStatus.failed
        onboarding.error = APPLY_FAILED
    onboarding.save()
    if onboarding.status == DataOnboardingStatus.applied:
        _email_report(onboarding)
    else:
        _email_failure(onboarding)


def _page_url(onboarding):
    return (
        f"{tenant_web_url(onboarding.tenant)}"
        f"/control-center/data-onboarding/{onboarding.id}"
    )


def _email_failure(onboarding):
    send_email(
        context={
            "send_to": [onboarding.created_by.email],
            "user": onboarding.created_by,
            "tenant": onboarding.tenant,
            "file_name": onboarding.file_name,
            "button": True,
            "button_url": _page_url(onboarding),
            "button_text": "Open the Data Onboarding",
        },
        type=EmailTypes.data_onboarding_failed,
    )


def _email_report(onboarding):
    report = onboarding.report
    issues = report["issues"]
    user = onboarding.created_by
    url = _page_url(onboarding)
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
    if not task.success and DataOnboarding.objects.filter(
        id=task.args[0], status=DataOnboardingStatus.applying
    ).update(
        status=DataOnboardingStatus.failed,
        error=APPLY_FAILED,
    ):
        _email_failure(DataOnboarding.objects.get(id=task.args[0]))


FILE_RETENTION = timedelta(days=14)


def purge_onboarding_files():
    # Scheduled (migration 0002). The upload holds personal data: keep it
    # only until Apply, or 14 days for a Proposal never applied. The
    # Proposal and Report hold no cell values and stay.
    for onboarding in DataOnboarding.objects.filter(
        Q(status=DataOnboardingStatus.applied)
        | Q(created__lt=timezone.now() - FILE_RETENTION),
        file__isnull=False,
    ):
        if storage.check(onboarding.file):
            storage.delete(onboarding.file)
        onboarding.file = None
        onboarding.save(update_fields=["file"])
