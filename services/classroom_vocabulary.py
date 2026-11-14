"""Import classroom meanings and explicit synonym pairs into reading word books."""

from __future__ import annotations

import csv
import io
import re
import threading
import zipfile

from openpyxl import load_workbook

from dictation_answers import canonical_vocabulary_word, parse_vocabulary_word_variants
from models import DictationBook, DictationWord, VocabularySense, db
from services.vocabulary_synonyms import SYNONYM_SENSE_POS, synonym_sense_key

MAX_WORDS = 1200
MAX_BYTES = 2 * 1024 * 1024
BOOK_DESCRIPTION = "课堂生词（单词、词性、中文）"
SYNONYM_BOOK_DESCRIPTION = "课堂词汇（含同义替换）"
_SAVE_LOCK = threading.Lock()
_HEADERS = (
    {"单词", "英文", "词汇", "word", "words", "english"},
    {"词性", "pos", "part of speech", "part_of_speech"},
    {"中文", "释义", "中文释义", "翻译", "meaning", "translation"},
)
_SYNONYM_HEADERS = (
    _HEADERS[0]
    | {"词组", "单词/词组", "单词或词组", "原词", "原词/词组", "原词或词组", "phrase", "original"},
    {"=", "＝", "关系", "relation"},
    {
        "同义词",
        "同义词组",
        "同义替换",
        "同义替换词",
        "同义替换的词",
        "同义词/词组",
        "同义替换词或词组",
        "同义词或词组",
        "synonym",
        "synonyms",
        "paraphrase",
    },
)
_POS_ALIASES = {
    "名词": "n.",
    "noun": "n.",
    "动词": "v.",
    "verb": "v.",
    "及物动词": "vt.",
    "不及物动词": "vi.",
    "形容词": "adj.",
    "adjective": "adj.",
    "a": "adj.",
    "副词": "adv.",
    "adverb": "adv.",
    "介词": "prep.",
    "preposition": "prep.",
    "连词": "conj.",
    "conjunction": "conj.",
    "代词": "pron.",
    "pronoun": "pron.",
    "短语": "phr.",
    "phrase": "phr.",
    "数词": "num.",
    "numeral": "num.",
    "限定词": "det.",
    "determiner": "det.",
    "冠词": "art.",
    "article": "art.",
    "助动词": "aux.",
    "auxiliary": "aux.",
    "感叹词": "int.",
    "interjection": "int.",
    "情态动词": "modal.",
}
_STANDARD_POS = {
    "n",
    "v",
    "vt",
    "vi",
    "adj",
    "adv",
    "prep",
    "conj",
    "pron",
    "phr",
    "num",
    "det",
    "art",
    "aux",
    "int",
    "interj",
    "modal",
}


class ClassroomVocabularyError(ValueError):
    def __init__(self, message, *, errors=None, status=400):
        super().__init__(message)
        self.message = message
        self.errors = errors or []
        self.status = status


def _cell(value):
    return "" if value is None else str(value).strip().lstrip("\ufeff")


def _part_of_speech(value):
    if not value:
        return ""
    parts = re.split(r"\s*[/／,，;；、&]\s*", value.lower())
    normalized = []
    for part in parts:
        key = part.strip().rstrip(".")
        result = _POS_ALIASES.get(key)
        if result is None and key in _STANDARD_POS:
            result = key + "."
        if result is None:
            raise ValueError("词性请用 n.、v.、adj.、adv. 等常见缩写，短语可填 phr. 或留空")
        normalized.append(result)
    return "/".join(normalized)


def _single_english_expression(value):
    # The catalog parser can strip annotations. An imported pair must retain
    # the complete expression, so reject annotations/lists before using it.
    return bool(
        re.fullmatch(r"[A-Za-z'’‘ \-‐‑–—]+", value)
        and len(parse_vocabulary_word_variants(value)) == 1
    )


def _validate_synonym(row, errors, warnings):
    line = row["line"]
    if row["part_of_speech"] == "＝":
        warnings.append({"line": line, "message": "同义替换符号已统一为 ="})
    row["part_of_speech"] = "="
    for key, label in (("word", "原词或词组"), ("meaning", "同义替换词或词组")):
        normalized = row[key].translate(str.maketrans("’‘‐‑–—", "''----"))
        if normalized != row[key]:
            warnings.append({"line": line, "message": f"{label}的引号或连字符已统一为英文符号"})
            row[key] = normalized
        if not _single_english_expression(row[key]):
            errors.append(
                {
                    "line": line,
                    "message": f"{label}请填写一个完整英文单词或词组；多个替换请分行录入",
                }
            )
    if (
        _single_english_expression(row["word"])
        and _single_english_expression(row["meaning"])
        and canonical_vocabulary_word(row["word"]) == canonical_vocabulary_word(row["meaning"])
    ):
        errors.append({"line": line, "message": "等号两侧不能是同一个单词或词组"})


