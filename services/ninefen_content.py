"""Convert version-bound Ninefen papers using an independently supplied answer key.

This module performs no IO or inference. It never derives answers from analysis,
transcripts, user answers, or the source's optional ``rightAnswer`` field.
"""

from __future__ import annotations

import html
import json
import math
import re
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from services.exam_sprint import content_digest


class NinefenContentError(ValueError):
    """The paper cannot safely be published in the current practice renderer."""


TYPES = {
    "single-choice": (1, "单选题"),
    "multiple-choice": (2, "多选题"),
    "fill-in-the-blank": (3, "填空题"),
    "matching": (4, "匹配题"),
    "map": (7, "匹配题"),
}
JUDGMENTS = {"TRUE", "FALSE", "NOT GIVEN", "YES", "NO"}


def _object(value, label):
    if not isinstance(value, dict):
        raise NinefenContentError(f"Invalid {label}")
    return value


def _identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,30}", value):
        raise NinefenContentError(f"Invalid {label}: IDs must remain decimal strings")
    return value


def _rows(value, label, *, required=True):
    if not isinstance(value, list) or (required and not value):
        raise NinefenContentError(f"Invalid {label}")
    return [_object(row, label) for row in value]


def _media(url, media_map):
    if not url:
        return ""
    value = media_map.get(url)
    if not isinstance(value, str):
        raise NinefenContentError("Required media has not been cached")
    parsed = urlsplit(value)
    decoded = unquote(value)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or not value.startswith("/practice/sprint/assets/")
        or ".." in decoded.split("/")
        or "\\" in decoded
        or re.search(r"[\x00-\x20\"'<>]", decoded)
    ):
        raise NinefenContentError("Media must use the local sprint asset route")
    return value


class _Markup(HTMLParser):
    """Keep a small structural vocabulary, replacing numbered source inputs."""

    TAGS = {
        "b",
        "i",
        "br",
        "p",
        "div",
        "ul",
        "ol",
        "li",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "th",
        "td",
        "caption",
        "colgroup",
        "col",
    }
    ACTIVE = {
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "svg",
        "math",
        "form",
        "button",
        "textarea",
        "select",
    }

    def __init__(self, questions=None):
        super().__init__(convert_charrefs=True)
        self.questions = questions or {}
        self.output = []
        self.plain = []
        self.placeholders = set()
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self.ACTIVE or any(key.lower().startswith("on") for key in attrs):
            raise NinefenContentError("Executable or interactive source markup")
        if tag == "input":
            number = str(attrs.get("placeholder", "")).strip()
            qid = self.questions.get(number)
            if qid is None:
                raise NinefenContentError("Source input has no matching question number")
            self.output.append(f"${qid}$")
            self.placeholders.add(qid)
            return
        if tag == "img":
            if not attrs.get("src"):
                raise NinefenContentError("Image has no source")
            self.images.append(attrs["src"])
            return
        tag = {"strong": "b", "em": "i"}.get(tag, tag)
        if tag in self.TAGS:
            safe_attrs = ""
            for key in ("rowspan", "colspan"):
                value = attrs.get(key)
                if value is not None:
                    if not re.fullmatch(r"[0-9]{1,2}", value) or not 1 <= int(value) <= 99:
                        raise NinefenContentError("Invalid table span")
                    safe_attrs += f' {key}="{int(value)}"'
            self.output.append(f"<{tag}{safe_attrs}>")
        if tag in {"br", "p", "div", "tr", "li"}:
            self.plain.append("\n")

    def handle_endtag(self, tag):
        tag = {"strong": "b", "em": "i"}.get(tag, tag)
        if tag in self.TAGS and tag not in {"br", "col"}:
            self.output.append(f"</{tag}>")
        if tag in {"p", "div", "tr", "li"}:
            self.plain.append("\n")

    def handle_data(self, data):
        if re.search(r"\$[^$\s]+\$", data):
            raise NinefenContentError("Ambiguous source placeholder text")
        self.output.append(html.escape(data, quote=False))
        self.plain.append(data)


def _markup(value, questions=None):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise NinefenContentError("Expected source text")
    parser = _Markup(questions)
    parser.feed(value)
    parser.close()
    return parser


def _text(value):
    parser = _markup(value)
    if parser.images:
        raise NinefenContentError("Unexpected image inside plain text field")
    return re.sub(r"[ \t\r\f\v]+", " ", "".join(parser.plain)).strip()


