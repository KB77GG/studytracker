"""Six annotation-led question templates with independent parser checks."""

import re
from dataclasses import dataclass, field
from hashlib import sha1

from .checks import Reason as R
from .parse_view import centers, finite, token_bounds, trim_tokens
from .spans import (
    ADVERBIAL_CLAUSE_ROLES,
    AMBIGUOUS_SUBORDINATORS,
    CLAUSE_DEPS,
    CLAUSE_LABELS,
    CLAUSE_NODES,
    CLAUSE_ROLES,
    COORDINATE_CLAUSE_ROLES,
    COORDINATED_PREDICATE_ROLES,
    MAIN_VERB_ROLES,
    NON_FINITE_ROLES,
    RELATION_BY_ROLE,
    RELATIVE_CLAUSE_ROLES,
    SUBORDINATOR_RELATIONS,
    classification_kind,
    clause_kind,
)

TEMPLATES = (
    "main_verb_tap",
    "clause_boundary",
    "clause_type_classify",
    "adverbial_relation",
    "subject_span",
    "finite_or_not",
)
TYPE_OPTIONS = [*CLAUSE_LABELS.values(), "不是从句（短语或非谓语）"]
RELATION_OPTIONS = ["时间", "原因", "条件", "让步", "对比", "目的", "结果"]
FINITE_OPTIONS = ["主句谓语", "从句里的谓语", "非谓语（不定式、分词、动名词）"]
GENERATOR_VERSION = "grammar-items-v0.2"
# Plan v0.2 B3: a highlighted verb always carries its auxiliaries, negation and particle.
VERB_UNIT_DEPS = frozenset({"aux", "auxpass", "neg", "prt"})
# Plan v0.2 B2: when/where/why right after a noun may be a relative adverb.
RELATIVE_ADVERBS = frozenset({"when", "where", "why"})


def char_span(sentence, start, end):
    return {"start": start, "end": end, "text": sentence[start:end]}


def token_span(sentence, token):
    return char_span(sentence, token.start, token.end)


def span_from_tokens(sentence, tokens):
    return char_span(sentence, tokens[0].start, tokens[-1].end) if tokens else None


QUOTE_PAIRS = {'"': '"', "“": "”", "‘": "’"}
# The digits after the apostrophe in a decade such as '60s.
DECADE = re.compile(r"\d0s\b")
# Dashes around an inserted phrase ("processes - melting, refining - take place"); a dash
# between digits is a range ("5–10"), not one of the pair.
DASH = re.compile(r"—|(?<!\d)–(?!\d)|(?<!\d) - (?!\d)")
# Trimming also drops a closing bracket ("Rani Ki Vav (Queen's Stepwell"); same bounded repair.
BRACKET_PAIRS = {"(": ")", "[": "]"}
# Coordinating conjunctions that spaCy may tag as mark; a clause led by them is still coordinate.
COORDINATING_MARKS = frozenset({"for", "so", "yet"})
# A coordinate clause needs a subject of its own; without one it is a coordinated predicate.
CLAUSE_SUBJECT_DEPS = frozenset({"nsubj", "nsubjpass", "csubj", "csubjpass", "expl"})


def single_quote_role(sentence, index):
    """'open' / 'close' for a straight single quote used as a quote mark, else None.

    Apostrophes are None: inside a word (it's) and in a decade ('80s); a quote may still
    start with a number ('15 volts ...'). An s' before a lower-case word is 'ambiguous':
    a possessive (students' books) or the end of a quoted term ('megacities' and);
    balance_single_quotes decides from context.
    """
    before = sentence[index - 1] if index else " "
    after = sentence[index + 1] if index + 1 < len(sentence) else " "
    if DECADE.match(sentence, index + 1):
        return None
    if before in "sS" and after == " " and sentence[index + 2 : index + 3].islower():
        return "ambiguous"
    if (before.isspace() or before in '(“"‘—–-') and after.isalnum():
        return "open"
    if (before.isalnum() or before in ".,!?;:)") and not after.isalnum():
        return "close"
    return None


