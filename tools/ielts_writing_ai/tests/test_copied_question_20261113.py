"""Review f46756f (2026-11-13, docs/design/iwa-prompt13-review-20261113): deciding by
text similarity that a sentence was copied from the question failed both ways. A
writer's own overview that reused the question's nouns lost all its words (a 152-word
Task 1 was sent as 138, with a below-150 warning), and in the official 5.5 script a
misspelled copied sentence was missed (18 of 34 copied words found). Now a comparison
is only a hint on the page; copying confirmed in the data (paragraphs or verbatim
passages, with who confirmed it) is left out of the count and passed to the model.
Also: timeouts must be finite and positive. Synthetic texts only."""

import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.ielts_writing_ai import essay, prompts, realcheck, realcheck_compare, review, storage
from tools.ielts_writing_ai.config import ConfigError, load_settings
from tools.ielts_writing_ai.llm import FakeClient

from .helpers import settings_for

QUESTION = (
    "City parks bring many benefits to residents. At the same time, there is worry about "
    "their cost to local councils and the space they take up. Do the advantages of city "
    "parks outweigh the disadvantages?"
)
OWN_TEXT = (
    "In my opinion parks are good for a city because people can relax there after work.\n"
    "Firstly, children have a safe place to play and families meet their neighbours.\n"
    "Secondly, trees clean the air and make the summer less hot in busy streets.\n"
    "However, parks need money every year and some councils have very small budgets.\n"
    "To sum up, I think the advantages are bigger than the problems if parks are planned well."
)

# The reviewer's synthetic Task 1 (copy_probe.py): 152 words; the overview reuses the
# question's words but adds the writer's own trend.
QUESTION_T1 = (
    "The chart below shows the percentage of people who travelled to work by car, "
    "bus and bicycle in Newtown in 2000 and 2020."
)
OVERVIEW = "Overall, the percentage of people who travelled to work by car in Newtown increased."
FULL_T1 = (
    "The two sets of figures compare three commuting methods over a twenty year period "
    "in Newtown.\n"
    + OVERVIEW
    + "\nCars accounted for 40% of journeys initially, rising to 70% by the end of the "
    "period. This was the largest change among the three categories, and motoring "
    "remained the leading choice in both years. By contrast, the share for buses "
    "declined from 35% to 20%, placing this mode second throughout. Cycling also became "
    "less common, falling from 25% to just 10%.\n"
    "At the beginning, the gap between cars and buses was only five percentage points. "
    "By the final year, it had widened to fifty points. Meanwhile, the combined share "
    "for the two smaller categories dropped from 60% to 30%. These comparisons "
    "indicate a clear shift towards private vehicles, alongside reduced use of both "
    "alternatives. The ranking of the categories nevertheless stayed unchanged."
)
QUESTION_T2 = (
    "Governments should spend more money on roads than on public transport. "
    "To what extent do you agree or disagree?"
)
OPPOSING = "Governments should not spend more money on roads than on public transport."

# Two copied paragraphs; the second sentence is misspelled so badly that the text
# comparison misses it, as in the official script.
COPIED = (
    "City parks bring many benefits to residents. At the same tim ther is wory abuot "
    "it's costs to locall councels and the spase thay take.\n"
    "Do the advantages of city parks outweight the disadvantages?\n"
)
SOURCE = "合成测试：确认前两段是抄题"


def payload_of(messages):
    return json.loads(messages[1]["content"].split("\n", 1)[1].rsplit("\n", 1)[0])


def submission(text, question=QUESTION, task_type="task2", spans=None, source=SOURCE):
    sub = {
        "task_type": task_type,
        "prompt_text": question,
        "essay_text": text,
        "word_count": essay.count_words(text),
        "target_band": 7.0,
        "copied_spans": None,
    }
    if task_type == "task1":
        sub.update(image_status="ready", image_description="Synthetic bar chart of commuting.")
    if spans is not None:
        resolved = essay.resolve_copied(text, spans)
        sub["copied_spans"] = json.dumps({"spans": resolved, "source": source})
    return sub