def _options(rows):
    options = []
    for row in _rows(rows or [], "options", required=False):
        key = _text(row.get("optionNum")).upper()
        if not re.fullmatch(r"[A-Z]+|[ivx]+", key, flags=re.I):
            raise NinefenContentError("Unsupported option key")
        options.append({"key": key, "text": _text(row.get("optionContent") or row.get("option"))})
    if len({row["key"] for row in options}) != len(options):
        raise NinefenContentError("Duplicate option key")
    return options


def _answer(value, options, kind):
    values = value if isinstance(value, list) else [value]
    if not values or any(not isinstance(v, str) or not v.strip() for v in values):
        raise NinefenContentError("Missing independently supplied answer")
    values = [v.strip() for v in values]
    if any(len(v) > 300 or re.search(r"[<>\x00-\x1f]", v) for v in values):
        raise NinefenContentError("Invalid answer text")
    if not options:
        return "/".join(dict.fromkeys(values))
    keys = {row["key"] for row in options}
    letters = [v.strip().upper() for item in values for v in re.split(r"[,/]", item)]
    if kind != "multiple-choice" and len(letters) != 1:
        raise NinefenContentError("Single-choice answer must select exactly one option")
    if not set(letters) <= keys or len(set(letters)) != len(letters):
        raise NinefenContentError("Answer is not a distinct offered option")
    return ",".join(letters)


def _question(raw, bank, kind, answers, seen):
    qid = _identifier(raw.get("id"), "question ID")
    if qid in seen:
        raise NinefenContentError("Duplicate question ID")
    seen.add(qid)
    if qid not in answers:
        raise NinefenContentError(f"Missing independently supplied answer for {qid}")
    number = str(raw.get("qNumber", ""))
    if not re.fullmatch(r"[1-9][0-9]?", number):
        raise NinefenContentError("Unsupported question number")
    options = _options(raw.get("options")) or bank
    if kind != "fill-in-the-blank" and not options:
        raise NinefenContentError("Choice or matching question has no options")
    answer = _answer(answers[qid], options, kind)
    if options and {o["text"].upper() for o in options} <= JUDGMENTS:
        translated = {o["key"]: o["text"].upper() for o in options}
        answer = translated[answer]
        options = [{"key": o["text"].upper(), "text": o["text"].upper()} for o in options]
    analysis = [
        _text(row.get("content"))
        for row in _rows(raw.get("analyses") or [], "analyses", required=False)
    ]
    return {
        "id": qid,
        "source_question_id": qid,
        "number": int(number),
        "title": _text(raw.get("question")),
        "answer": answer,
        "answers": answer.split("/"),
        "options": options,
        "analysis": "\n".join(filter(None, analysis)) or _text(raw.get("analysisText")),
        "source_sentence_index": raw.get("sentenceIndex"),
        "source_heading_paragraph_index": raw.get("headingParagraphIndex"),
    }


def _shared_multiple(raw, questions, bank):
    if raw["type"] != "multiple-choice" or len(questions) == 1:
        return bank, False
    stems = {q["title"] for q in questions}
    options = bank or questions[0]["options"]
    if len(stems) != 1 or not options or any(q["options"] != options for q in questions):
        raise NinefenContentError("Ambiguous multi-question selection group")
    supplied = [q["answer"].split(",") for q in questions]
    combined = list(dict.fromkeys(letter for row in supplied for letter in row))
    if len(combined) != len(questions):
        raise NinefenContentError("Selection count does not match question marks")
    if not (all(len(row) == 1 for row in supplied) or all(row == supplied[0] for row in supplied)):
        raise NinefenContentError("Inconsistent combined selection answers")
    for question in questions:
        question["answer"] = ",".join(combined)
        question["answers"] = [question["answer"]]
        question["options"] = []
        question["uses_group_options"] = True
    return options, True