def balance_single_quotes(sentence, start, end, low, high):
    opened = closed = 0
    for i in range(start, end):
        role = single_quote_role(sentence, i) if sentence[i] == "'" else None
        if role == "ambiguous":
            role = "close" if opened > closed else None  # Closes a pending quote only.
        opened += role == "open"
        closed += role == "close"
    if opened > closed:
        for i in range(end, high):
            if sentence[i] == "'" and single_quote_role(sentence, i) in ("close", "ambiguous"):
                return start, i + 1
    if closed > opened:
        for i in range(start - 1, low - 1, -1):
            if sentence[i] == "'" and single_quote_role(sentence, i) == "open":
                return i, end
    return start, end


def close_quotes(sentence, span, low, high):
    """Re-attach a quote mark, bracket or closing dash that trimming split off, inside [low, high)."""
    if not span:
        return span
    start, end = span["start"], span["end"]
    for opening, closing in {**QUOTE_PAIRS, **BRACKET_PAIRS}.items():
        text = sentence[start:end]
        if opening == closing:
            missing_open = missing_close = text.count(opening) % 2 == 1
        else:
            balance = text.count(opening) - text.count(closing)
            missing_open, missing_close = balance < 0, balance > 0
        before = sentence.rfind(opening, low, start) if missing_open else -1
        if before >= 0:
            start = before
            continue
        after = sentence.find(closing, end, high) if missing_close else -1
        if after >= 0:
            end = after + len(closing)
    start, end = balance_single_quotes(sentence, start, end, low, high)
    if len(DASH.findall(sentence, start, end)) % 2:
        after = DASH.search(sentence, end, high)
        if after and not sentence[end : after.start()].strip():
            end = after.start() + len(after.group().rstrip())
    if (start, end) == (span["start"], span["end"]):
        return span
    return char_span(sentence, start, end)


def item_id(source, template, start, end, variant):
    text = f"{source['passage_id']}|{source['sentence_id']}|{template}|{start}:{end}|{variant}"
    return "gi_v02_" + sha1(text.encode("utf-8")).hexdigest()[:12]


def verb_unit(view, head, start=None, end=None):
    """The head verb plus its aux/auxpass/neg/prt children.

    With bounds, children outside [start, end) are dropped; this is only kept for the
    T1 answer, which plan v0.2 freezes. Displayed units use the unbounded form.
    """
    children = (
        c
        for c in view.children(head)
        if c.dep in VERB_UNIT_DEPS and (start is None or (start <= c.start and c.end <= end))
    )
    return sorted([head, *children], key=lambda t: t.i)


def outside_span(tokens, span):
    """Plan v0.2 review F1: a unit reaching past the tag span must not auto-pass."""
    outside = any(t.start < span.start or t.end > span.end for t in tokens)
    return [R.VERB_UNIT_OUTSIDE_SPAN] if outside else []


def unit_target(sentence, tokens):
    """Display span covering the unit, with one part per run of adjacent tokens."""
    runs = []
    for token in tokens:
        if runs and token.i == runs[-1][-1].i + 1:
            runs[-1].append(token)
        else:
            runs.append([token])
    target = char_span(sentence, tokens[0].start, tokens[-1].end)
    target["parts"] = [char_span(sentence, run[0].start, run[-1].end) for run in runs]
    return target


def relative_adverb_risk(view, span):
    tokens = trim_tokens(view.within(span.start, span.end))
    if not tokens or tokens[0].text.lower() not in RELATIVE_ADVERBS:
        return []
    before = [t for t in view.tokens if t.end <= span.start and not t.is_punct]
    before = [t for t in before if not t.text.isspace()]
    risky = bool(before) and before[-1].pos in {"NOUN", "PROPN", "NUM"}
    return [R.POSSIBLE_RELATIVE_ADVERB] if risky else []


def difficulty(view, spans):
    level = max((s.level for s in spans), default=1)
    if view.word_count <= 20 and level <= 2:
        return "easy"
    return "hard" if view.word_count > 35 or level >= 3 else "medium"


def evidence(view, span, head=None):
    subtree = trim_tokens(view.subtree(head)) if head else ()
    return {
        "tag_role": span.role,
        "tag_level": span.level,
        "tag_span": {"start": span.start, "end": span.end},
        "parser": {
            "head": head.text if head else None,
            "head_token": head.i if head else None,
            "dep": head.dep if head else None,
            "finite": finite(head, view) if head else None,
            "subtree": token_bounds(subtree),
        },
    }


