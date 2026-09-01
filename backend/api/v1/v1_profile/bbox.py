"""Bounding boxes stored as an administration attribute (SEED-003).

A unit's box is an ordinary `AdministrationAttribute` of type VALUE, holding
"minLng,minLat,maxLng,maxLat" as a string. Both the CSV importer (which
validates and writes it) and the fake data seeder (which reads it) go through
here, so there is one parser and one set of error messages.

See doc/design/SEED-tenant-aware-seeders.md.
"""
from random import uniform

from api.v1.v1_profile.constants import BBOX_ATTRIBUTE_NAME
from api.v1.v1_profile.models import (
    AdministrationAttribute,
    AdministrationAttributeValue,
)

BBOX_FORMAT = "minLng,minLat,maxLng,maxLat"


class BboxError(ValueError):
    """A bounding box that cannot be used.

    A plain ValueError subclass rather than CommandError so this module stays
    importable outside a management command; each caller wraps it in whatever
    its own error type is.
    """


def parse_bbox(raw):
    """'minLng,minLat,maxLng,maxLat' -> (floats), validated.

    Rejects rather than repairs. A box that is inverted or out of range is
    far more likely to be a column swapped at generation time than a real
    place, and a silently corrected one puts pins somewhere plausible-looking
    and wrong.
    """
    parts = [p.strip() for p in (raw or "").split(",")]
    if len(parts) != 4:
        raise BboxError(
            f"expected four numbers as '{BBOX_FORMAT}', got {raw!r}"
        )
    try:
        min_lng, min_lat, max_lng, max_lat = [float(p) for p in parts]
    except ValueError:
        raise BboxError(f"{raw!r} is not four numbers")
    if min_lng >= max_lng or min_lat >= max_lat:
        raise BboxError(
            "needs min < max on both axes; got "
            f"lng {min_lng}..{max_lng}, lat {min_lat}..{max_lat}"
        )
    if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180):
        raise BboxError("longitudes must be within -180..180")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise BboxError("latitudes must be within -90..90")
    return min_lng, min_lat, max_lng, max_lat


def random_point_in(bbox):
    """A [lat, lng] inside the bbox, in the order FormData.geo expects.

    Latitude first: the map widgets read geo[0] as latitude, so the order is
    load-bearing rather than cosmetic, and it is the opposite of the order the
    box itself is written in.
    """
    min_lng, min_lat, max_lng, max_lat = bbox
    return [uniform(min_lat, max_lat), uniform(min_lng, max_lng)]


def get_bbox_attribute(tenant, create=False):
    """The workspace's bounding-box attribute, or None.

    Scoped by tenant: attribute names are not globally unique, so an unscoped
    lookup would hand one workspace another's definition.
    """
    existing = AdministrationAttribute.objects.filter(
        name=BBOX_ATTRIBUTE_NAME, tenant=tenant
    ).first()
    if existing or not create:
        return existing
    return AdministrationAttribute.objects.create(
        name=BBOX_ATTRIBUTE_NAME,
        type=AdministrationAttribute.Type.VALUE,
        tenant=tenant,
    )


def format_bbox(bbox):
    """(floats) -> the stored string. Round-trips through parse_bbox."""
    return ",".join(f"{value:.6g}" for value in bbox)


def resolve_bbox(administration, attribute, cache=None):
    """The unit's own box, else the nearest ancestor's, else None.

    The ancestor walk is not decoration. Boxes are attached to the deepest
    unit of each CSV row (D-6), so a workspace that later gains a tier -- a
    3-tier import followed by an upload adding a 4th -- has target units one
    level below the boxes.

    `Administration.ancestors` is ordered root-first, so it is walked
    reversed to find the nearest one.
    """
    if attribute is None:
        return None
    if cache is None:
        cache = {}
    chain = [administration]
    if administration.path:
        chain += list(reversed(list(administration.ancestors or [])))
    for unit in chain:
        if unit.id in cache:
            if cache[unit.id] is not None:
                return cache[unit.id]
            continue
        value = AdministrationAttributeValue.objects.filter(
            administration=unit, attribute=attribute
        ).values_list("value", flat=True).first()
        bbox = None
        if value:
            try:
                bbox = parse_bbox((value or {}).get("value"))
            except BboxError:
                # A box edited into nonsense through the attribute manager
                # falls through to the ancestor rather than failing the run.
                bbox = None
        cache[unit.id] = bbox
        if bbox is not None:
            return bbox
    return None


__all__ = [
    "BBOX_FORMAT",
    "BboxError",
    "format_bbox",
    "get_bbox_attribute",
    "parse_bbox",
    "random_point_in",
    "resolve_bbox",
]
