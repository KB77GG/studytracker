"""Raw-role whitelists from plan section 5 and ordered source-span location."""

from dataclasses import dataclass

from api.reading_study_glossary import resolve_role

MAIN_VERB_ROLES = frozenset(
    {
        "verb_phrase",
        "predicate",
        "verb",
        "main_predicate",
        "passive_predicate",
        "passive_verb_phrase",
        "passive_verb",
        "linking_verb",
        "linking_predicate",
    }
)
COORDINATED_PREDICATE_ROLES = frozenset(
    {
        "coordinated_predicate",
        "coordinate_predicate",
        "coordinated_verb_phrase",
        "compound_predicate",
        "coordinate_verb",
        "first_predicate",
        "coordinate_passive_predicate",
        "coordinated_passive_predicate",
    }
)
RELATIVE_CLAUSE_ROLES = frozenset(
    {
        "relative_clause",
        "nonrestrictive_relative_clause",
        "non_restrictive_relative_clause",
    }
)
NOUN_CLAUSE_ROLES = frozenset(
    {
        "noun_clause",
        "object_clause",
        "subject_clause",
        "appositive_clause",
        "content_clause",
        "predicative_clause",
        "that_clause",
        "subject_complement_clause",
        "embedded_question",
    }
)
COORDINATE_CLAUSE_ROLES = frozenset(
    {
        "coordinated_clause",
        "coordinate_clause",
        "coordinated_main_clause",
    }
)
NON_FINITE_ROLES = frozenset(
    {
        "participial_phrase",
        "past_participle_modifier",
        "past_participial_phrase",
        "present_participle_modifier",
        "present_participle_adverbial",
        "present_participial_phrase",
        "present_participle_result",
        "participial_modifier",
        "past_participle_phrase",
        "past_participle_postmodifier",
        "infinitive_phrase",
        "infinitive_complement",
        "purpose_infinitive",
        "infinitive_modifier",
        "infinitive_purpose",
        "infinitive_postmodifier",
        "gerund_phrase",
        "gerund_subject",
        "gerund_object",
        "gerund_complement",
        "non_finite_clause",
    }
)
RELATION_BY_ROLE = {
    "conditional_clause": "条件",
    "condition_clause": "条件",
    "time_clause": "时间",
    "temporal_clause": "时间",
    "purpose_clause": "目的",
    "concessive_clause": "让步",
    "concession_clause": "让步",
    "result_clause": "结果",
    "contrast_clause": "对比",
    "contrastive_clause": "对比",
    "reason_clause": "原因",
    "cause_clause": "原因",
}
ADVERBIAL_CLAUSE_ROLES = frozenset({"adverbial_clause", *RELATION_BY_ROLE})
SUBORDINATOR_RELATIONS = {
    "although": "让步",
    "though": "让步",
    "even though": "让步",
    "even if": "让步",
    "whereas": "对比",
    "because": "原因",
    "if": "条件",
    "unless": "条件",
    "provided": "条件",
    "providing": "条件",
    "as long as": "条件",
    "so that": "目的",
    "in order that": "目的",
    "until": "时间",
    "till": "时间",
    "before": "时间",
    "after": "时间",
    "once": "时间",
    "whenever": "时间",
    "as soon as": "时间",
    "when": "时间",
}
AMBIGUOUS_SUBORDINATORS = frozenset({"while", "since", "as", "so"})
CLAUSE_ROLES = {
    "relative": RELATIVE_CLAUSE_ROLES,
    "noun": NOUN_CLAUSE_ROLES,
    "adverbial": ADVERBIAL_CLAUSE_ROLES,
    "coordinate": COORDINATE_CLAUSE_ROLES,
}
CLAUSE_DEPS = {
    "relative": frozenset({"relcl"}),
    "noun": frozenset({"ccomp", "csubj", "csubjpass", "pcomp"}),
    "adverbial": frozenset({"advcl"}),
    "coordinate": frozenset({"conj"}),
}
CLAUSE_NODES = {"relative": "G-C04", "noun": "G-C08", "adverbial": "G-C10", "coordinate": "G-C02"}
CLAUSE_LABELS = {
    "relative": "定语从句",
    "noun": "名词性从句",
    "adverbial": "状语从句",
    "coordinate": "并列分句",
}


@dataclass(frozen=True)
class Span:
    text: str
    role: str
    level: int
    start: int
    end: int
    ambiguous: bool
    concept: str


def locate_spans(sentence, structure):
    spans, previous = [], 0
    for raw in structure:
        text = raw["text"]
        start = sentence.find(text, previous) if text else -1
        first = sentence.find(text) if text else -1
        ambiguous = first >= 0 and sentence.find(text, first + 1) >= 0
        spans.append(
            Span(
                text,
                raw["role"],
                raw["level"],
                start,
                start + len(text) if start >= 0 else -1,
                ambiguous,
                resolve_role(raw["role"])["concept"],
            )
        )
        if start >= 0:
            previous = start
    return tuple(spans)


def clause_kind(span):
    return next((kind for kind, roles in CLAUSE_ROLES.items() if span.role in roles), None)


def classification_kind(span):
    kind = clause_kind(span)
    if kind:
        return kind
    if span.role in NON_FINITE_ROLES or span.concept == "prepositional_phrase":
        return "phrase"
    return None
