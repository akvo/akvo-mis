import tempfile
from pathlib import Path

from django.test import SimpleTestCase
from openpyxl import Workbook

from api.v1.v1_jobs.management.commands.export_snapshot import (
    diff_workbooks,
)


def _workbook(path, rows, sheet="data"):
    book = Workbook()
    book.active.title = sheet
    for row in rows:
        book.active.append(row)
    book.save(path)
    return path


class DiffWorkbooksTest(SimpleTestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_identical_workbooks_have_no_differences(self):
        rows = [["name", "age"], ["Ana", 31]]
        a = _workbook(self.dir / "a.xlsx", rows)
        b = _workbook(self.dir / "b.xlsx", rows)
        self.assertEqual(diff_workbooks(a, b), [])

    def test_a_changed_cell_is_reported_with_its_row(self):
        a = _workbook(self.dir / "a.xlsx", [["age"], [31]])
        b = _workbook(self.dir / "b.xlsx", [["age"], [31.0001]])
        diffs = diff_workbooks(a, b)
        self.assertEqual(len(diffs), 1)
        self.assertIn("data!row 2", diffs[0])

    def test_a_dropped_row_is_reported(self):
        a = _workbook(self.dir / "a.xlsx", [["age"], [31], [40]])
        b = _workbook(self.dir / "b.xlsx", [["age"], [31]])
        self.assertIn("data: 3 rows != 2 rows", diff_workbooks(a, b))

    def test_renamed_sheets_are_reported(self):
        a = _workbook(self.dir / "a.xlsx", [["x"]], sheet="data")
        b = _workbook(self.dir / "b.xlsx", [["x"]], sheet="Data")
        self.assertEqual(
            diff_workbooks(a, b), ["sheets ['data'] != ['Data']"]
        )