def evaluated(sub):
    _messages, context = prompts.build_evaluate(sub, essay.split_sentences(sub["essay_text"]))
    return review.normalize_evaluation(FakeClient._evaluate(context), sub)


class SimilarIsOnlyAHintTest(unittest.TestCase):
    def test_the_152_word_report_keeps_its_count_and_its_messages(self):
        sub = submission(FULL_T1, QUESTION_T1, "task1")
        self.assertEqual(sub["word_count"], 152)
        self.assertEqual([h["p"] for h in essay.similar_to_prompt(FULL_T1, QUESTION_T1)], [2])
        messages, _ = prompts.build_evaluate(sub, essay.split_sentences(FULL_T1))
        payload = payload_of(messages)
        for key in ("copied_from_question", "word_count_without_copied", "copied_note"):
            self.assertNotIn(key, payload)
        self.assertEqual((payload["word_count"], payload["essay"]), (152, FULL_T1))
        result = evaluated(sub)
        self.assertEqual(result["copied_from_question"], [])
        self.assertEqual(result["similar_to_question"], [{"p": 2, "words": 14}])
        hint = next(w for w in result["warnings"] if "待确认" in w)
        self.assertIn("第 2 段有 1 句与题目用词高度重合", hint)
        self.assertIn("本工具没有因此扣字数", hint)
        joined = "\n".join(result["warnings"])
        self.assertNotIn("去掉后", joined)
        self.assertNotIn("138", joined)
        self.assertNotIn("低于 150 词", joined)

    def test_an_opposing_position_is_not_taken_away(self):
        text = OPPOSING + "\n" + OWN_TEXT
        sub = submission(text, QUESTION_T2)
        self.assertEqual(len(essay.similar_to_prompt(text, QUESTION_T2)), 1)
        messages, _ = prompts.build_evaluate(sub, essay.split_sentences(text))
        self.assertNotIn("copied_from_question", messages[1]["content"])
        self.assertEqual(payload_of(messages)["word_count"], essay.count_words(text))

    def test_without_a_hint_there_is_no_notice(self):
        result = evaluated(submission(OWN_TEXT))
        self.assertEqual((result["copied_from_question"], result["similar_to_question"]), ([], []))
        self.assertFalse(any("题目" in w and "抄" in w for w in result["warnings"]))


class ConfirmedCopyingTest(unittest.TestCase):
    def test_confirmed_paragraphs_count_in_full_although_the_comparison_misses_some(self):
        text = COPIED + OWN_TEXT
        copied_words = essay.count_words(COPIED)
        found = sum(h["words"] for h in essay.similar_to_prompt(text, QUESTION))
        self.assertLess(found, copied_words)  # what the comparison alone would give
        sub = submission(text, spans=[{"paragraph": 1}, {"paragraph": 2}])
        messages, _ = prompts.build_evaluate(sub, essay.split_sentences(text))
        payload = payload_of(messages)
        self.assertEqual(
            payload["copied_from_question"],
            [{"p": n, "text": t} for n, t in enumerate(essay.split_paragraphs(COPIED), 1)],
        )
        self.assertEqual(payload["word_count_without_copied"], essay.count_words(OWN_TEXT))
        self.assertIn("A reviewer confirmed", payload["copied_note"])
        self.assertIn("Everything else in the essay", payload["copied_note"])
        self.assertNotIn(SOURCE, messages[1]["content"])  # who confirmed it stays local
        plain, _ = prompts.build_evaluate(submission(OWN_TEXT), essay.split_sentences(OWN_TEXT))
        self.assertEqual(plain[0], messages[0])  # the rules themselves are unchanged
        self.assertNotIn("copied_from_question", plain[1]["content"])

        result = evaluated(sub)
        self.assertEqual(sum(s["words"] for s in result["copied_from_question"]), copied_words)
        warning = next(w for w in result["warnings"] if "已确认是照抄题目" in w)
        self.assertIn(f"第 1 段、第 2 段有 {copied_words} 词已确认是照抄题目", warning)
        self.assertIn(f"依据：{SOURCE}", warning)
        total, own = sub["word_count"], essay.count_words(OWN_TEXT)
        self.assertIn(f"原文 {total} 词，去掉后 {own} 词", warning)
        self.assertEqual(result["similar_to_question"], [])  # not repeated as a hint
        self.assertFalse(any("待确认" in w for w in result["warnings"]))

    def test_a_confirmed_passage_inside_a_paragraph(self):
        text = "City parks bring many benefits to residents. " + OWN_TEXT
        quote = "City parks bring many benefits to residents."
        sub = submission(text, spans=[{"quote": quote}])
        payload = payload_of(prompts.build_evaluate(sub, essay.split_sentences(text))[0])
        self.assertEqual(payload["copied_from_question"], [{"p": 1, "text": quote}])
        self.assertEqual(
            payload["word_count_without_copied"], essay.count_words(text) - essay.count_words(quote)
        )

    def test_the_minimum_is_named_when_only_the_copying_brings_the_essay_over_it(self):
        own = " ".join(["Parks give people a calm place to rest after work."] * 24)
        text = COPIED + own
        self.assertLess(essay.count_words(own), 250)
        self.assertGreaterEqual(essay.count_words(text), 250)
        result = evaluated(submission(text, spans=[{"paragraph": 1}, {"paragraph": 2}]))
        warning = next(w for w in result["warnings"] if "已确认是照抄题目" in w)
        self.assertTrue(warning.endswith("，低于 250 词要求。"))


