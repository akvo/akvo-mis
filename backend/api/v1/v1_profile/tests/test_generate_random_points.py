from django.test import SimpleTestCase

from api.v1.v1_profile.management.commands.generate_random_points import (
    decode_arcs,
    geometry_points,
    leaf_name,
)


class GenerateRandomPointsHelpersTestCase(SimpleTestCase):
    def test_decode_arcs_accumulates_deltas(self):
        topo = {"arcs": [[[1, 1], [2, 3], [-1, 0]]]}
        # 1,1 -> +2,+3 -> -1,0 (cumulative)
        self.assertEqual(decode_arcs(topo), [[(1, 1), (3, 4), (2, 4)]])

    def test_geometry_points_polygon(self):
        arcs = [[(0, 0), (2, 2)]]
        geometry = {"type": "Polygon", "arcs": [[0]]}
        self.assertEqual(geometry_points(geometry, arcs), [(0, 0), (2, 2)])

    def test_geometry_points_negative_index_is_reversed(self):
        arcs = [[(0, 0), (2, 2)]]
        # ~(-1) == 0, and the arc is traversed in reverse
        geometry = {"type": "Polygon", "arcs": [[-1]]}
        self.assertEqual(geometry_points(geometry, arcs), [(2, 2), (0, 0)])

    def test_geometry_points_multipolygon(self):
        arcs = [[(0, 0)], [(5, 5)]]
        geometry = {"type": "MultiPolygon", "arcs": [[[0]], [[1]]]}
        self.assertEqual(geometry_points(geometry, arcs), [(0, 0), (5, 5)])

    def test_geometry_points_unsupported_type(self):
        self.assertEqual(geometry_points({"type": "Point"}, []), [])

    def test_leaf_name_picks_deepest_alias(self):
        properties = {
            "National_0": "Country",
            "Municipality_1": "Muni",
            "Islet_2": "Islet",
            "code_2": "MH0114",
            "Shape_Area": 0.1,
        }
        self.assertEqual(leaf_name(properties), "Islet")

    def test_leaf_name_ignores_code_keys(self):
        # Only code_<level> keys present -> no alias path.
        self.assertIsNone(leaf_name({"code_0": "MH", "ADM0_EN": "X"}))

    def test_leaf_name_returns_none_without_alias_keys(self):
        self.assertIsNone(leaf_name({"ADM0_EN": "X", "ADM0_PCODE": "MH"}))