def ambiguous(span, sentence, target=None):
    text = target["text"] if target else span.text
    first = sentence.find(text)
    repeated = bool(text) and first >= 0 and sentence.find(text, first + 1) >= 0
    return [R.AMBIGUOUS_SPAN_LOCATION] if span.ambiguous or repeated else []


@dataclass
class Context:
    source: dict
    spans: tuple
    view: object
    candidates: list = field(default_factory=list)
    rejections: list = field(default_factory=list)

    @property
    def sentence(self):
        return self.source["sentence"]

    def reject(self, template, reasons, span=None, variant="", node=None):
        self.rejections.append(
            {
                "source": self.source,
                "template": template,
                "variant": variant,
                "node_id": node,
                "status": "rejected",
                "reasons": sorted(set(reasons)),
                "scope": "template",
                "difficulty": difficulty(self.view, self.spans),
                "target": char_span(self.sentence, span.start, span.end) if span else None,
                "tag_role": span.role if span else None,
            }
        )

    def emit(
        self,
        template,
        node,
        prompt,
        span,
        head=None,
        *,
        target=None,
        options=None,
        answer_spans=None,
        option=None,
        kind="option",
        grading=None,
        distractors=None,
        reasons=(),
        variant="",
        extra=None,
    ):
        identity = target or char_span(self.sentence, span.start, span.end)
        parser_evidence = evidence(self.view, span, head)
        parser_evidence.update(extra or {})
        reasons = sorted(set(reasons) | set(ambiguous(span, self.sentence, target)))
        item = {
            "item_id": item_id(
                self.source,
                template,
                identity["start"],
                identity["end"],
                f"{variant}|{span.role}|{span.level}",
            ),
            "generator_version": GENERATOR_VERSION,
            "template": template,
            "node_id": node,
            "source": self.source,
            "prompt_zh": prompt,
            "target": target,
            "options": options,
            "answer": {"kind": kind, "spans": answer_spans or [], "option": option},
            "grading": grading or {"mode": "exact_option"},
            "distractors": distractors or [],
            "difficulty": difficulty(self.view, self.spans),
            "status": "needs_review" if reasons else "auto_pass",
            "reasons": reasons,
            "evidence": parser_evidence,
        }
        self.candidates.append(item)
        return item


def main_selection(ctx):
    level_one = [s for s in ctx.spans if s.level == 1]
    verbs = [s for s in level_one if s.role in MAIN_VERB_ROLES]
    reasons = []
    if not verbs:
        reasons.append(R.NO_MAIN_VERB_TAG)
    if len(verbs) > 1:
        reasons.append(R.MULTIPLE_MAIN_VERBS)
    if any(s.role in COORDINATED_PREDICATE_ROLES for s in level_one):
        reasons.append(R.COORDINATED_MAIN_VERBS)
    if any(s.role in COORDINATE_CLAUSE_ROLES for s in level_one):
        reasons.append(R.COORDINATED_MAIN_CLAUSES)
    return verbs[0] if len(verbs) == 1 else None, reasons


def main_checks(ctx, span):
    root, reasons = ctx.view.root, []
    if not (span.start <= root.start and root.end <= span.end):
        reasons.append(R.PARSER_ROOT_OUTSIDE_VERB_SPAN)
    if any(clause_kind(s) and s.start <= root.start and root.end <= s.end for s in ctx.spans):
        reasons.append(R.PARSER_ROOT_INSIDE_SUBORDINATE_SPAN)
    return reasons


def main_distractors(ctx, unit):
    """Verbs inside deeper clause/non-finite spans, each shown as its full verb unit.

    Returns the distractors and the review reasons: a unit reaching past the span it was
    found in ("to" before an infinitive tagged from "close", a "not" the parser hung on
    "identified") means the tags and the parse disagree, as for the main unit.
    """
    targets, reasons = {}, []
    excluded = {t.i for t in unit}
    for span in ctx.spans:
        if span.level < 2 or not (clause_kind(span) or span.role in NON_FINITE_ROLES):
            continue
        inside = ctx.view.within(span.start, span.end)
        indexes = {t.i for t in inside}
        for token in inside:
            if token.pos not in {"VERB", "AUX"} or token.i in excluded:
                continue
            if token.dep in VERB_UNIT_DEPS and token.head in indexes:
                continue  # An auxiliary shown as part of its head's unit.
            unit_tokens = verb_unit(ctx.view, token)
            parts = [t for t in unit_tokens if t.i not in excluded]
            reasons += outside_span(parts, span)
            value = targets.setdefault(token.i, {**unit_target(ctx.sentence, parts), "roles": []})
            if span.role not in value["roles"]:
                value["roles"].append(span.role)
    return [targets[index] for index in sorted(targets)], reasons


