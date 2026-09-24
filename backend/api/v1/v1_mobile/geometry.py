"""Geometry payload for the device datapoint list (GEO-005).

The device turns this into a spatial index (GEO-006) and validates new
polygons against it (GEO-007). Two things here exist only to stop that
validation passing silently against an incomplete candidate set: the
strict gate below, and a count that ignores the sync cursor.

Scoping note, because it is easy to get wrong. `Answers.objects` is NOT
tenant-scoped. `TenantManager` leaves `get_queryset` alone and exposes an
opt-in `for_user()`, so filtering `Answers` by `form_id` or
`question_id` alone would cross tenants. Everything here is keyed on data
ids that originate in `FormData.objects.for_user(assignment.user)`. Keep
it that way.
"""

from api.v1.v1_data.models import Answers
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Questions


def enabled_geoshape_question_ids(form):
    """Geoshape questions on this form that opted into overlap detection.

    The gate is deliberately strict. GEO-010 now rejects `"true"` and
    `["true"]` at the write boundary, but rows written before it did are
    still out there, and this is the last thing standing between them and
    a silently incomplete candidate set. Anything that is not the real
    boolean means off. Failing open would hand the device a candidate set
    nobody promised was complete, which is the exact failure this
    feature exists to prevent.

    The `=True` lookup carries that strictness: Django encodes the
    right-hand side as JSON, so it matches `true` and not `"true"`,
    `["true"]`, `1` or a missing key.
    """
    return list(
        Questions.objects.filter(
            form=form,
            type=QuestionTypes.geoshape,
            extra__geoConfig__detectOverlaps=True,
        ).values_list("id", flat=True)
    )


def bounding_box(coordinates):
    """Bounding box of `[[lat, lon], ...]`, in the device's key names.

    Computed per request rather than stored. This is min and max over
    roughly 180 floats on a list the database has already handed us, and
    a stored column would need a "null means not yet computed" fallback
    on the device, which is one more way for validation to degrade
    quietly.

    Known limitation: a polygon crossing the antimeridian gets a bbox
    spanning the globe. Plot boundaries do not, and GEO-006's range
    queries could not use such a bbox anyway.

    Indexed rather than unpacked with `zip(*coordinates)`: since
    GEO-014 a vertex may carry a third element (GPS accuracy in metres),
    and `zip(*)` would raise `ValueError: too many values to unpack` on
    it - taking the whole form's datapoint-list response down rather
    than one row. Slicing off the first two axes is length-agnostic, so
    a ring that mixes walked and tapped vertices works too.
    """
    latitudes = [point[0] for point in coordinates]
    longitudes = [point[1] for point in coordinates]
    return {
        "min_lat": min(latitudes),
        "max_lat": max(latitudes),
        "min_lon": min(longitudes),
        "max_lon": max(longitudes),
    }


def accuracy_summary(coordinates):
    """Per-polygon accuracy for the list payload (GEO-014 D-10).

    Max of the measured vertex accuracies, plus whether any vertex was
    measured. Per-vertex readings stay on `{uuid}.json`; the list only
    needs the one number GEO-007's adaptive threshold reads.
    """
    measured = []
    for point in coordinates:
        if not isinstance(point, (list, tuple)) or len(point) < 3:
            continue
        value = point[2]
        if value is None:
            continue
        try:
            metres = float(value)
        except (TypeError, ValueError):
            continue
        if metres > 0:
            measured.append(metres)
    if not measured:
        return {"max": None, "measured": False}
    return {"max": max(measured), "measured": True}


def geometry_answers(data_ids, question_ids):
    """The one queryset both the payload and the count are built from.

    They have to describe the same set. A count that included a row the
    payload skipped would leave the device's comparison permanently
    unbalanced, so it would refuse to validate forever.

    `data_ids` may be a list of ids or an id-yielding queryset; both work
    with `__in`.

    Ordered so a datapoint's repeat-group entries arrive in the same
    sequence on every request. Postgres is free to return an unordered
    query's rows in any order it likes, and a device diffing two
    responses should not see a change that is not one.
    """
    return Answers.objects.filter(
        data_id__in=data_ids,
        question_id__in=question_ids,
    ).exclude(
        options__isnull=True
    ).exclude(options=[]).order_by("question_id", "index")


def geometry_by_data_id(data_ids, question_ids):
    """Map `{data_id: [geometry, ...]}` for one page of the list.

    One follow-up query keyed on the page's ids, never a join onto the
    paginated queryset: a join multiplies rows and corrupts `total` and
    `total_page`.

    Coordinates are deliberately absent (GEO-006 §4): they travel once
    in `{uuid}.json`. Duplicating them here doubled the page payload and
    risked an index row whose coordinates were not yet on the device.
    """
    result = {}
    rows = geometry_answers(data_ids, question_ids).values(
        "data_id", "question_id", "index", "options"
    )
    for row in rows:
        coordinates = row["options"]
        result.setdefault(row["data_id"], []).append({
            "question_id": row["question_id"],
            "index": row["index"],
            "bbox": bounding_box(coordinates),
            "accuracy": accuracy_summary(coordinates),
        })
    return result
