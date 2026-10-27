"""Dependency-free token views and the sole, lazy spaCy adapter."""

import json
from dataclasses import asdict, dataclass
from hashlib import sha1
from pathlib import Path

MODEL_NAME = "en_core_web_trf"
MODEL_VERSION = "3.8.0"


@dataclass(frozen=True)
class Token:
    i: int
    text: str
    start: int
    end: int
    pos: str
    tag: str
    dep: str
    head: int
    morph_verbform: tuple[str, ...] = ()
    is_punct: bool = False


@dataclass(frozen=True)
class ParseView:
    tokens: tuple[Token, ...]

    @property
    def root(self):
        return next((t for t in self.tokens if t.dep == "ROOT"), None)

    @property
    def word_count(self):
        return sum(not t.is_punct and not t.text.isspace() for t in self.tokens)

    def children(self, token):
        return tuple(t for t in self.tokens if t.head == token.i and t.i != token.i)

    def within(self, start, end):
        return tuple(t for t in self.tokens if start <= t.start and t.end <= end)

    def subtree(self, token):
        seen, pending = set(), [token.i]
        while pending:
            index = pending.pop()
            if index in seen:
                continue
            seen.add(index)
            pending.extend(t.i for t in self.children(self.tokens[index]))
        return self.tokens[min(seen) : max(seen) + 1]


def finite(token, view):
    finite_tags = {"VBD", "VBZ", "VBP", "MD"}
    return (
        "Fin" in token.morph_verbform
        or token.tag in finite_tags
        or any(c.dep in {"aux", "auxpass"} and c.tag in finite_tags for c in view.children(token))
    )


def unit_symbol(tokens):
    """A % after a number belongs to it ("A full 94%"), though spaCy marks it punctuation."""
    return (
        len(tokens) > 1 and tokens[-1].text == "%" and any(ch.isdigit() for ch in tokens[-2].text)
    )


def trim_tokens(tokens, coordinate=False):
    tokens = list(tokens)
    while tokens and (tokens[0].is_punct or tokens[0].text.isspace()):
        tokens.pop(0)
    while tokens and (tokens[-1].is_punct or tokens[-1].text.isspace()) and not unit_symbol(tokens):
        tokens.pop()
    if coordinate and tokens and tokens[0].text.lower() in {"and", "but", "or"}:
        return trim_tokens(tokens[1:])
    return tuple(tokens)


def token_bounds(tokens):
    return (tokens[0].i, tokens[-1].i + 1) if tokens else None


def centers(tokens):
    inside = {t.i for t in tokens}
    return tuple(
        t for t in tokens if not t.is_punct and not t.text.isspace() and t.head not in inside
    )


def from_doc(doc):
    return ParseView(
        tuple(
            Token(
                t.i,
                t.text,
                t.idx,
                t.idx + len(t),
                t.pos_,
                t.tag_,
                t.dep_,
                t.head.i,
                tuple(t.morph.get("VerbForm")),
                t.is_punct,
            )
            for t in doc
        )
    )


def load_parser(seed):
    import spacy

    spacy.require_cpu()
    spacy.util.fix_random_seed(seed)
    nlp = spacy.load(MODEL_NAME)
    if nlp.meta["version"] != MODEL_VERSION:
        raise RuntimeError(f"Required {MODEL_NAME} {MODEL_VERSION}")
    return nlp, {
        "spacy": spacy.__version__,
        "model_name": MODEL_NAME,
        "model_version": nlp.meta["version"],
        "device": "CPU",
    }


class ParseCache:
    """Sentence SHA-1 + model version; verify adapter version before reuse."""

    def __init__(self, path, environment):
        self.path = Path(path)
        self.environment = environment
        self.rows = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                if row["environment"] == environment:
                    self.rows[row["key"]] = row

    def key(self, sentence):
        return f"{sha1(sentence.encode()).hexdigest()}|{MODEL_NAME}-{MODEL_VERSION}"

    def parse(self, sentence, nlp):
        key = self.key(sentence)
        if key not in self.rows:
            view = from_doc(nlp(sentence))
            row = {
                "key": key,
                "environment": self.environment,
                "tokens": [asdict(t) for t in view.tokens],
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            self.rows[key] = row
            return view
        return ParseView(
            tuple(
                Token(**{**t, "morph_verbform": tuple(t["morph_verbform"])})
                for t in self.rows[key]["tokens"]
            )
        )
