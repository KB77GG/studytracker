"""Integrity checks for the grammar knowledge graph draft.

The graph (data/grammar_graph/grammar_graph_v0.json) is hand-edited by teachers
during review, so these tests guard the structural rules that later import and
recommendation code will rely on: valid references, an acyclic graph, full
coverage of the Reading Study concept vocabulary, and a self-contained phase 1.

Run standalone:
    python -m unittest tests.test_grammar_graph_draft -v
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
for _path in (str(ROOT), str(SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import build_ielts_grammar_60_materials as grammar_60  # noqa: E402

from api.reading_study_glossary import CONCEPTS  # noqa: E402

GRAPH_PATH = ROOT / "data" / "grammar_graph" / "grammar_graph_v0.json"
NODE_ID = re.compile(r"^G-[A-Z]\d{2}$")


class GrammarGraphDraftTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        cls.nodes = {node["id"]: node for node in cls.graph["nodes"]}

    def test_node_ids_are_unique_and_well_formed(self):
        ids = [node["id"] for node in self.graph["nodes"]]
        self.assertEqual(len(ids), len(set(ids)))
        for node_id in ids:
            self.assertRegex(node_id, NODE_ID)

    def test_nodes_use_declared_vocabularies(self):
        modules = {module["id"] for module in self.graph["modules"]}
        task_types = set(self.graph["task_types"])
        auto_values = set(self.graph["auto_items_semantics"])
        for node in self.graph["nodes"]:
            with self.subTest(node=node["id"]):
                self.assertIn(node["module"], modules)
                self.assertIn(node["phase"], (1, 2))
                self.assertIn(node["auto_items"], auto_values)
                self.assertTrue(node["task_types"])
                self.assertLessEqual(set(node["task_types"]), task_types)
                self.assertTrue(node["objective"] and node["evidence"] and node["common_errors"])

    def test_edges_reference_existing_nodes_without_duplicates(self):
        seen = set()
        for edge in self.graph["edges"]:
            pair = (edge["node"], edge["requires"])
            with self.subTest(edge=pair):
                self.assertIn(edge["node"], self.nodes)
                self.assertIn(edge["requires"], self.nodes)
                self.assertNotEqual(edge["node"], edge["requires"])
                self.assertIn(edge["strength"], ("hard", "soft"))
                self.assertTrue(edge["reason"].strip())
                self.assertNotIn(pair, seen)
                seen.add(pair)

    def test_graph_is_acyclic(self):
        requires = {node_id: [] for node_id in self.nodes}
        for edge in self.graph["edges"]:
            requires[edge["node"]].append(edge["requires"])
        state = {}

        def visit(node_id, path):
            if state.get(node_id) == "done":
                return
            if state.get(node_id) == "active":
                self.fail("cycle: " + " -> ".join(path + [node_id]))
            state[node_id] = "active"
            for prereq in requires[node_id]:
                visit(prereq, path + [node_id])
            state[node_id] = "done"

        for node_id in self.nodes:
            visit(node_id, [])

    def test_every_glossary_concept_is_mapped_or_excluded(self):
        mapped = {concept for node in self.graph["nodes"] for concept in node["concepts"]}
        excluded = set(self.graph["excluded_concepts"])
        self.assertLessEqual(mapped, set(CONCEPTS))
        self.assertLessEqual(excluded, set(CONCEPTS))
        self.assertFalse(mapped & excluded)
        self.assertEqual(mapped | excluded, set(CONCEPTS))

    def test_phase_one_hard_prerequisites_stay_in_phase_one(self):
        for edge in self.graph["edges"]:
            if edge["strength"] != "hard" or self.nodes[edge["node"]]["phase"] != 1:
                continue
            with self.subTest(edge=(edge["node"], edge["requires"])):
                self.assertEqual(self.nodes[edge["requires"]]["phase"], 1)

    def test_grammar_60_references_match_existing_units(self):
        titles = {f"{topic['unit']} {topic['title_cn']}" for topic in grammar_60.TOPICS}
        for node in self.graph["nodes"]:
            for ref in node["grammar_60_units"]:
                with self.subTest(node=node["id"], ref=ref):
                    self.assertIn(ref, titles)


if __name__ == "__main__":
    unittest.main()
