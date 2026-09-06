import unittest
from pathlib import Path

from scripts.audit_practice_markup import (
    audit_group_placeholders,
    audit_markup_text,
    audit_repository,
)

ROOT = Path(__file__).resolve().parents[1]


class PlaceholderTokenTests(unittest.TestCase):
    def test_matches_only_exact_ids_from_the_same_group(self):
        group = {
            "collect": "Tickets cost US$90-$100; answers $123$ and $123$; stray $999$.",
            "table": None,
            "questions": [
                {"id": 90},
                {"id": 100},
                {"id": 123},
                {"id": 124},
            ],
        }

        result = audit_group_placeholders(group)

        self.assertEqual(result["recognized_occurrences"], 2)
        self.assertEqual(result["exact_ids"], [])
        self.assertEqual(result["duplicate_ids"], ["123"])
        self.assertEqual(result["missing_ids"], ["100", "124", "90"])
        self.assertEqual(result["orphan_tokens"], ["999"])

    def test_collect_and_table_form_one_active_placeholder_surface(self):
        group = {
            "collect": "First $10$",
            "table": {"title": "Results", "content": [["Second $11$"]]},
            "items": [{"id": 10}, {"id": 11}],
        }

        result = audit_group_placeholders(group)

        self.assertEqual(result["exact_ids"], ["10", "11"])
        self.assertEqual(result["missing_ids"], [])
        self.assertEqual(result["orphan_tokens"], [])


class MarkupScannerTests(unittest.TestCase):
    def test_reports_supported_structure_and_unsafe_attributes_separately(self):
        result = audit_markup_text(
            '<table class="source"><tr><th scope="col">A</th>'
            '<td rowspan="2" onclick="steal()"><script>x</script>&nbsp;</td></tr></table>'
        )

        self.assertEqual(result["tags"]["table"], 2)
        self.assertEqual(result["tags"]["script"], 2)
        self.assertEqual(result["entities"]["&nbsp;"], 1)
        self.assertEqual(result["discarded_attributes"]["table.class"], 1)
        self.assertNotIn("th.scope", result["discarded_attributes"])
        self.assertNotIn("td.rowspan", result["discarded_attributes"])
        self.assertEqual(
            result["dangerous_attributes"],
            [{"tag": "td", "attribute": "onclick", "value": "steal()"}],
        )

    def test_reports_html_compatibility_forms_and_span_value_errors(self):
        optional = audit_markup_text(
            '<table><tr><td>A<td>$1$</tr><tr><td rowspan="0">B<td>$2$</table>'
        )
        formatted = audit_markup_text("<table>\n<tr>\n<td>$1$</td>\n</tr>\n</table>")
        invalid = audit_markup_text(
            '<table><tr><td rowspan="-1" colspan="101">A</td>'
            '<th scope="diagonal">B</th></tr></table>'
        )

        self.assertEqual(optional["optional_end_tag_closures"], 5)
        self.assertEqual(optional["rowspan_zero_occurrences"], 1)
        self.assertEqual(formatted["structural_whitespace_segments"], 4)
        self.assertEqual(len(invalid["invalid_safe_attributes"]), 3)


class ReachableCorpusAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = audit_repository(ROOT)
        cls.corpora = {corpus["name"]: corpus for corpus in cls.report["corpora"]}

    def test_catalog_file_unit_group_and_question_counts_are_exact(self):
        expected = {
            "listening_cambridge": (72, 72, 288, 568, 2880),
            "listening_jfdr6": (6, 6, 24, 48, 240),
            "listening_jfdr7": (6, 6, 24, 42, 240),
            "listening_jijing_legacy": (232, 232, 232, 497, 2320),
            "listening_jijing_xiahuar": (113, 113, 113, 178, 1130),
            "reading_cambridge": (72, 72, 216, 613, 2880),
            "reading_jijing_online": (56, 56, 168, 498, 2240),
            "reading_jijing_offline_direct": (1, 1, 3, 8, 39),
        }
        self.assertEqual(set(self.corpora), set(expected))
        for name, values in expected.items():
            counts = self.corpora[name]["counts"]
            self.assertEqual(
                tuple(
                    counts[key]
                    for key in ("catalog_entries", "files", "units", "groups", "questions")
                ),
                values,
                name,
            )
        self.assertEqual(
            self.report["totals"],
            {
                "catalog_entries": 558,
                "files": 558,
                "units": 1068,
                "groups": 2452,
                "questions": 11969,
            },
        )

    def test_placeholder_coverage_and_known_legacy_gap_are_reported(self):
        self.assertEqual(
            self.report["placeholders"],
            {
                "active_groups": 854,
                "recognized_occurrences": 4885,
                "covered_question_ids": 4873,
                "exact_once_question_ids": 4861,
                "duplicate_question_ids": 12,
                "duplicate_extra_occurrences": 12,
                "missing_question_ids": 4,
                "orphan_marker_occurrences": 0,
            },
        )
        legacy = self.corpora["listening_jijing_legacy"]["placeholders"]
        missing = [finding for finding in legacy["findings"] if finding["missing_ids"]]
        self.assertEqual(len(missing), 1)
        self.assertEqual(
            (
                missing[0]["path"],
                missing[0]["group_id"],
                missing[0]["missing_ids"],
            ),
            (
                "static/listening_jijing/parts/jijing_76_test_113_part_3_1308.json",
                2903,
                ["12916", "12917", "12918", "12919"],
            ),
        )

    def test_renderer_dispatch_risks_include_cambridge_and_online_zyz(self):
        cambridge = self.corpora["reading_cambridge"]["renderer_dispatch"]
        self.assertEqual(
            (
                cambridge["complete_placeholder_with_options_groups"],
                cambridge["complete_placeholder_with_options_questions"],
                cambridge["risk_groups"],
                cambridge["risk_questions"],
            ),
            (39, 191, 39, 191),
        )
        zyz = self.corpora["reading_jijing_online"]["renderer_dispatch"]
        self.assertEqual(
            (
                zyz["complete_placeholder_with_options_groups"],
                zyz["complete_placeholder_with_options_questions"],
                zyz["completion_type_groups"],
                zyz["completion_type_questions"],
                zyz["risk_groups"],
                zyz["risk_questions"],
            ),
            (15, 73, 8, 37, 8, 37),
        )

    def test_markup_inventory_covers_structured_source_html(self):
        markup = self.report["markup"]
        self.assertEqual(markup["object_table_groups"], 196)
        self.assertEqual(markup["raw_html_table_groups"], 1)
        self.assertEqual(markup["raw_structured_html_groups"], 5)
        self.assertEqual(markup["dangerous_attribute_occurrences"], 0)
        self.assertEqual(markup["invalid_safe_attribute_occurrences"], 0)
        self.assertEqual(markup["rowspan_zero_occurrences"], 0)
        self.assertEqual(markup["optional_end_tag_closures"], 0)
        self.assertEqual(markup["structural_whitespace_segments"], 0)
        self.assertEqual(markup["unsupported_tag_occurrences"], {})
        self.assertEqual(markup["entity_occurrences"], {"&nbsp;": 13160})
        self.assertEqual(
            markup["discarded_attribute_occurrences"],
            {"table.border": 1, "table.cellspacing": 1, "table.class": 1},
        )

        reading = self.corpora["reading_cambridge"]["markup"]
        raw_table = [
            finding
            for finding in reading["raw_structured_html_findings"]
            if "table" in finding["tags"]
        ]
        self.assertEqual(len(raw_table), 1)
        self.assertEqual(
            (raw_table[0]["path"], raw_table[0]["group_id"]),
            ("static/reading_tests/ielts21_test2_reading.json", 589),
        )


if __name__ == "__main__":
    unittest.main()