def _group(raw, subject, answers, media_map, seen):
    kind = raw.get("type")
    if kind not in TYPES:
        raise NinefenContentError(f"Unsupported question type: {kind}")
    source_questions = _rows(raw.get("questions"), "questions")
    if any(
        q.get("questionGroupId") != raw.get("id") or q.get("type") != kind for q in source_questions
    ):
        raise NinefenContentError("Question belongs to another group or type")
    bank = _options(raw.get("options"))
    if not bank and kind in {"matching", "map", "multiple-choice"}:
        bank = _options(source_questions[0].get("options"))
    questions = [_question(q, bank, kind, answers, seen) for q in source_questions]
    if len({q["number"] for q in questions}) != len(questions):
        raise NinefenContentError("Duplicate question number")
    bank, combined = _shared_multiple(raw, questions, bank)
    numbers = {str(q["number"]): q["id"] for q in questions}
    markup = _markup(raw.get("contentHtml"), numbers)
    images = list(
        dict.fromkeys(filter(None, [raw.get("imageUrl") or raw.get("image"), *markup.images]))
    )
    if len(images) > 1:
        raise NinefenContentError("Multiple group images require a supported layout")
    image = _media(images[0], media_map) if images else ""
    collect = "".join(markup.output).strip()
    if collect and not combined:
        for question in questions:
            if question["id"] not in markup.placeholders:
                if not question["title"]:
                    raise NinefenContentError("Question has no prompt or source blank")
                collect += f'<p>{html.escape(question["title"])} ${question["id"]}$</p>'
    if not collect and any(not q["title"] for q in questions):
        raise NinefenContentError("Question has no prompt or source blank")
    desc = "\n".join(
        filter(
            None,
            [_text(raw.get("qRange")), _text(raw.get("description") or raw.get("typeDescription"))],
        )
    )
    result = {
        "group_id": _identifier(raw.get("id"), "group ID"),
        "source_type": kind,
        "source_subtype": raw.get("questionSubtype"),
        "type": TYPES[kind][0],
        "type_name": TYPES[kind][1],
        "title": _text(raw.get("title") or raw.get("title1")),
        "question_title": questions[0]["title"] if combined else _text(raw.get("title2")),
        "desc": desc,
        "collect": "" if combined else collect,
        "table": None,
        "img_url": image,
        "img_local": "",
        "source_reuse": raw.get("reuse"),
    }
    if subject == "listening":
        return _listening_group(result, questions, bank, combined)
    result["questions"] = questions
    result["collect_option"] = {"title": "", "list": bank}
    for question in questions:
        question["input_mode"] = "select" if bank else "choice" if question["options"] else "text"
        if bank and not question["options"]:
            question["uses_group_options"] = True
    return result


def _listening_group(result, questions, bank, combined):
    def options(rows):
        return [{"title": o["key"], "content": o["text"]} for o in rows]

    result["items"] = [{**q, "options": options(q["options"])} for q in questions]
    result["collect_options"] = {"title": "", "list": options(bank)}
    if result["source_type"] == "multiple-choice" and not combined:
        result["type"] = 9
    if bank and result["source_type"] in {"matching", "map"}:
        for question in result["items"]:
            question["options"] = []
    return result


def _article(part):
    value = part.get("articleJson")
    if isinstance(value, str) and value.strip():
        try:
            value = json.loads(value)
        except ValueError as exc:
            raise NinefenContentError("Invalid article JSON") from exc
    if not isinstance(value, dict):
        raise NinefenContentError("Structured article or transcript is required")
    return value, _rows(value.get("segments"), "article segments")


def _segment_text(segment):
    if segment.get("text"):
        return _text(segment["text"])
    sentences = _rows(segment.get("sentences") or [], "sentences", required=False)
    return " ".join(_text(sentence.get("text")) for sentence in sentences).strip()


def _reading_content(part):
    article, segments = _article(part)
    texts = [_segment_text(segment) for segment in segments]
    if not all(texts):
        raise NinefenContentError("Article contains an empty paragraph")
    labels = [re.match(r"^([A-Z])\s+(.+)$", text, flags=re.S) for text in texts]
    labeled = all(labels) and [match.group(1) for match in labels] == [
        chr(65 + i) for i in range(len(labels))
    ]
    return {
        "title": _text(article.get("title") or part.get("title")),
        "summary": _text(part.get("subtitle")),
        "paragraphs": [
            {
                "label": labels[i].group(1) if labeled else "",
                "text": labels[i].group(2) if labeled else text,
            }
            for i, text in enumerate(texts)
        ],
    }


def _transcript(part):
    _data, segments = _article(part)
    rows = []
    for index, segment in enumerate(segments):
        text = _segment_text(segment)
        if not text:
            raise NinefenContentError("Transcript contains an empty segment")
        start, end = segment.get("start_time"), segment.get("end_time")
        if start is None and end is None:
            start, end = 0, 0
        if (
            any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in (start, end)
            )
            or not 0 <= start <= end
        ):
            raise NinefenContentError("Invalid transcript timing")
        rows.append(
            {
                "order": index,
                "en_text": text,
                "cn_text": "",
                "start_time": round(start * 1000),
                "end_time": round(end * 1000),
            }
        )
    return rows


def _part_number(part, subject):
    label = part.get("partNum") or part.get("label")
    match = re.fullmatch(r"Part ([1-4])", str(label))
    if not match or (subject == "reading" and match.group(1) == "4"):
        raise NinefenContentError("Unknown source part number")
    return int(match.group(1))