def main_verb(ctx):
    span, reasons = main_selection(ctx)
    root = ctx.view.root
    if any(c.dep == "conj" and c.pos in {"VERB", "AUX"} for c in ctx.view.children(root)):
        reasons.append(R.COORDINATED_MAIN_VERBS)
    if reasons:
        ctx.reject(TEMPLATES[0], reasons, span)
        return None, reasons
    unit = verb_unit(ctx.view, root, span.start, span.end)
    distractors, distractor_reasons = main_distractors(ctx, unit)
    reasons = main_checks(ctx, span) + outside_span(verb_unit(ctx.view, root), span)
    reasons += distractor_reasons
    item = ctx.emit(
        TEMPLATES[0],
        "G-L01" if distractors else "G-S01",
        "点出这句话的主句谓语动词。",
        span,
        root,
        answer_spans=[token_span(ctx.sentence, t) for t in unit],
        kind="tokens",
        grading={
            "mode": "contains_root_subset_of_verb_unit",
            "required_root": token_span(ctx.sentence, root),
        },
        distractors=distractors,
        reasons=reasons,
        variant="main",
        extra={"verb_unit_tokens": [t.i for t in unit]},
    )
    return item, []


def type_matches(view, head, kind):
    """A finite head with the clause dep; a coordinate clause has its own subject and no
    subordinator ("and that ..." is a noun clause, "and usually refer to ..." a predicate).
    An adverbial clause led by "for" ("for they shared ...") is coordinate as taught."""
    if not (finite(head, view) and head.dep in CLAUSE_DEPS[kind]):
        return False
    children = view.children(head)
    marks = {c.text.lower() for c in children if c.dep == "mark"}
    if kind == "adverbial":
        return "for" not in marks
    if kind != "coordinate":
        return True
    return marks <= COORDINATING_MARKS and any(c.dep in CLAUSE_SUBJECT_DEPS for c in children)


def boundary_reasons(ctx, head, tokens, kind):
    """Clause targets must match the parser subtree, as T2 already requires (review F3)."""
    subtree = trim_tokens(ctx.view.subtree(head), kind == "coordinate")
    return [] if token_bounds(subtree) == token_bounds(tokens) else [R.BOUNDARY_MISMATCH]


def target_analysis(ctx, span, kind):
    tokens = trim_tokens(ctx.view.within(span.start, span.end), kind == "coordinate")
    heads = centers(tokens)
    reasons = [] if len(heads) == 1 else [R.SPAN_NOT_CONSTITUENT]
    return tokens, heads[0] if len(heads) == 1 else None, reasons


def clause_boundaries(ctx):
    for kind, roles in CLAUSE_ROLES.items():
        spans = [s for s in ctx.spans if s.role in roles]
        for span in spans:
            if len(spans) != 1:
                ctx.reject(
                    TEMPLATES[1],
                    [R.MULTIPLE_TARGETS_SAME_TYPE],
                    span,
                    variant=kind,
                    node=CLAUSE_NODES[kind],
                )
                continue
            tokens, head, reasons = target_analysis(ctx, span, kind)
            if head:
                if not type_matches(ctx.view, head, kind):
                    reasons.append(R.CLAUSE_TYPE_MISMATCH)
                reasons.extend(boundary_reasons(ctx, head, tokens, kind))
            if kind == "adverbial":
                reasons.extend(relative_adverb_risk(ctx.view, span))
            answer = close_quotes(
                ctx.sentence, span_from_tokens(ctx.sentence, tokens), span.start, span.end
            )
            ctx.emit(
                TEMPLATES[1],
                CLAUSE_NODES[kind],
                f"划出句中的{CLAUSE_LABELS[kind]}（从第一个词划到最后一个词）。",
                span,
                head,
                answer_spans=[answer] if answer else [],
                kind="span",
                grading={
                    "mode": "exact_span_ignore_punct",
                    "allow_leading_conjunction": kind == "coordinate",
                },
                reasons=reasons,
                variant=kind,
            )


