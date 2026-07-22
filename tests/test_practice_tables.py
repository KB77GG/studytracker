import json
import unittest
from pathlib import Path

from practice_tables import normalize_practice_table


ROOT = Path(__file__).resolve().parents[1]
TABLE_ROOTS = (
    ROOT / "static/reading_tests",
    ROOT / "static/reading_jijing",
    ROOT / "static/listening_tests",
    ROOT / "static/listening_jijing/parts",
)


def iter_tables(value):
    if isinstance(value, dict):
        if isinstance(value.get("table"), dict):
            yield value["table"]
        for child in value.values():
            yield from iter_tables(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_tables(child)


class PracticeTableNormalizerTests(unittest.TestCase):
    def test_vertical_merge_references_become_rowspans(self):
        payload = json.loads(
            (ROOT / "static/reading_tests/ielts4_test1_reading.json").read_text(encoding="utf-8")
        )
        table = payload["passages"][1]["groups"][0]["table"]
        rows = normalize_practice_table(table)["render"]["rows"]

        smell = rows[1][0]
        vision = rows[4][0]
        hearing = rows[10][0]
        self.assertEqual((smell["rowspan"], smell["colspan"]), (2, 1))
        self.assertEqual((vision["rowspan"], vision["colspan"]), (6, 1))
        self.assertEqual((hearing["rowspan"], hearing["colspan"]), (3, 1))
        self.assertFalse(any(cell["column_index"] == 0 for cell in rows[2]))

    def test_full_width_title_and_nested_header_are_normalized(self):
        title_table = {
            "content": [
                ["Course details"],
                ["Name", "Information", "Deadline"],
            ]
        }
        title_render = normalize_practice_table(title_table)["render"]
        self.assertEqual(title_render["column_count"], 3)
        self.assertEqual(title_render["rows"][0][0]["colspan"], 3)

        nested_table = {"content": [[["School Facility", "Information"]], ["Library", "Open"]]}
        nested_render = normalize_practice_table(nested_table)["render"]
        self.assertEqual(nested_render["column_count"], 2)
        self.assertEqual(
            [cell["text"] for cell in nested_render["rows"][0]],
            ["School Facility", "Information"],
        )
        self.assertTrue(all(cell["is_header"] for cell in nested_render["rows"][0]))
        self.assertTrue(all(cell["scope"] == "col" for cell in nested_render["rows"][0]))

    def test_header_row_after_a_spanning_title_uses_column_scope(self):
        table = {
            "content": [
                ["<bc>MEMBERSHIP SCHEMES</bc>", [0, 0]],
                ["<b>Type</b>", "<b>Cost</b>"],
            ]
        }
        rows = normalize_practice_table(table)["render"]["rows"]
        self.assertEqual(rows[0][0]["scope"], "colgroup")
        self.assertEqual([cell["scope"] for cell in rows[1]], ["col", "col"])

    def test_shifted_full_row_references_use_current_row_origin(self):
        table = {
            "content": [
                ["Name", "Size", "Price"],
                ["Roadster", "large", "£30"],
                ["Prices include tax", [1, 1], [1, 2]],
            ]
        }
        render = normalize_practice_table(table)["render"]
        self.assertEqual(len(render["rows"][2]), 1)
        self.assertEqual(render["rows"][2][0]["colspan"], 3)
        self.assertEqual(render["rows"][2][0]["text"], "Prices include tax")

    def test_all_imported_tables_have_a_complete_non_overlapping_render_grid(self):
        table_count = 0
        for root in TABLE_ROOTS:
            for path in root.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                for table in iter_tables(payload):
                    table_count += 1
                    render = normalize_practice_table(table)["render"]
                    area = sum(
                        cell["rowspan"] * cell["colspan"]
                        for row in render["rows"]
                        for cell in row
                    )
                    expected = len(render["rows"]) * render["column_count"]
                    self.assertEqual(area, expected, path.name)
                    for row in render["rows"]:
                        for cell in row:
                            self.assertIsInstance(cell["text"], str, path.name)
                            self.assertNotRegex(cell["text"], r"^\[\s*\d+\s*,\s*\d+\s*\]$")
        self.assertEqual(table_count, 196)


if __name__ == "__main__":
    unittest.main()
