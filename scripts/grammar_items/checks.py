"""The exhaustive plan reason codes and whole-sentence checks (no ID rules)."""

import re
from collections import Counter
from enum import StrEnum

# Plan v0.2 section B1: a sentence end glued to the next sentence ("these."Manufacturers).
GLUED_BOUNDARY = re.compile(r"(?<=\S)[.!?][\"”’')\]]?(?=[A-Z])")
INITIALS = re.compile(r"\b(?:[A-Z]\.)+[A-Z]$")
# Plan v0.2 section B1: a properly spaced sentence end inside one unit.
SPACED_BOUNDARY = re.compile(r"[a-z0-9][.!?][\"”’')\]]?\s+[\"“‘'(]?[A-Z]")
# A unit opening with a stray mark (". To encourage"), left by a stripped paragraph label;
# a leading ellipsis ("... I think") is a quotation cut, not a stray mark.
LEADING_STRAY_PUNCTUATION = re.compile(r"^(?!\.\.\.)[.,;:!?]\s")
# Encoding damage such as NUL for a lost "$" ("yuan (\x001.9 trillion)"); Excel rejects these.
CONTROL_CHARACTER = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Words as plain alphabetic runs; used for the corpus vocabulary and split-word check.
WORD = re.compile(r"[A-Za-z]+")
# A rare pair whose concatenation is a known word, e.g. "calcu lated" (OCR split).
SPLIT_WORD_MAX_PART_COUNT = 2
ABBREVIATION = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|St|Mt|Prof|Jr|Sr|No|Co|Inc|Ltd|vs|etc|U\.S|U\.K|e\.g|i\.e|a\.m|p\.m)"
    r"[.!?][\"”’')\]]?\s+[\"“‘'(]?[A-Z]$"
)
# Not sentence ends (2026-10-19 re-split review): a leading list number ("1. Valid ..."), and
# a quoted question or exclamation followed by its speaker ("...?" Pepperberg asked.).
LIST_MARKER = re.compile(r"\d{1,2}\.\s+[A-Z]")
# Round 7 (user decision on review A3/A6): sentences the reading notes mark as defective, and
# list items, still get items, but none passes automatically. A reading note that describes a
# defect of the sentence itself opens with this prefix.
SOURCE_PROBLEM_PREFIX = "原句问题："
# A bulleted or numbered list item ("- is calm, and ...", "• The S.K.I. ...", "2) Restriction ...").
LIST_ITEM = re.compile(r"^\s*(?:[-–—•*]|\(?\d{1,2}[.)])\s")
QUOTED_ATTRIBUTION = re.compile(
    r"[?!][\"”’']\s+(?:[A-Z][\w.'’-]*\s+){1,3}"
    r"(?:says|said|asks|asked|adds|added|explains|explained|replies|replied|wonders|wondered)\b"
)


class Reason(StrEnum):
    HEADING = "heading"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    UNKNOWN_SPAN = "unknown_span"
    SPAN_NOT_FOUND = "span_not_found"
    LEVEL_ONE_SUBORDINATE = "level_one_subordinate"
    FRAGMENT = "fragment"
    UNBALANCED_QUOTES_OR_BRACKETS = "unbalanced_quotes_or_brackets"
    TAGGED_FRAGMENT = "tagged_fragment"
    CLAUSE_ATTACHED_TO_CONJUNCTION = "clause_attached_to_conjunction"
    GLUED_SENTENCE_BOUNDARY = "glued_sentence_boundary"
    MULTI_SENTENCE_UNIT = "multi_sentence_unit"
    SUSPECTED_SPLIT_WORD = "suspected_split_word"
    LEADING_STRAY_PUNCTUATION = "leading_stray_punctuation"
    CONTROL_CHARACTER = "control_character"
    PARSE_FAILURE = "parse_failure"
    AMBIGUOUS_SPAN_LOCATION = "ambiguous_span_location"
    PARSER_ROOT_OUTSIDE_VERB_SPAN = "parser_root_outside_verb_span"
    PARSER_ROOT_INSIDE_SUBORDINATE_SPAN = "parser_root_inside_subordinate_span"
    COORDINATED_MAIN_VERBS = "coordinated_main_verbs"
    MULTIPLE_TARGETS_SAME_TYPE = "multiple_targets_same_type"
    SPAN_NOT_CONSTITUENT = "span_not_constituent"
    CLAUSE_TYPE_MISMATCH = "clause_type_mismatch"
    BOUNDARY_MISMATCH = "boundary_mismatch"
    NO_RELATION_LABEL = "no_relation_label"
    SUBORDINATOR_MISMATCH = "subordinator_mismatch"
    SUBORDINATOR_AMBIGUOUS = "subordinator_ambiguous"
    SUBORDINATOR_UNKNOWN = "subordinator_unknown"
    SUBJECT_MISMATCH = "subject_mismatch"
    FINITENESS_MISMATCH = "finiteness_mismatch"
    NO_MAIN_VERB_TAG = "no_main_verb_tag"
    MULTIPLE_MAIN_VERBS = "multiple_main_verbs"
    COORDINATED_MAIN_CLAUSES = "coordinated_main_clauses"
    SPLIT_SUBJECT = "split_subject"
    EXISTENTIAL = "existential"
    SUBJECT_AFTER_VERB = "subject_after_verb"
    RELATION_LABEL_OUT_OF_SCOPE = "relation_label_out_of_scope"
    NO_DISTRACTOR = "no_distractor"
    POSSIBLE_RELATIVE_ADVERB = "possible_relative_adverb"
    VERB_UNIT_OUTSIDE_SPAN = "verb_unit_outside_span"
    SOURCE_QUALITY = "source_quality"
    LIST_ITEM = "list_item"