class ResolveTest(unittest.TestCase):
    TEXT = "First paragraph here.\n\n  Second one, with words.\nThird and last one."

    def test_spans_come_back_in_essay_order(self):
        spans = essay.resolve_copied(self.TEXT, [{"paragraph": 3}, {"quote": "Second one"}])
        self.assertEqual(
            spans, [{"p": 2, "text": "Second one"}, {"p": 3, "text": "Third and last one."}]
        )

    def test_bad_entries_are_refused(self):
        for entries in (
            [],
            {"paragraph": 1},
            [{"paragraph": 0}],
            [{"paragraph": 4}],
            [{"paragraph": True}],
            [{"paragraph": "1"}],
            [{"quote": "not in the essay"}],
            [{"quote": "one"}],  # occurs twice
            [{"quote": "here.\n\n  Second"}],  # across paragraphs
            [{"quote": "econd one"}],  # not a whole word
            [{"quote": "   "}],
            [{"paragraph": 2}, {"quote": "with words"}],  # overlap
            [{"paragraph": 1, "quote": "First"}],
            [{"line": 1}],
        ):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                essay.resolve_copied(self.TEXT, entries)


class TokenBoundaryTest(unittest.TestCase):
    """Review cd82fc1: a quote may not stop inside a word as count_words sees it."""

    CASES = {
        "apostrophe": ("don't", ["don", "t"]),
        "curly_apostrophe": ("don’t", ["don", "t"]),
        "hyphen": ("cost-effective", ["cost", "effective"]),
    }

    def test_half_words_are_refused_and_whole_words_kept(self):
        for name, (compound, halves) in self.CASES.items():
            text = f"The {compound} approach is useful."
            with self.subTest(case=name):
                self.assertEqual(
                    essay.resolve_copied(text, [{"quote": compound}]), [{"p": 1, "text": compound}]
                )
                self.assertEqual(
                    essay.resolve_copied(text, [{"quote": f"The {compound}"}])[0]["text"],
                    f"The {compound}",
                )
                for quote in halves + [f"The {halves[0]}", f"{halves[-1]} approach"]:
                    with self.assertRaises(ValueError):
                        essay.resolve_copied(text, [{"quote": quote}])
                with self.assertRaises(ValueError):
                    essay.resolve_copied(text, [{"quote": q} for q in halves])
        # Punctuation next to a whole word is still a boundary.
        self.assertEqual(
            essay.resolve_copied("Yes, it works.", [{"quote": "it works."}])[0]["text"],
            "it works.",
        )
        with self.assertRaises(ValueError):  # a letter outside WORD_RE still counts
            essay.resolve_copied("A naïve plan.", [{"quote": "na"}])

    def test_one_word_is_never_taken_off_twice(self):
        text = "A cost-effective plan works. " + " ".join(["item"] * 147)
        self.assertEqual(essay.count_words(text), 151)
        tmp = Path(tempfile.mkdtemp(prefix="iwa-boundary-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        row = {
            "id": "split",
            "task_type": "task1",
            "prompt": "The chart compares spending on a cost-effective plan over time.",
            "essay": text,
            "copied_source": SOURCE,
        }
        path = tmp / "s.jsonl"
        for spans, ok in (
            ([{"quote": "cost"}, {"quote": "effective"}], False),
            ([{"quote": "cost-effective"}], True),
        ):
            path.write_text(json.dumps(dict(row, copied_from_question=spans)) + "\n")
            if not ok:
                with self.assertRaises(realcheck.RealCheckError):
                    realcheck.load_samples(str(path))
                continue
            sub = submission(text, row["prompt"], "task1", spans=spans)
            self.assertEqual(essay.confirmed_copies(sub)["words"], 1)
            payload = payload_of(prompts.build_evaluate(sub, essay.split_sentences(text))[0])
            self.assertEqual(payload["word_count_without_copied"], 150)
            warning = next(w for w in evaluated(sub)["warnings"] if "已确认" in w)
            self.assertIn("原文 151 词，去掉后 150 词", warning)
            self.assertNotIn("低于 150", warning)


class LoadSamplesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iwa-copied-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def load(self, **fields):
        row = {"id": "s1", "task_type": "task2", "prompt": QUESTION, "essay": COPIED + OWN_TEXT}
        row.update(fields)
        path = self.tmp / "s.jsonl"
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        return realcheck.load_samples(str(path))

    def test_confirmed_copying_needs_its_source_and_must_be_in_the_essay(self):
        self.assertEqual(len(self.load()), 1)
        self.assertEqual(
            len(self.load(copied_from_question=[{"paragraph": 1}], copied_source=SOURCE)), 1
        )
        for fields, message in (
            ({"copied_from_question": [{"paragraph": 1}]}, "需要 copied_source"),
            ({"copied_from_question": [{"paragraph": 1}], "copied_source": " "}, "需要"),
            ({"copied_from_question": [{"paragraph": 1}], "copied_source": "x" * 201}, "需要"),
            ({"copied_source": SOURCE}, "没有 copied_from_question"),
            ({"copied_from_question": [{"paragraph": 9}], "copied_source": SOURCE}, "段号"),
            ({"copied_from_question": [{"quote": "absent"}], "copied_source": SOURCE}, "找不到"),
        ):
            with self.subTest(fields=fields):
                with self.assertRaises(realcheck.RealCheckError) as caught:
                    self.load(**fields)
                self.assertIn("第 1 行", str(caught.exception))
                self.assertIn(message, str(caught.exception))


class Recording(FakeClient):
    def __init__(self):
        super().__init__()
        self.sent = []

    def complete(self, messages, **kwargs):
        self.sent.append(messages)
        return super().complete(messages, **kwargs)


class RealcheckRunTest(unittest.TestCase):
    def test_confirmed_copying_reaches_the_model_and_the_run_data(self):
        tmp = Path(tempfile.mkdtemp(prefix="iwa-copied-run-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = tmp / "s.jsonl"
        rows = [
            {
                "id": "copied",
                "task_type": "task2",
                "prompt": QUESTION,
                "essay": COPIED + OWN_TEXT,
                "copied_from_question": [{"paragraph": 1}, {"paragraph": 2}],
                "copied_source": SOURCE,
            },
            {"id": "own", "task_type": "task2", "prompt": QUESTION, "essay": OWN_TEXT},
        ]
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        client = Recording()
        data = realcheck.run(
            settings_for(str(tmp / "d")),
            realcheck.load_samples(str(path)),
            client=client,
            kinds=("evaluate",),
        )
        first, second = (payload_of(m) for m in client.sent)
        self.assertEqual([c["p"] for c in first["copied_from_question"]], [1, 2])
        self.assertEqual(first["word_count_without_copied"], essay.count_words(OWN_TEXT))
        self.assertNotIn("copied_from_question", second)
        copied, own = data["samples"]
        spans = json.loads(copied["submission"]["copied_spans"])
        self.assertEqual((len(spans["spans"]), spans["source"]), (2, SOURCE))
        self.assertIsNone(own["submission"]["copied_spans"])
        result = copied["generations"]["evaluate"]["result"]
        self.assertEqual(
            sum(s["words"] for s in result["copied_from_question"]), essay.count_words(COPIED)
        )
        # Comparison fingerprints of runs without confirmed copying are unchanged.
        legacy = {"submission": {k: v for k, v in own["submission"].items() if k != "copied_spans"}}
        self.assertEqual(
            realcheck_compare._fingerprint(own), realcheck_compare._fingerprint(legacy)
        )
        self.assertNotEqual(
            realcheck_compare._fingerprint(copied),
            realcheck_compare._fingerprint(
                {"submission": dict(copied["submission"], copied_spans=None)}
            ),
        )


class StorageMigrationTest(unittest.TestCase):
    def test_a_database_from_before_gets_the_column_and_keeps_its_rows(self):
        tmp = Path(tempfile.mkdtemp(prefix="iwa-migrate-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        db = tmp / "iwa.sqlite3"
        old_schema = storage.SCHEMA.replace("    copied_spans TEXT,\n", "")
        self.assertNotEqual(old_schema, storage.SCHEMA)
        conn = sqlite3.connect(db)
        conn.executescript(old_schema)
        conn.execute(
            "INSERT INTO trial_user(name, code_hash, code_hint, created_at)"
            " VALUES ('t', 'h', 'x', '2026-11-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO submission(public_id, user_id, task_type, prompt_text, essay_text,"
            " essay_sha256, word_count, target_band, image_status, created_at)"
            " VALUES ('old', 1, 'task2', 'q', 'e', '-', 1, 7.0, 'none', '2026-11-01T00:00:00Z')"
        )
        conn.commit()
        conn.close()
        store = storage.Storage(db)
        store.init_schema()
        store.init_schema()  # a second start changes nothing
        with store.connect() as conn:
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(submission)")]
            old = dict(conn.execute("SELECT * FROM submission WHERE public_id = 'old'").fetchone())
        self.assertEqual(columns.count("copied_spans"), 1)
        self.assertEqual((old["essay_text"], old["copied_spans"]), ("e", None))
        created = store.create_submission(
            public_id="new",
            user_id=1,
            task_type="task2",
            prompt_text="q",
            essay_text="e",
            essay_sha256="-",
            word_count=1,
            target_band=7.0,
            image_path=None,
            image_mime=None,
            image_status="none",
            daily_limit=100,
            copied_spans='{"spans": [], "source": "s"}',
        )
        self.assertEqual(
            store.get_submission(created["id"])["copied_spans"], '{"spans": [], "source": "s"}'
        )


class TimeoutValidationTest(unittest.TestCase):
    def test_timeouts_must_be_finite_and_positive(self):
        for name in ("LLM_TIMEOUT", "EVALUATE_THINKING_TIMEOUT", "VISION_TIMEOUT"):
            for value in ("inf", "-inf", "nan", "0", "-1", "1e10", "3601"):
                settings = load_settings(env={f"IWA_{name}": value}, env_file="/nonexistent")
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ConfigError) as caught:
                        settings.validate()
                    self.assertIn(f"IWA_{name}", str(caught.exception))
            for value, expected in (("0.5", 0.5), ("240", 240.0), ("3600", 3600.0)):
                settings = load_settings(env={f"IWA_{name}": value}, env_file="/nonexistent")
                settings.validate()
                self.assertEqual(getattr(settings, name.lower()), expected)


if __name__ == "__main__":
    unittest.main()
