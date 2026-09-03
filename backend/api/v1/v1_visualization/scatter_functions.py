from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_visualization.functions import (
    get_base_monitoring_qs,
    get_monitoring_data_ids,
)


def handle_scatter(form, question_x, question_y, params):
    """Return per-datapoint X/Y values for a scatter chart.

    Each point is one datapoint (or one latest monitoring submission),
    with the numeric answer to question_x as x and question_y as y.
    Points missing either answer are dropped.
    """
    qs, is_latest, _ = get_base_monitoring_qs(
        form, form.id, params
    )
    data_ids = get_monitoring_data_ids(qs, is_latest)

    x_map = dict(
        Answers.objects.filter(
            data_id__in=data_ids,
            question_id=question_x.id,
            value__isnull=False,
        ).values_list("data_id", "value")
    )

    y_map = dict(
        Answers.objects.filter(
            data_id__in=data_ids,
            question_id=question_y.id,
            value__isnull=False,
        ).values_list("data_id", "value")
    )

    if is_latest:
        name_map = dict(qs.values_list("latest_id", "name"))
    else:
        name_map = dict(
            FormData.objects.filter(
                id__in=data_ids,
            ).values_list("id", "name")
        )

    common_ids = set(x_map.keys()) & set(y_map.keys())
    data = [
        {
            "name": name_map.get(did, str(did)),
            "x": round(x_map[did], 2),
            "y": round(y_map[did], 2),
        }
        for did in sorted(common_ids)
    ]

    return data