def classify_clauses(ctx):
    for span in ctx.spans:
        kind = classification_kind(span)
        if not kind:
            continue
        tokens, head, reasons = target_analysis(ctx, span, kind)
        if head:
            matches = (
                (not finite(head, ctx.view) or head.dep == "prep")
                if kind == "phrase"
                else type_matches(ctx.view, head, kind)
            )
            if not matches:
                reasons.append(R.CLAUSE_TYPE_MISMATCH)
            if kind != "phrase":
                reasons.extend(boundary_reasons(ctx, head, tokens, kind))
        if kind == "adverbial":
            reasons.extend(relative_adverb_risk(ctx.view, span))
        option = TYPE_OPTIONS[-1] if kind == "phrase" else CLAUSE_LABELS[kind]
        ctx.emit(
            TEMPLATES[2],
            "G-C03",
            "判断句中【】标出的部分是什么。",
            span,
            head,
            target=close_quotes(
                ctx.sentence, span_from_tokens(ctx.sentence, tokens), span.start, span.end
            ),
            options=TYPE_OPTIONS,
            option=option,
            reasons=reasons,
            variant=kind,
        )


def subordinator(ctx, tokens, head):
    words = [t.text.lower() for t in tokens]
    marks = {t.i for t in ctx.view.children(head) if t.dep == "mark"} if head else set()
    phrases = sorted(SUBORDINATOR_RELATIONS, key=lambda x: (-len(x.split()), x))
    for phrase in phrases:
        parts = phrase.split()
        for index in range(len(words) - len(parts) + 1):
            matched = words[index : index + len(parts)] == parts
            anchored = any(t.i in marks for t in tokens[index : index + len(parts)])
            if matched and (anchored or (not marks and index == 0)):
                return phrase
    return next((t.text.lower() for t in tokens if t.i in marks), words[0] if words else "")


def adverbial_relations(ctx):
    for span in ctx.spans:
        if span.role not in ADVERBIAL_CLAUSE_ROLES:
            continue
        if span.role not in RELATION_BY_ROLE:
            ctx.reject(TEMPLATES[3], [R.NO_RELATION_LABEL], span, node="G-C11")
            continue
        relation = RELATION_BY_ROLE[span.role]
        if relation not in RELATION_OPTIONS:
            ctx.reject(TEMPLATES[3], [R.RELATION_LABEL_OUT_OF_SCOPE], span, node="G-C11")
            continue
        tokens, head, reasons = target_analysis(ctx, span, "adverbial")
        word = subordinator(ctx, tokens, head)
        if word in AMBIGUOUS_SUBORDINATORS:
            reasons.append(R.SUBORDINATOR_AMBIGUOUS)
        elif word not in SUBORDINATOR_RELATIONS:
            reasons.append(R.SUBORDINATOR_UNKNOWN)
        elif SUBORDINATOR_RELATIONS[word] != relation:
            reasons.append(R.SUBORDINATOR_MISMATCH)
        reasons.extend(relative_adverb_risk(ctx.view, span))
        if head:
            reasons.extend(boundary_reasons(ctx, head, tokens, "adverbial"))
        ctx.emit(
            TEMPLATES[3],
            "G-C11",
            "句中【】标出的状语从句表示什么关系？",
            span,
            head,
            target=close_quotes(
                ctx.sentence, span_from_tokens(ctx.sentence, tokens), span.start, span.end
            ),
            options=RELATION_OPTIONS,
            option=relation,
            reasons=reasons,
            variant=span.role,
            extra={"subordinator": word},
        )