def validate_rows(raw_rows):
    """Return every nonempty row and actionable errors; never drop bad rows."""
    if not isinstance(raw_rows, list):
        raise ClassroomVocabularyError("词表必须为行列表")
    if len(raw_rows) > MAX_WORDS:
        raise ClassroomVocabularyError(f"每份词表最多 {MAX_WORDS} 个词，请分批录入")
    rows, errors, warnings, seen = [], [], [], {}
    for index, raw in enumerate(raw_rows, 1):
        line = raw.get("line", index) if isinstance(raw, dict) else index
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            line = index
        if not isinstance(raw, dict):
            errors.append(
                {"line": line, "message": "每行必须包含单词、词性或等号、中文或同义替换三列"}
            )
            continue
        row = {"line": line}
        for key in ("word", "part_of_speech", "meaning"):
            value = raw.get(key, "")
            if not isinstance(value, str):
                errors.append({"line": line, "message": "三列内容必须为文本"})
                value = ""
            row[key] = value.strip()
        if not any(row[key] for key in ("word", "part_of_speech", "meaning")):
            continue
        rows.append(row)
        synonym = row["part_of_speech"] in {"=", "＝"}
        for key, limit, label in (
            ("word", 100, "单词"),
            ("part_of_speech", 32, "词性"),
            ("meaning", 100 if synonym else 2000, "同义替换" if synonym else "中文"),
        ):
            value = row[key]
            if len(value) > limit:
                errors.append({"line": line, "message": f"{label}不能超过 {limit} 个字符"})
            if re.search(r"[\x00-\x1f\x7f]", value):
                errors.append({"line": line, "message": f"{label}不能包含换行或控制字符"})
        if synonym:
            _validate_synonym(row, errors, warnings)
        elif (
            not row["word"]
            or len(parse_vocabulary_word_variants(row["word"])) != 1
            or re.search(r"[\u3400-\u9fff]", row["word"])
        ):
            errors.append({"line": line, "message": "请填写一个英文单词或短语，多个单词请分行录入"})
        if not row["meaning"] and not synonym:
            errors.append({"line": line, "message": "中文释义不能为空"})
        if not synonym:
            if re.search(r"[A-Za-z]", row["meaning"]) and not re.search(
                r"[\u3400-\u9fff]", row["meaning"]
            ):
                warnings.append(
                    {"line": line, "message": "此行释义为英文；若是同义替换，请将第二列改为 ="}
                )
            try:
                canonical_pos = _part_of_speech(row["part_of_speech"])
                if canonical_pos != row["part_of_speech"]:
                    warnings.append({"line": line, "message": f"词性已统一为 {canonical_pos}"})
                row["part_of_speech"] = canonical_pos
                if len(canonical_pos) > 32:
                    errors.append({"line": line, "message": "词性统一格式后不能超过 32 个字符"})
            except ValueError as exc:
                errors.append({"line": line, "message": str(exc)})
        identity = (
            canonical_vocabulary_word(row["word"]),
            row["part_of_speech"],
            canonical_vocabulary_word(row["meaning"]) if synonym else row["meaning"],
        )
        if identity in seen:
            errors.append(
                {"line": line, "message": f"与第 {seen[identity]} 行重复，请删除重复行后重试"}
            )
        else:
            seen[identity] = line
    if not rows:
        errors.append({"line": 0, "message": "请至少录入一个单词"})
    return {
        "rows": rows,
        "errors": errors,
        "warnings": warnings,
        "valid": not errors,
        "word_count": len(rows),
    }


def _table_rows(table):
    rows, errors = [], []
    first = True
    for line, cells in table:
        values = [_cell(value) for value in cells]
        while len(values) > 3 and not values[-1]:
            values.pop()
        if not any(values):
            continue
        if (
            first
            and len(values) == 3
            and any(
                all(
                    value.lower() in aliases for value, aliases in zip(values, headers, strict=True)
                )
                for headers in (_HEADERS, _SYNONYM_HEADERS)
            )
        ):
            first = False
            continue
        first = False
        if len(rows) >= MAX_WORDS:
            raise ClassroomVocabularyError(f"每份词表最多 {MAX_WORDS} 个词，请分批录入")
        if len(values) != 3:
            errors.append(
                {
                    "line": line,
                    "message": "需要单词、词性或等号、中文或同义替换三列；请从 Excel/WPS 复制三列，或用制表符分隔",
                }
            )
        padded = values + [""] * 3
        rows.append(
            dict(zip(("word", "part_of_speech", "meaning"), padded[:3], strict=True), line=line)
        )
    result = validate_rows(rows)
    result["errors"] = errors + result["errors"]
    result["valid"] = not result["errors"]
    return result


def preview_text(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise ClassroomVocabularyError("词表文本过大，请分批录入")
    delimiter = "\t" if "\t" in text else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter, strict=True)
    try:
        return _table_rows((reader.line_num or 1, row) for row in reader)
    except csv.Error as exc:
        raise ClassroomVocabularyError("无法解析词表，请检查引号和三列分隔") from exc


