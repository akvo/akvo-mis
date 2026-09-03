from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_visualization.functions import (
    get_base_monitoring_qs,
    get_monitoring_data_ids,
)


def _answer_map(data_ids, question):
    """Map data_id -> numeric value for one question."""
    return dict(
        Answers.objects.filter(
            data_id__in=data_ids,
            question_id=question.id,
            value__isnull=False,
        ).values_list("data_id", "value")
    )


def handle_scatter(form, question_x, question_y, params):
    """Return per-datapoint X/Y values for a scatter chart.

    Either axis question can be None, meaning "number of datapoints"
    (each point gets value 1 on that axis).
    Points missing the non-null axis answer are dropped.
    """
    qs, is_latest, _ = get_base_monitoring_qs(
        form, form.id, params
    )
    data_ids = get_monitoring_data_ids(qs, is_latest)

    if is_latest:
        name_map = dict(qs.values_list("latest_id", "name"))
    else:
        name_map = dict(
            FormData.objects.filter(
                id__in=data_ids,
            ).values_list("id", "name")
        )

    if question_x:
        x_map = _answer_map(data_ids, question_x)
    else:
        x_map = {did: 1 for did in data_ids}

    if question_y:
        y_map = _answer_map(data_ids, question_y)
    else:
        y_map = {did: 1 for did in data_ids}

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