def subject_boundary(ctx):
    verb, reasons = main_selection(ctx)
    subjects = [s for s in ctx.spans if s.level == 1 and s.role == "subject"]
    if len(subjects) != 1:
        reasons.append(R.SPLIT_SUBJECT)
    if any(t.dep == "expl" for t in ctx.view.children(ctx.view.root)):
        reasons.append(R.EXISTENTIAL)
    if verb and len(subjects) == 1 and subjects[0].start >= verb.start:
        reasons.append(R.SUBJECT_AFTER_VERB)
    if reasons:
        ctx.reject(TEMPLATES[4], reasons, node="G-S02")
        return
    subject = subjects[0]
    tokens = trim_tokens(ctx.view.within(subject.start, verb.start))
    heads = [
        t
        for t in ctx.view.children(ctx.view.root)
        if t.dep in {"nsubj", "nsubjpass", "csubj", "csubjpass"}
    ]
    head = heads[0] if len(heads) == 1 else None
    if not head or token_bounds(trim_tokens(ctx.view.subtree(head))) != token_bounds(tokens):
        reasons.append(R.SUBJECT_MISMATCH)
    reasons.extend(ambiguous(verb, ctx.sentence))
    answer = close_quotes(
        ctx.sentence, span_from_tokens(ctx.sentence, tokens), subject.start, verb.start
    )
    ctx.emit(
        TEMPLATES[4],
        "G-S02",
        "划出这句话的完整主语（包括修饰它的成分）。",
        subject,
        head,
        answer_spans=[answer] if answer else [],
        kind="span",
        reasons=reasons,
        grading={"mode": "exact_span_ignore_punct", "allow_leading_conjunction": False},
        variant="subject",
        extra={"predicate_start": verb.start},
    )


def finite_targets(ctx, main_item, main_rejections):
    if main_item:
        span, _ = main_selection(ctx)
        # finite_or_not redoes the unit check for the root; T1's distractor check is not ours.
        reasons = [r for r in main_item["reasons"] if r != R.VERB_UNIT_OUTSIDE_SPAN]
        yield span, ctx.view.root, "main", reasons
    else:
        ctx.reject(TEMPLATES[5], main_rejections, variant="main", node="G-N01")
    for span in ctx.spans:
        if span.role in RELATIVE_CLAUSE_ROLES | ADVERBIAL_CLAUSE_ROLES:
            variant = "subordinate"
        elif span.role in NON_FINITE_ROLES:
            variant = "non_finite"
        else:
            continue
        tokens, head, reasons = target_analysis(ctx, span, clause_kind(span))
        if head is None:
            head = next((t for t in tokens if t.pos in {"VERB", "AUX"}), None)
        if head is None or head.pos not in {"VERB", "AUX"}:
            ctx.reject(
                TEMPLATES[5], [*reasons, R.FINITENESS_MISMATCH], span, variant=variant, node="G-N01"
            )
            continue
        yield span, head, variant, reasons


def finite_or_not(ctx, main_item, main_rejections):
    for span, head, variant, original_reasons in finite_targets(ctx, main_item, main_rejections):
        reasons = list(original_reasons)
        if variant == "main":
            matches, option = head.dep == "ROOT", FINITE_OPTIONS[0]
        elif variant == "subordinate":
            matches = finite(head, ctx.view) and head.dep in {"relcl", "advcl"}
            option = FINITE_OPTIONS[1]
        else:
            matches, option = not finite(head, ctx.view), FINITE_OPTIONS[2]
        if not matches:
            reasons.append(R.FINITENESS_MISMATCH)
        unit = verb_unit(ctx.view, head)
        reasons.extend(outside_span(unit, span))
        participle = (
            variant == "non_finite"
            and not span.role.startswith("gerund")
            and ("particip" in span.role or head.tag in {"VBG", "VBN"})
        )
        ctx.emit(
            TEMPLATES[5],
            "G-N04" if participle else "G-N01",
            "句中【】里的动词在句子里是什么身份？",
            span,
            head,
            target=unit_target(ctx.sentence, unit),
            options=FINITE_OPTIONS,
            option=option,
            reasons=reasons,
            variant=f"{variant}:{span.role}:{span.start}:{span.end}",
            extra={"variant": variant},
        )


def generate_templates(source, spans, view):
    ctx = Context(source, spans, view)
    main_item, main_rejections = main_verb(ctx)
    clause_boundaries(ctx)
    classify_clauses(ctx)
    adverbial_relations(ctx)
    subject_boundary(ctx)
    finite_or_not(ctx, main_item, main_rejections)
    unique = {}
    for item in ctx.candidates:
        previous = unique.setdefault(item["item_id"], item)
        if previous != item:
            raise ValueError(f"Conflicting item identity: {item['item_id']}")
    return list(unique.values()), ctx.rejections
