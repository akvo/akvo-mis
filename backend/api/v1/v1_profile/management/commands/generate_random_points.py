import csv
import json
from mis.settings import COUNTRY_NAME
from django.core.management.base import BaseCommand


def decode_arcs(topo: dict) -> list:
    """Decode TopoJSON delta-encoded arcs into absolute quantized coords."""
    arcs = []
    for arc in topo["arcs"]:
        points, x, y = [], 0, 0
        for dx, dy in arc:
            x += dx
            y += dy
            points.append((x, y))
        arcs.append(points)
    return arcs


def geometry_points(geometry: dict, arcs: list) -> list:
    """Collect every quantized coordinate of a (Multi)Polygon geometry."""
    def arc_coords(idx):
        return arcs[idx] if idx >= 0 else list(reversed(arcs[~idx]))

    if geometry["type"] == "Polygon":
        polygons = [geometry["arcs"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["arcs"]
    else:
        return []
    points = []
    for polygon in polygons:
        for ring in polygon:
            for idx in ring:
                points.extend(arc_coords(idx))
    return points


def leaf_name(properties: dict):
    """Return the deepest "<alias>_<level>" value, e.g. Islet_2 -> name."""
    keys = [
        key for key in properties
        if key.split("_")[-1].isdigit() and not key.startswith("code_")
    ]
    if not keys:
        return None
    deepest = max(keys, key=lambda key: int(key.split("_")[-1]))
    return properties.get(deepest)


# Small deterministic offsets so each area yields a few distinct points.
JITTERS = [(0, 0), (0.01, 0.01), (-0.01, -0.01)]


class Command(BaseCommand):
    help = (
        "Generates a <country>_random_points.csv from the TopoJSON, "
        "using each leaf administration's centroid. Consumed by "
        "fake_complete_data_seeder."
    )

    def handle(self, *args, **options):
        topojson_path = f"./source/{COUNTRY_NAME}.topojson"
        output_path = f"./source/{COUNTRY_NAME}_random_points.csv"
        with open(topojson_path, "r") as f:
            topo = json.load(f)
        scale = topo["transform"]["scale"]
        translate = topo["transform"]["translate"]
        arcs = decode_arcs(topo)

        rows = []
        pid = 0
        # Only leaf features carry the deepest alias key, so non-leaf
        # layers (e.g. ADM0/ADM1) are skipped by leaf_name returning None.
        for obj in topo["objects"].values():
            for geometry in obj.get("geometries", []):
                name = leaf_name(geometry["properties"])
                if not name:
                    continue
                points = geometry_points(geometry, arcs)
                if not points:
                    continue
                cx = sum(p[0] for p in points) / len(points)
                cy = sum(p[1] for p in points) / len(points)
                lng = cx * scale[0] + translate[0]
                lat = cy * scale[1] + translate[1]
                pid += 1
                for d_lng, d_lat in JITTERS:
                    rows.append((
                        pid,
                        name,
                        round(lng + d_lng, 10),
                        round(lat + d_lat, 10),
                    ))

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "X", "Y"])
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(
            f"Wrote {len(rows)} points for {pid} areas to {output_path}"
        ))
