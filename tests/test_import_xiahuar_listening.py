"""Unit tests for the Xiahuar listening importer."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.import_xiahuar_listening import (
    build_fill_layout,
    load_embedded_data,
    parse_timestamp,
)


class TimestampTests(unittest.TestCase):
    def test_standard_srt_timestamp(self):
        self.assertEqual(parse_timestamp("00:04:22,560"), 262_560)

    def test_minute_second_colon_timestamp(self):
        self.assertEqual(parse_timestamp("04:57:120"), 297_120)

    def test_malformed_nonzero_hour_is_source_minute(self):
        self.assertEqual(parse_timestamp("06:10:00,000"), 370_000)


class EmbeddedDataTests(unittest.TestCase):
    def test_loads_test_data_script(self):
        payload = {"title": "Example", "groups": []}
        html = (
            "<html><script id=\"test-data\" type=\"application/json\">"
            + json.dumps(payload)
            + "</script></html>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "example.html"
            path.write_text(html, encoding="utf-8")
            self.assertEqual(load_embedded_data(path), payload)


class FillLayoutTests(unittest.TestCase):
    def test_places_each_question_once(self):
        group = {
            "bodyLines": [
                {"text": "Complete the notes.", "list": False},
                {"text": "Name: 1. ______", "list": False},
                {"text": "Cost: £ 2. ______", "list": False},
            ]
        }
        questions = [
            {"id": "1", "text": "Name: 1. ______"},
            {"id": "2", "text": "Cost: £ 2. ______"},
        ]
        collect, table = build_fill_layout(group, questions)
        self.assertIsNone(table)
        self.assertEqual(collect.count("$1$"), 1)
        self.assertEqual(collect.count("$2$"), 1)


if __name__ == "__main__":
    unittest.main()