def unbalanced(sentence):
    pairs = {"(": ")", "[": "]", "{": "}", "“": "”", "‘": "’"}
    stack, straight = [], set()
    for index, char in enumerate(sentence):
        before = sentence[index - 1] if index else ""
        after = sentence[index + 1] if index + 1 < len(sentence) else ""
        if char in {"'", "’"} and before.isalnum() and after.isalnum():
            continue  # A contraction, not a quotation delimiter.
        if char in {"'", "’"} and before.lower() == "s":
            if char not in straight and (not stack or stack[-1] != char):
                continue  # Unquoted plural possessive, e.g. students' books.
        if char in {'"', "'"}:
            if char in straight:
                straight.remove(char)
            else:
                straight.add(char)
        elif char in pairs:
            stack.append(pairs[char])
        elif char in pairs.values():
            if not stack or stack.pop() != char:
                return True
    return bool(stack or straight)


def glued_sentence_boundary(sentence):
    return any(
        not INITIALS.search(sentence[max(0, m.start() - 4) : m.end() + 1])
        for m in GLUED_BOUNDARY.finditer(sentence)
    )


def sentence_end(sentence, match):
    if ABBREVIATION.search(sentence[max(0, match.start() - 6) : match.end()]):
        return False
    if match.start() == 0 and LIST_MARKER.match(sentence):
        return False
    return not QUOTED_ATTRIBUTION.match(sentence, match.start() + 1)


def multi_sentence_unit(sentence):
    return any(sentence_end(sentence, m) for m in SPACED_BOUNDARY.finditer(sentence))


def corpus_vocabulary(sentences):
    """Lower-cased word counts over the whole corpus (deterministic, parser-free)."""
    return Counter(w.lower() for sentence in sentences for w in WORD.findall(sentence))


def suspected_split_word(sentence, vocabulary):
    words = list(WORD.finditer(sentence))
    for left, right in zip(words, words[1:], strict=False):
        if sentence[left.end() : right.start()] != " ":
            continue
        a, b = left.group().lower(), right.group().lower()
        rare = max(vocabulary[a], vocabulary[b]) <= SPLIT_WORD_MAX_PART_COUNT
        if rare and vocabulary[a + b] >= 1:
            return True
    return False


def clause_attached_to_conjunction(view):
    clause_deps = {"advcl", "conj", "ccomp", "relcl", "csubj", "csubjpass", "acl"}
    return any(t.dep in clause_deps and view.tokens[t.head].dep == "cc" for t in view.tokens)


def review_reasons(sentence, difficult_points=()):
    """Whole-sentence reasons that send every item of the sentence to review, not rejection."""
    reasons = []
    if any(str(point).startswith(SOURCE_PROBLEM_PREFIX) for point in difficult_points):
        reasons.append(Reason.SOURCE_QUALITY)
    if LIST_ITEM.match(sentence):
        reasons.append(Reason.LIST_ITEM)
    return reasons


def sentence_reasons(sentence, spans, view, vocabulary=None):
    checks = {
        Reason.HEADING: any(s.concept == "heading" for s in spans),
        Reason.UNKNOWN_SPAN: any(s.concept == "unknown" for s in spans),
        Reason.SPAN_NOT_FOUND: any(s.start < 0 for s in spans),
        Reason.LEVEL_ONE_SUBORDINATE: any(
            s.level == 1 and s.concept in {"relative_clause", "noun_clause"} for s in spans
        ),
        Reason.UNBALANCED_QUOTES_OR_BRACKETS: unbalanced(sentence),
        Reason.TAGGED_FRAGMENT: any("fragment" in s.role for s in spans),
        Reason.GLUED_SENTENCE_BOUNDARY: glued_sentence_boundary(sentence),
        Reason.MULTI_SENTENCE_UNIT: multi_sentence_unit(sentence),
        Reason.PARSE_FAILURE: view is None,
        Reason.SUSPECTED_SPLIT_WORD: vocabulary is not None
        and suspected_split_word(sentence, vocabulary),
        Reason.LEADING_STRAY_PUNCTUATION: bool(LEADING_STRAY_PUNCTUATION.match(sentence)),
        Reason.CONTROL_CHARACTER: bool(CONTROL_CHARACTER.search(sentence)),
    }
    if view is not None:
        checks.update(
            {
                Reason.TOO_SHORT: view.word_count < 6,
                Reason.TOO_LONG: view.word_count > 60,
                Reason.FRAGMENT: view.root is None or view.root.pos not in {"VERB", "AUX"},
                Reason.CLAUSE_ATTACHED_TO_CONJUNCTION: clause_attached_to_conjunction(view),
            }
        )
    return sorted(reason for reason, matched in checks.items() if matched)
