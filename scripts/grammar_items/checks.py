"""The exhaustive plan reason codes and whole-sentence checks (no ID rules)."""

import re
from enum import StrEnum

# Plan v0.2 section B1: a sentence end glued to the next sentence ("these."Manufacturers).
GLUED_BOUNDARY = re.compile(r"(?<=\S)[.!?][\"”’')\]]?(?=[A-Z])")
INITIALS = re.compile(r"\b(?:[A-Z]\.)+[A-Z]$")
# Plan v0.2 section B1: a properly spaced sentence end inside one unit.
SPACED_BOUNDARY = re.compile(r"[a-z0-9][.!?][\"”’')\]]?\s+[\"“‘'(]?[A-Z]")
ABBREVIATION = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|St|Prof|Jr|Sr|No|Co|Inc|Ltd|vs|etc|U\.S|U\.K|e\.g|i\.e|a\.m|p\.m)"
    r"[.!?][\"”’')\]]?\s+[A-Z]$"
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


def multi_sentence_unit(sentence):
    return any(
        not ABBREVIATION.search(sentence[max(0, m.start() - 6) : m.end()])
        for m in SPACED_BOUNDARY.finditer(sentence)
    )


def clause_attached_to_conjunction(view):
    clause_deps = {"advcl", "conj", "ccomp", "relcl", "csubj", "csubjpass", "acl"}
    return any(t.dep in clause_deps and view.tokens[t.head].dep == "cc" for t in view.tokens)


def sentence_reasons(sentence, spans, view):
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