def preview_workbook(file):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise ClassroomVocabularyError("请上传 .xlsx 文件；旧版 .xls 可另存为 .xlsx 或直接复制三列")
    content = file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ClassroomVocabularyError("Excel 文件不能超过 2 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(entry.file_size for entry in archive.infolist()) > 20 * MAX_BYTES:
                raise ClassroomVocabularyError("Excel 解压后过大，请仅保留需要的词表")
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
        try:
            sheet = workbook.worksheets[0]
            if sheet.max_row and sheet.max_row > 10000:
                raise ClassroomVocabularyError("Excel 行数过多，请仅保留需要的词表")
            if sheet.max_column and sheet.max_column > 32:
                raise ClassroomVocabularyError("Excel 列数过多，请仅保留需要的三列词表")

            def values():
                for line, cells in enumerate(sheet.iter_rows(), 1):
                    if any(cell.data_type == "f" for cell in cells):
                        raise ClassroomVocabularyError(
                            f"第 {line} 行含公式，请复制并粘贴为值后导入"
                        )
                    yield line, [cell.value for cell in cells]

            result = _table_rows(values())
            if len(workbook.sheetnames) > 1:
                result["warnings"].insert(
                    0,
                    {
                        "line": 0,
                        "message": f"仅导入第一个工作表「{sheet.title}」，其他工作表未导入",
                    },
                )
            return result
        finally:
            workbook.close()
    except ClassroomVocabularyError:
        raise
    except Exception as exc:
        raise ClassroomVocabularyError("无法读取 Excel，请检查文件是否损坏或加密") from exc


def _translation(row):
    return " ".join(value for value in (row["part_of_speech"], row["meaning"]) if value)


def _matches_synonym_sense(sense, row):
    return bool(
        sense
        and sense.part_of_speech == SYNONYM_SENSE_POS
        and sense.canonical_key == synonym_sense_key(row["word"], row["meaning"])
        and canonical_vocabulary_word(sense.lemma) == canonical_vocabulary_word(row["word"])
        and canonical_vocabulary_word(sense.definition_en)
        == canonical_vocabulary_word(row["meaning"])
        and not sense.meaning_zh
    )


def _synonym_sense(row):
    key = synonym_sense_key(row["word"], row["meaning"])
    sense = VocabularySense.query.filter_by(canonical_key=key).first()
    if sense:
        if not _matches_synonym_sense(sense, row):
            raise ClassroomVocabularyError("这组同义替换的资料不一致，请联系管理员核对")
        return sense
    sense = VocabularySense(
        canonical_key=key,
        lemma=row["word"],
        part_of_speech=SYNONYM_SENSE_POS,
        definition_en=row["meaning"],
    )
    db.session.add(sense)
    db.session.flush()
    return sense


def _same_words(book, rows):
    words = (
        DictationWord.query.filter_by(book_id=book.id)
        .order_by(DictationWord.sequence, DictationWord.id)
        .all()
    )
    if len(words) != len(rows):
        return False
    for word, row in zip(words, rows, strict=True):
        if word.word != row["word"] or word.translation != _translation(row):
            return False
        if row["part_of_speech"] == "=":
            if not _matches_synonym_sense(word.sense, row):
                return False
        elif word.sense and word.sense.part_of_speech == SYNONYM_SENSE_POS:
            return False
    return True


def save_book(payload, user_id):
    if not isinstance(payload, dict):
        raise ClassroomVocabularyError("请求内容必须为对象")
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
        raise ClassroomVocabularyError("请填写 1–200 字的词表名称")
    title = title.strip()
    if re.search(r"[\x00-\x1f\x7f]", title):
        raise ClassroomVocabularyError("词表名称不能包含换行或控制字符")
    result = validate_rows(payload.get("rows"))
    if not result["valid"]:
        raise ClassroomVocabularyError("词表仍有错误，请修正后保存", errors=result["errors"])
    description = (
        SYNONYM_BOOK_DESCRIPTION
        if any(row["part_of_speech"] == "=" for row in result["rows"])
        else BOOK_DESCRIPTION
    )
    # Production deliberately runs one gthread worker. Serialize the whole
    # dedupe/write sequence across its threads; content lookup also survives a
    # restart or a lost response, without introducing a new migration/table.
    with _SAVE_LOCK:
        books = DictationBook.query.filter_by(
            created_by=user_id,
            title=title,
            description=description,
            is_deleted=False,
            is_active=True,
        ).all()
        for book in books:
            if _same_words(book, result["rows"]):
                return book, True
        book = DictationBook(
            title=title,
            description=description,
            word_count=len(result["rows"]),
            created_by=user_id,
            book_type="dictation",
            default_vocabulary_goal="reading",
            course_system="general",
        )
        db.session.add(book)
        db.session.flush()
        for sequence, row in enumerate(result["rows"], 1):
            sense = _synonym_sense(row) if row["part_of_speech"] == "=" else None
            db.session.add(
                DictationWord(
                    book_id=book.id,
                    sequence=sequence,
                    word=row["word"],
                    translation=_translation(row),
                    sense_id=sense.id if sense else None,
                )
            )
        db.session.commit()
        return book, False
