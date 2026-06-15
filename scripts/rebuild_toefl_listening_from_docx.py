#!/usr/bin/env python3
"""Rebuild a screenshot-based TOEFL listening JSON from DOCX images.

This is an offline maintenance tool. It extracts the original embedded PNG
files, detects the four radio circles, and OCRs each option independently.
That avoids the cross-option merging caused by whole-page OCR.

Optional local dependencies:
    pip install opencv-python-headless pytesseract
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import tempfile
from pathlib import Path
from zipfile import ZipFile

import cv2
import pytesseract


REPO_ROOT = Path(__file__).resolve().parents[1]
ANSWER_CSV = (
    REPO_ROOT
    / "data"
    / "toefl_answer_keys"
    / "practice_crosswalk"
    / "question_answer_crosswalk.csv"
)

QUESTION_IMAGES_2026_04_15_S1 = {
    "m1": {
        **{number: number for number in range(1, 13)},
        13: 14,
        14: 15,
        15: 17,
        16: 18,
        17: 20,
        18: 21,
        19: 23,
        20: 24,
        21: 26,
        22: 27,
        23: 29,
        24: 30,
        25: 32,
        26: 33,
        27: 34,
        28: 35,
        29: 37,
        30: 38,
        31: 39,
        32: 40,
    },
    "m2": {
        1: 42,
        2: 43,
        3: 44,
        4: 46,
        5: 47,
        6: 49,
        7: 50,
        8: 52,
        9: 53,
        10: 54,
        11: 55,
        12: 57,
        13: 58,
        14: 59,
        15: 60,
    },
}


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _clean_ocr_text(value: str) -> str:
    value = _compact(value)
    value = re.sub(r"^[^A-Za-z0-9]+", "", value)
    replacements = (
        (r"^\|(?=[A-Za-z])", "I "),
        (r"^1(?=[A-Za-z])", "I "),
        (r"^received\b", "I received"),
        (r"^think\b", "I think"),
        (r"^like\b", "I like"),
        (r"^spent\b", "I spent"),
        (r"^visited\b", "I visited"),
        (r"^had\b", "I had"),
        (r"^love\b", "I love"),
        (r"^enjoy\b", "I enjoy"),
        (r"^usually\b", "I usually"),
        (r"^Creating\b", "Creating"),
        (r"^reating\b", "Creating"),
        (r"^ontact\b", "Contact"),
        (r"^alculating\b", "Calculating"),
        (r"^omparing\b", "Comparing"),
        (r"\bItis\b", "It is"),
        (r"\bItwas\b", "It was"),
        (r"\bItwill\b", "It will"),
        (r"\bAtextbook\b", "A textbook"),
        (r"\bAcollection\b", "A collection"),
        (r"\bAfamous\b", "A famous"),
        (r"\bAtool\b", "A tool"),
        (r"\bAsocial\b", "A social"),
        (r"\bAstory\b", "A story"),
        (r"\bAunique\b", "A unique"),
        (r"\bartform\b", "art form"),
        (r"[“\"]anvas\b", "canvas"),
        (r"\bShey\b", "They"),
        (r"^they are\b", "They are"),
        (r"\bfrom the 1700:\s*4\b", "from the 1700s?"),
    )
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value, flags=re.I)
    return value.strip(" |\\")


def _radio_centers(gray) -> list[tuple[float, float, float]]:
    height, width = gray.shape
    circles = cv2.HoughCircles(
        cv2.medianBlur(gray, 5),
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=35,
        param1=100,
        param2=25,
        minRadius=8,
        maxRadius=25,
    )
    if circles is None:
        return []
    candidates = sorted(
        [
            (float(x), float(y), float(radius))
            for x, y, radius in circles[0]
            if 0.48 * width < x < 0.58 * width
            and 0.18 * height < y < 0.85 * height
        ],
        key=lambda item: item[1],
    )
    result = []
    for candidate in candidates:
        if not result or candidate[1] - result[-1][1] > 30:
            result.append(candidate)
    return result[:4]


def _ocr_crop(gray, left: int, top: int, right: int, bottom: int) -> str:
    crop = gray[max(0, top):max(top + 1, bottom), max(0, left):max(left + 1, right)]
    crop = cv2.resize(crop, None, fx=2, fy=2)
    return _clean_ocr_text(
        pytesseract.image_to_string(crop, lang="eng", config="--psm 6")
    )


def extract_question(image_path: Path, listen_and_choose: bool) -> tuple[str, list[str]]:
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Cannot read image: {image_path}")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    circles = _radio_centers(gray)
    if len(circles) != 4:
        raise RuntimeError(
            f"Expected four radio circles in {image_path.name}, found {len(circles)}"
        )

    y_values = [circle[1] for circle in circles]
    options = []
    for index, (x, y, _radius) in enumerate(circles):
        top = int((y_values[index - 1] + y) / 2) if index else int(y - 30)
        bottom = (
            int((y + y_values[index + 1]) / 2)
            if index < 3
            else min(height, int(y + (y - y_values[index - 1]) / 2 + 20))
        )
        options.append(
            _ocr_crop(gray, int(x + 10), top, int(width * 0.99), bottom)
        )

    prompt = ""
    if not listen_and_choose:
        prompt = _ocr_crop(
            gray,
            int(width * 0.43),
            int(height * 0.06),
            int(width * 0.99),
            int(y_values[0] - 35),
        )
    return prompt, options


def _answer_map(practice_id: str) -> dict[tuple[str, int], str]:
    result = {}
    with ANSWER_CSV.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            row_practice_id = row.get("practice_id") or row.get("\ufeffpractice_id")
            if row_practice_id != practice_id or row.get("subject") != "listening":
                continue
            result[(row["module"], int(row["source_question_no"]))] = row[
                "correct_answer"
            ]
    return result


def _task_type(module: str, number: int) -> str:
    if (module == "m1" and number <= 12) or (module == "m2" and number <= 3):
        return "listen_and_choose"
    if (module == "m1" and number <= 24) or (module == "m2" and number <= 7):
        return "conversation"
    return "academic_talk"


def _directive(task_type: str) -> str:
    if task_type == "listen_and_choose":
        return "Choose the best response"
    if task_type == "conversation":
        return "Listen to a conversation."
    return "Listen to an announcement or academic talk."


def rebuild(
    docx_path: Path,
    output_path: Path,
    practice_id: str,
    exam_id: str,
) -> dict:
    answers = _answer_map(practice_id)
    existing = json.loads(output_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="toefl-docx-ocr-") as temporary:
        temp_root = Path(temporary)
        with ZipFile(docx_path) as archive:
            archive.extractall(temp_root)
        media_root = temp_root / "word" / "media"

        questions = []
        order = 0
        for module, mapping in QUESTION_IMAGES_2026_04_15_S1.items():
            for number, image_number in mapping.items():
                order += 1
                task_type = _task_type(module, number)
                prompt, options = extract_question(
                    media_root / f"image{image_number}.png",
                    listen_and_choose=task_type == "listen_and_choose",
                )
                if len(options) != 4 or any(len(option) < 3 for option in options):
                    raise RuntimeError(f"Unusable OCR for {module} question {number}: {options}")
                answer = answers.get((module, number), "")
                questions.append(
                    {
                        "id": f"listening_{exam_id}_{module}_q{number}",
                        "task_type": task_type,
                        "order": order,
                        "number": str(number),
                        "number_end": None,
                        "directive": _directive(task_type),
                        "prompt": prompt,
                        "passage": None,
                        "audio_ref": module,
                        "options": [
                            {"key": chr(65 + index), "text": text}
                            for index, text in enumerate(options)
                        ],
                        "answer": (
                            {"keys": [answer], "explanation": None}
                            if answer in {"A", "B", "C", "D"}
                            else None
                        ),
                        "response_type": "mc",
                        "content_status": "complete",
                        "grading_status": "auto" if answer else "review_only",
                        "source_ref": str(docx_path),
                    }
                )
    existing["questions"] = questions
    output_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return existing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--practice-id", required=True)
    parser.add_argument("--exam-id", required=True)
    args = parser.parse_args()
    payload = rebuild(args.docx, args.output, args.practice_id, args.exam_id)
    print(f"Rebuilt {len(payload['questions'])} listening questions.")


if __name__ == "__main__":
    main()
