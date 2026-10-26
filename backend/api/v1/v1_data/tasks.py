from django.utils import timezone
from api.v1.v1_data.models import FormData
from django.conf import settings
from api.v1.v1_visualization.functions import refresh_materialized_data


def seed_approved_data(data: FormData):
    """
    Update FormData object from pending status to approved status
    """
    # No need to create new data, just update existing FormData
    data.updated = timezone.now()
    data.is_pending = False
    data.save()

    # Save to file after approval
    if not data.form.parent and not settings.TEST_ENV:
        # If the form is a parent form, save to file
        data.save_to_file
    # Refresh materialized view after saving data
    refresh_materialized_data()

    return data


def finalize_batch_approval(batch_id: int):
    """Run post-approval side-effects once per batch.

    is_pending is flipped synchronously at approval time, so this only
    handles the heavy work: export registration datapoints to file and
    refresh the materialized views a single time. Doing it per batch
    instead of per datapoint avoids the DB connection storm (one full
    materialized view refresh per approved record) that previously
    exhausted PostgreSQL connection slots and failed the approval seed.
    """
    # Imported here to avoid a circular import at module load.
    from api.v1.v1_approval.models import DataBatchList

    data_list = DataBatchList.objects.filter(
        batch_id=batch_id
    ).select_related("data__form")
    if not settings.TEST_ENV:
        for dl in data_list:
            if not dl.data.form.parent:
                dl.data.save_to_file
    refresh_materialized_data()