def convert_ninefen_unit(payload, *, answers_by_question_id, media_map, expected_source_sha256):
    """Return immutable-ready documents; all required answers/media must be present.

    ``media_map`` maps original source URLs to ``/practice/sprint/assets/...``.
    The caller owns authorization/provenance and writes these pure results only
    after it can publish every document and media file together.
    """
    data = _object(_object(payload, "response").get("data"), "exam")
    if payload.get("code") not in (200, "200"):
        raise NinefenContentError("Source did not return a successful exam")
    digest = content_digest(payload)
    if not isinstance(expected_source_sha256, str) or digest != expected_source_sha256:
        raise NinefenContentError("Answer key does not match this source version")
    unit_id = _identifier(data.get("id"), "unit ID")
    versioned_id = f"ninefen_{unit_id}_{digest[:12]}"
    subject = data.get("channel")
    if subject not in {"listening", "reading"}:
        raise NinefenContentError("Unsupported source subject")
    if not isinstance(answers_by_question_id, dict) or any(
        not isinstance(k, str) for k in answers_by_question_id
    ):
        raise NinefenContentError("Answer map must use string question IDs")
    if not isinstance(media_map, dict):
        raise NinefenContentError("Invalid media map")
    parts = _rows(data.get("parts"), "parts")
    seen, seen_parts, documents, passages = set(), set(), [], []
    metadata = {
        "source": "ninefen",
        "source_id": unit_id,
        "source_content_sha256": digest,
        "source_version_title": _text(data.get("title")),
    }
    for part in parts:
        part_id = _identifier(part.get("id"), "part ID")
        number = _part_number(part, subject)
        if (
            part.get("channel") != subject
            or part.get("entryMode") != "exam"
            or number in seen_parts
        ):
            raise NinefenContentError("Invalid, unavailable or duplicate source part")
        seen_parts.add(number)
        source_groups = _rows(part.get("groups"), "groups")
        if any(group.get("partId") != part_id for group in source_groups):
            raise NinefenContentError("Group belongs to another source part")
        groups = [
            _group(g, subject, answers_by_question_id, media_map, seen) for g in source_groups
        ]
        questions = [
            q for group in groups for q in group["items" if subject == "listening" else "questions"]
        ]
        if (
            type(part.get("total")) is not int
            or len(questions) != part["total"]
            or len({q["number"] for q in questions}) != len(questions)
        ):
            raise NinefenContentError("Source question total is incomplete or duplicated")
        common = {
            **metadata,
            "source_part_id": part_id,
            "source_part_number": number,
            "groups": groups,
            "question_count": len(questions),
            "question_name": f'Questions {min(q["number"] for q in questions)}–{max(q["number"] for q in questions)}',
        }
        if subject == "reading":
            passages.append(
                {
                    **common,
                    "id": f"{versioned_id}_p{number}",
                    "part_id": part_id,
                    "passage": len(passages) + 1,
                    "title": _text(part.get("title")),
                    "content": _reading_content(part),
                    "question_type": [group["type_name"] for group in groups],
                }
            )
        else:
            local_id = f"{versioned_id}_p{number}"
            audio_url = part.get("audioUrl") or part.get("exAudioUrl")
            if not audio_url:
                raise NinefenContentError("Listening exam has no audio")
            document = {
                **common,
                "id": local_id,
                "paper_id": part_id,
                "in_book": "九分学长",
                "test_name": metadata["source_version_title"],
                "part_title": f"Part {number}",
                "part_number": number,
                "audio": {"local_path": _media(audio_url, media_map)},
                "content": _transcript(part),
            }
            documents.append(
                {
                    "id": local_id,
                    "source_part_id": part_id,
                    "part_number": number,
                    "relative_path": f"listening/{local_id}.json",
                    "payload": document,
                }
            )
    if set(answers_by_question_id) != seen:
        raise NinefenContentError("Answer map contains unknown question IDs")
    if subject == "reading":
        local_id = versioned_id
        document = {
            **metadata,
            "id": local_id,
            "title": metadata["source_version_title"],
            "passages": passages,
            "question_count": len(seen),
        }
        documents.append(
            {
                "id": local_id,
                "source_part_id": passages[0]["source_part_id"] if len(passages) == 1 else None,
                "part_number": 1 if len(passages) == 1 else None,
                "source_part_number": (
                    passages[0]["source_part_number"] if len(passages) == 1 else None
                ),
                "relative_path": f"reading/{local_id}.json",
                "payload": document,
            }
        )
    return {**metadata, "subject": subject, "question_count": len(seen), "documents": documents}
