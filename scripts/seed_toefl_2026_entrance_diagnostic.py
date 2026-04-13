#!/usr/bin/env python3
"""Seed a TOEFL iBT entrance diagnostic aligned to the 2026 TOEFL update.

This script does three things:
1. Verifies the local ETS source materials exist under the desktop TOEFL folder.
2. Builds/copies the listening + speaking media into uploads/entrance/audio.
3. Inserts one TOEFL entrance paper into the existing entrance_test_* tables.

The paper uses Practice Test 5 materials because that set aligns with TOEFL iBT
tests taken on or after 2026-01-21 and includes a complete answer key.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import app  # noqa: E402
from models import (  # noqa: E402
    EntranceTestPaper,
    EntranceTestQuestion,
    EntranceTestSection,
    User,
    db,
)


PAPER_TITLE = "新版 TOEFL iBT 入学诊断（2026 对应版）"
PAPER_EXAM_TYPE = "toefl"
PAPER_LEVEL = "toefl_2026_diagnostic"
DEFAULT_MATERIALS_DIR = "/Users/zhouxin/Desktop/新托福资料"


def _opts(pairs):
    return json.dumps([{"key": k, "text": t} for k, t in pairs], ensure_ascii=False)


def _sentence_answers(sentence: str) -> str:
    """Accept light punctuation variations for sentence-building items."""
    base = sentence.strip()
    variants = {base, base.rstrip("?."), base.replace("'", ""), base.rstrip("?.").replace("'", "")}
    if not base.endswith("?"):
        variants.add(base + "?")
    return "|".join(sorted(v for v in variants if v))


def _get_default_creator_id():
    user = User.query.filter(User.role.in_(("admin", "teacher"))).order_by(User.id.asc()).first()
    if not user:
        user = User.query.order_by(User.id.asc()).first()
    return user.id if user else None


def _media_root() -> Path:
    root = PROJECT_ROOT / "uploads" / "entrance" / "audio"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _concat_audio_to_mp3(output_name: str, inputs: list[Path]) -> str:
    output_path = _media_root() / output_name
    if output_path.exists():
        return f"/uploads/entrance/audio/{output_name}"

    missing = [str(p) for p in inputs if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing source audio files: {missing}")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for path in inputs:
            safe_path = str(path).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")
        list_path = Path(f.name)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-vn",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "4",
                str(output_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        err = exc.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"ffmpeg failed while building {output_name}: {err}") from exc
    finally:
        list_path.unlink(missing_ok=True)

    return f"/uploads/entrance/audio/{output_name}"


def _copy_media(output_name: str, source: Path) -> str:
    output_path = _media_root() / output_name
    if output_path.exists():
        return f"/uploads/entrance/audio/{output_name}"
    if not source.exists():
        raise FileNotFoundError(f"Missing source media file: {source}")
    shutil.copy2(source, output_path)
    return f"/uploads/entrance/audio/{output_name}"


def build_media_urls(materials_root: Path) -> dict[str, str]:
    test5_root = materials_root / "test 7" / "Teacher Practice Test 5 Audio Files"
    listening_root = test5_root / "Listening"
    speaking_root = test5_root / "Speaking"

    urls = {
        "listening_choose_response": _concat_audio_to_mp3(
            "toefl_2026_pt5_listening_choose_response_m1.mp3",
            [
                listening_root / "Listen and Response" / f"Listening1_Listen_Response_Question{i}.ogg"
                for i in range(1, 9)
            ],
        ),
        "listening_conversation_9_10": _concat_audio_to_mp3(
            "toefl_2026_pt5_listening_conversation_9_10.mp3",
            [
                listening_root / "Short Conversation" / "Listening1_Conversation_Directions_9-10.ogg",
                listening_root / "Short Conversation" / "Listening1_Conversation_Questions_9-10.ogg",
            ],
        ),
        "listening_conversation_11_12": _concat_audio_to_mp3(
            "toefl_2026_pt5_listening_conversation_11_12.mp3",
            [
                listening_root / "Short Conversation" / "Listening1_Conversation_Directions_11-12.ogg",
                listening_root / "Short Conversation" / "Listening1_Conversation_Questions_11-12.ogg",
            ],
        ),
        "listening_announcement_13_14": _concat_audio_to_mp3(
            "toefl_2026_pt5_listening_announcement_13_14.mp3",
            [
                listening_root / "Announcements" / "Listening1_Announcement_Directions_13-14.ogg",
                listening_root / "Announcements" / "Listening1_Announcement_Questions_13-14.ogg",
            ],
        ),
        "listening_academic_talk_15_18": _concat_audio_to_mp3(
            "toefl_2026_pt5_listening_academic_talk_15_18.mp3",
            [
                listening_root / "Academic Talk" / "Listening1_Academic_Talk_Directions_15-18.ogg",
                listening_root / "Academic Talk" / "Listening1_Academic_Talk_Questions_15-18.ogg",
            ],
        ),
        "speaking_repeat_directions": _copy_media(
            "toefl_2026_pt5_speaking_repeat_directions.ogg",
            speaking_root / "Listen and Repeat" / "Speaking_Listen_Repeat_Directions.ogg",
        ),
        "speaking_interview_directions": _copy_media(
            "toefl_2026_pt5_speaking_interview_directions.ogg",
            speaking_root / "Interview" / "Speaking_Interview_Directions.ogg",
        ),
    }

    for i in range(1, 8):
        urls[f"speaking_repeat_{i}"] = _copy_media(
            f"toefl_2026_pt5_speaking_repeat_{i}.ogg",
            speaking_root / "Listen and Repeat" / f"Speaking_Listen_Repeat_{i}.ogg",
        )

    for i in range(1, 5):
        urls[f"speaking_interview_{i}"] = _copy_media(
            f"toefl_2026_pt5_speaking_interview_{i}.mp4",
            speaking_root / "Interview" / f"Speaking_Interview_{i}.mp4",
        )

    return urls


def build_paper_data(media_urls: dict[str, str]) -> dict:
    return {
        "title": PAPER_TITLE,
        "exam_type": PAPER_EXAM_TYPE,
        "level": PAPER_LEVEL,
        "description": (
            "对齐 2026-01-21 起生效的新版 TOEFL iBT 题型。系统内包含 Reading / Listening / Writing "
            "三大部分，其中口语材料已同步到项目 uploads 目录，建议由老师线下或面谈执行后在后台录入 "
            "speaking_score 和 speaking_comment。"
        ),
        "sections": [
            {
                "section_type": "reading",
                "sequence": 1,
                "title": "Reading Task 1: Complete the Words",
                "instructions": (
                    "阅读短文，并按顺序补全 10 个缺失的字母片段。答案只填写缺失部分，不要抄写完整单词。"
                ),
                "passage": (
                    "Film and television play a powerful role in shaping cultural norms and public "
                    "opinion. T_ _ industry encom_ _ _ _ _ _ a wide ra_ _ _ of arti_ _ _ _ and "
                    "tech_ _ _ _ _ processes, fr_ _ scriptwriting a_ _ directing t_ post-production. "
                    "Techno_ _ _ _ _ _ _ innovations, su_ _ as digital effects and streaming platforms, "
                    "have significantly altered both how content is produced and how audiences engage "
                    "with it. Studying film offers insights into narrative structure, visual "
                    "storytelling, and the broader social impact of media. It also involves examining "
                    "genres, audience responses, and the economic forces behind production."
                ),
                "duration_minutes": 8,
                "questions": [
                    {"sequence": 1, "question_type": "short_answer", "stem": "Blank 1: T_ _", "correct_answer": "he", "points": 1},
                    {"sequence": 2, "question_type": "short_answer", "stem": "Blank 2: encom_ _ _ _ _ _", "correct_answer": "passes", "points": 1},
                    {"sequence": 3, "question_type": "short_answer", "stem": "Blank 3: ra_ _ _", "correct_answer": "nge", "points": 1},
                    {"sequence": 4, "question_type": "short_answer", "stem": "Blank 4: arti_ _ _ _", "correct_answer": "stic", "points": 1},
                    {"sequence": 5, "question_type": "short_answer", "stem": "Blank 5: tech_ _ _ _ _", "correct_answer": "nical", "points": 1},
                    {"sequence": 6, "question_type": "short_answer", "stem": "Blank 6: fr_ _", "correct_answer": "om", "points": 1},
                    {"sequence": 7, "question_type": "short_answer", "stem": "Blank 7: a_ _", "correct_answer": "nd", "points": 1},
                    {"sequence": 8, "question_type": "short_answer", "stem": "Blank 8: t_", "correct_answer": "o", "points": 1},
                    {"sequence": 9, "question_type": "short_answer", "stem": "Blank 9: Techno_ _ _ _ _ _ _", "correct_answer": "logical", "points": 1},
                    {"sequence": 10, "question_type": "short_answer", "stem": "Blank 10: su_ _", "correct_answer": "ch", "points": 1},
                ],
            },
            {
                "section_type": "reading",
                "sequence": 2,
                "title": "Reading Task 2: Read in Daily Life (Email)",
                "instructions": "阅读邮件并回答问题。",
                "passage": (
                    "Subject: TechHub shipment\n\n"
                    "Dear Ms. Turner,\n\n"
                    "TechHub has shipped the order you placed on Thursday. It should arrive by "
                    "Monday. Please make sure the package contains what you ordered. Returns will "
                    "only be accepted within 3 business days of your package's arrival. Thank you "
                    "for your purchase.\n\nRegards,\nJames Lee"
                ),
                "duration_minutes": 4,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "single_choice",
                        "stem": "When is the latest Ms. Turner will receive her order?",
                        "options_json": _opts([("A", "By Monday"), ("B", "By Tuesday"), ("C", "By Wednesday"), ("D", "By Thursday")]),
                        "correct_answer": "A",
                        "points": 1,
                    },
                    {
                        "sequence": 2,
                        "question_type": "single_choice",
                        "stem": "What is Ms. Turner advised to do?",
                        "options_json": _opts([("A", "Review the return policy"), ("B", "Return the completed warranty form"), ("C", "Send in the final payment"), ("D", "Check the contents of the package")]),
                        "correct_answer": "D",
                        "points": 1,
                    },
                ],
            },
            {
                "section_type": "reading",
                "sequence": 3,
                "title": "Reading Task 3: Read in Daily Life (Notice)",
                "instructions": "阅读活动通知并回答问题。",
                "passage": (
                    "Come join us at the Summer Book Festival!\n\n"
                    "Date: July 18\nTime: 10:00 A.M. - 4:00 P.M.\nLocation: Town Square\n\n"
                    "Enjoy author signings, book readings, and literary workshops. This event is "
                    "perfect for book lovers of all ages, with a special area dedicated to young "
                    "readers.\n\nAdmission is free.\n\nA variety of food and beverages will be "
                    "available for purchase from local food trucks and vendors.\n\nFree parking is "
                    "available at the Town Square parking lot and nearby streets."
                ),
                "duration_minutes": 5,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "single_choice",
                        "stem": "What is the main purpose of the notice?",
                        "options_json": _opts([("A", "To advertise a used-book sales event"), ("B", "To announce an event for people who like reading"), ("C", "To promote an event celebrating the publication of a new book"), ("D", "To advertise prices for a series of writing workshops")]),
                        "correct_answer": "B",
                        "points": 1,
                    },
                    {
                        "sequence": 2,
                        "question_type": "single_choice",
                        "stem": "Where will the event take place?",
                        "options_json": _opts([("A", "At a local bookstore"), ("B", "At the library"), ("C", "At the town square"), ("D", "At the community center")]),
                        "correct_answer": "C",
                        "points": 1,
                    },
                    {
                        "sequence": 3,
                        "question_type": "single_choice",
                        "stem": "What can be concluded about the Summer Book Festival?",
                        "options_json": _opts([("A", "It is suitable for children."), ("B", "It has a registration fee."), ("C", "It will last all day."), ("D", "It requires tickets.")]),
                        "correct_answer": "A",
                        "points": 1,
                    },
                ],
            },
            {
                "section_type": "reading",
                "sequence": 4,
                "title": "Reading Task 4: Read an Academic Passage",
                "instructions": "阅读学术短文并回答问题。",
                "passage": (
                    "Mysterious Viking Sunstones\n\n"
                    "The Vikings, seafaring warriors from Scandinavia, are believed to have navigated "
                    "their ships with remarkable precision across the North Atlantic during the medieval "
                    "period (about 500-1500 C.E.). [A] One key to their navigational success may have "
                    "been the use of so-called \"sunstones,\" as described in Icelandic sagas (medieval "
                    "Icelandic texts). Some argue the sagas' content is mythical, while others suggest "
                    "these stones were real tools used by the Vikings, probably crystals, such as Iceland "
                    "spar. Iceland spar is a transparent variety of calcite that possesses unique optical "
                    "properties. [B] It polarizes light by splitting light into two beams, creating a "
                    "double image when the stone is held up to the sky. By rotating the crystal, the "
                    "Vikings could determine the location of the sun in the sky on cloudy days, which "
                    "would help them maintain their course. [C] However, evidence of actual sunstone use "
                    "remains scarce. Archaeologists have yet to uncover these stones in the remains of "
                    "Viking settlements or ships. But an Iceland spar sunstone was recovered from a ship "
                    "that sank in 1592, suggesting that this navigational tool was indeed used for quite "
                    "some time. [D] The theoretical use of sunstones remains a fascinating example of "
                    "Viking ingenuity."
                ),
                "duration_minutes": 10,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "single_choice",
                        "stem": "Why does debate continue about the sunstones mentioned in Icelandic sagas?",
                        "options_json": _opts([("A", "The sagas describe other uses for sunstones."), ("B", "Archaeologists have not found any such stones when examining Viking sites."), ("C", "Research indicates that sunstones are not actually an effective navigation tool."), ("D", "Researchers suspect that sunstones were not easy to obtain in the medieval period.")]),
                        "correct_answer": "B",
                        "points": 1,
                    },
                    {
                        "sequence": 2,
                        "question_type": "single_choice",
                        "stem": "In what way was Iceland spar useful to Vikings?",
                        "options_json": _opts([("A", "It helped them predict when clouds would disappear."), ("B", "It was used as a tool to help maintain ships."), ("C", "It helped them figure out where the sun was when it could not be seen."), ("D", "It was used to improve seafarers' vision.")]),
                        "correct_answer": "C",
                        "points": 1,
                    },
                    {
                        "sequence": 3,
                        "question_type": "single_choice",
                        "stem": "Why does the author mention a ship that sank in 1592?",
                        "options_json": _opts([("A", "To explain how Elizabethans refined a technology invented by Vikings"), ("B", "To support the theory that Vikings used Iceland spar for navigation"), ("C", "To give an example of a more modern navigational tool"), ("D", "To provide information about archaeological methods")]),
                        "correct_answer": "B",
                        "points": 1,
                    },
                    {
                        "sequence": 4,
                        "question_type": "single_choice",
                        "stem": "The word \"ingenuity\" in the passage is closest in meaning to",
                        "options_json": _opts([("A", "education"), ("B", "cleverness"), ("C", "luck"), ("D", "fame")]),
                        "correct_answer": "B",
                        "points": 1,
                    },
                    {
                        "sequence": 5,
                        "question_type": "single_choice",
                        "stem": "Where would the sentence \"This is all the more remarkable considering the lack of technology at the time.\" best fit?",
                        "options_json": _opts([("A", "Option A"), ("B", "Option B"), ("C", "Option C"), ("D", "Option D")]),
                        "correct_answer": "A",
                        "points": 1,
                    },
                ],
            },
            {
                "section_type": "listening",
                "sequence": 5,
                "title": "Listening Task 1: Listen and Choose a Response",
                "instructions": "播放音频后选择最合适的回应。建议每题只听一遍，但系统音频可重复播放。",
                "audio_url": media_urls["listening_choose_response"],
                "duration_minutes": 8,
                "questions": [
                    {"sequence": 1, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "I think so."), ("B", "He is tired."), ("C", "Yesterday evening."), ("D", "Last time.")]), "correct_answer": "A", "points": 1},
                    {"sequence": 2, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "It's on the table."), ("B", "Not right now."), ("C", "Yes, last Monday."), ("D", "Sure, let's have some.")]), "correct_answer": "B", "points": 1},
                    {"sequence": 3, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "Yes, in the computer."), ("B", "I had the same complaint."), ("C", "It's facing forward."), ("D", "I'll send it immediately.")]), "correct_answer": "D", "points": 1},
                    {"sequence": 4, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "Last night, I think."), ("B", "Perhaps soon."), ("C", "The soup is great."), ("D", "Not really.")]), "correct_answer": "D", "points": 1},
                    {"sequence": 5, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "Sure, I'm free."), ("B", "That's a good choice."), ("C", "Sorry-I forgot."), ("D", "We saved you a seat.")]), "correct_answer": "C", "points": 1},
                    {"sequence": 6, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "This evening is fine."), ("B", "Sure, let's talk soon."), ("C", "No, in the conference room."), ("D", "I believe it was cancelled.")]), "correct_answer": "D", "points": 1},
                    {"sequence": 7, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "They are open late."), ("B", "The shipment arrived this morning."), ("C", "There's one inside the supermarket."), ("D", "I had a good experience there.")]), "correct_answer": "C", "points": 1},
                    {"sequence": 8, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "The same one as last week."), ("B", "A lot of people can't make it."), ("C", "Right after lunch."), ("D", "There wasn't enough room for everyone last time.")]), "correct_answer": "A", "points": 1},
                ],
            },
            {
                "section_type": "listening",
                "sequence": 6,
                "title": "Listening Task 2: Short Conversation",
                "instructions": "听一段对话并回答 2 个问题。",
                "audio_url": media_urls["listening_conversation_9_10"],
                "duration_minutes": 4,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "single_choice",
                        "stem": "What is the woman trying to do?",
                        "options_json": _opts([("A", "Find a new job"), ("B", "Rent a new apartment"), ("C", "Renew a lease"), ("D", "Book a hotel room")]),
                        "correct_answer": "B",
                        "points": 1,
                    },
                    {
                        "sequence": 2,
                        "question_type": "single_choice",
                        "stem": "What does the man imply when he mentions a new hotel?",
                        "options_json": _opts([("A", "The woman should book a room in the new hotel."), ("B", "The woman should check information about the new hotel online."), ("C", "Downtown apartments are very expensive."), ("D", "The downtown area was not a nice place to live until recently.")]),
                        "correct_answer": "D",
                        "points": 1,
                    },
                ],
            },
            {
                "section_type": "listening",
                "sequence": 7,
                "title": "Listening Task 3: Conversation",
                "instructions": "听一段对话并回答 2 个问题。",
                "audio_url": media_urls["listening_conversation_11_12"],
                "duration_minutes": 4,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "single_choice",
                        "stem": "What problem did the woman have with her computer?",
                        "options_json": _opts([("A", "A hardware issue"), ("B", "A software issue"), ("C", "A network issue"), ("D", "A power issue")]),
                        "correct_answer": "B",
                        "points": 1,
                    },
                    {
                        "sequence": 2,
                        "question_type": "single_choice",
                        "stem": "Why does the woman mention her manager?",
                        "options_json": _opts([("A", "To explain why she needed her computer urgently"), ("B", "To indicate that hardware issues can be particularly problematic"), ("C", "To provide details about how she solved a problem"), ("D", "To describe the benefits of a new operating system")]),
                        "correct_answer": "B",
                        "points": 1,
                    },
                ],
            },
            {
                "section_type": "listening",
                "sequence": 8,
                "title": "Listening Task 4: Announcement",
                "instructions": "听一段课堂通知并回答 2 个问题。",
                "audio_url": media_urls["listening_announcement_13_14"],
                "duration_minutes": 4,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "single_choice",
                        "stem": "What will the speaker be doing on Friday?",
                        "options_json": _opts([("A", "Traveling to a conference"), ("B", "Listening to student presentations"), ("C", "Grading student projects"), ("D", "Giving a presentation to her colleagues")]),
                        "correct_answer": "A",
                        "points": 1,
                    },
                    {
                        "sequence": 2,
                        "question_type": "single_choice",
                        "stem": "What can be concluded about Julie and Max?",
                        "options_json": _opts([("A", "They asked for extra time to work on a project."), ("B", "They recently attended a conference."), ("C", "They will have to miss class on Monday."), ("D", "They are the first students who will give presentations.")]),
                        "correct_answer": "D",
                        "points": 1,
                    },
                ],
            },
            {
                "section_type": "listening",
                "sequence": 9,
                "title": "Listening Task 5: Academic Talk",
                "instructions": "听一段学术类讲解并回答 4 个问题。",
                "audio_url": media_urls["listening_academic_talk_15_18"],
                "duration_minutes": 8,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "single_choice",
                        "stem": "What does the speaker mainly discuss?",
                        "options_json": _opts([("A", "How scientists first discovered the placebo effect"), ("B", "How the brain drives the placebo effect"), ("C", "What types of medications are used in clinical trials"), ("D", "What role pharmaceutical companies play in placebo research")]),
                        "correct_answer": "B",
                        "points": 1,
                    },
                    {
                        "sequence": 2,
                        "question_type": "single_choice",
                        "stem": "What point does the speaker make about the various types of placebos?",
                        "options_json": _opts([("A", "They should be cheaper than the actual treatment."), ("B", "They should be colorful and eye-catching."), ("C", "They must undergo testing before clinical use."), ("D", "They must resemble real treatments.")]),
                        "correct_answer": "D",
                        "points": 1,
                    },
                    {
                        "sequence": 3,
                        "question_type": "single_choice",
                        "stem": "Why does the speaker discuss \"creating a kind of bridge\"?",
                        "options_json": _opts([("A", "To illustrate how expectation can lead to physical response"), ("B", "To describe how medicine travels through the body"), ("C", "To clarify how emotions can block medical progress"), ("D", "To discuss the chemical composition of placebos")]),
                        "correct_answer": "A",
                        "points": 1,
                    },
                    {
                        "sequence": 4,
                        "question_type": "single_choice",
                        "stem": "What is the speaker's opinion about the use of placebos in health care?",
                        "options_json": _opts([("A", "Placebos are not very relevant to patient care."), ("B", "Placebos can complement traditional therapies."), ("C", "Placebos are only beneficial in psychological experiments."), ("D", "Placebos should be studied more before being used in clinical settings.")]),
                        "correct_answer": "B",
                        "points": 1,
                    },
                ],
            },
            {
                "section_type": "writing",
                "sequence": 10,
                "title": "Writing Task 1: Build a Sentence",
                "instructions": "根据上下文，把打乱顺序的词组整理成完整、自然、语法正确的句子。",
                "duration_minutes": 6,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "short_answer",
                        "stem": "Your presentation yesterday was impressive.\n\nThanks. Rearrange the fragments:\nyou want / of it / me / you / to send / do / a copy",
                        "correct_answer": _sentence_answers("Do you want me to send you a copy?"),
                        "points": 1,
                    },
                    {
                        "sequence": 2,
                        "question_type": "short_answer",
                        "stem": "I wish I hadn't missed the conference last week.\n\nRearrange the fragments:\nthe recordings / where / don't / know / the sessions / of / to get",
                        "correct_answer": _sentence_answers("Don't you know where to get the recordings of the sessions?"),
                        "points": 1,
                    },
                    {
                        "sequence": 3,
                        "question_type": "short_answer",
                        "stem": "The new yoga class was very relaxing.\n\nRearrange the fragments:\nare / a few / classes / wonder / I / held / if / on Saturdays",
                        "correct_answer": _sentence_answers("I wonder if a few classes are held on Saturdays."),
                        "points": 1,
                    },
                    {
                        "sequence": 4,
                        "question_type": "short_answer",
                        "stem": "We had a blast at the national park yesterday.\n\nRearrange the fragments:\ndoes / it / anybody / whether / is open / know / all year long",
                        "correct_answer": _sentence_answers("Does anybody know whether it is open all year long?"),
                        "points": 1,
                    },
                    {
                        "sequence": 5,
                        "question_type": "short_answer",
                        "stem": "The film festival this weekend was amazing.\n\nRearrange the fragments:\nthey / if / are / can / find out / planning / another one / we",
                        "correct_answer": _sentence_answers("Can we find out if they are planning another one?"),
                        "points": 1,
                    },
                    {
                        "sequence": 6,
                        "question_type": "short_answer",
                        "stem": "The workshop on graphic design was very helpful.\n\nRearrange the fragments:\nwhy / each / tell me / how long / was / workshop session / could / you",
                        "correct_answer": _sentence_answers("Could you tell me how long each workshop session was?"),
                        "points": 1,
                    },
                    {
                        "sequence": 7,
                        "question_type": "short_answer",
                        "stem": "The new art exhibit at the museum is stunning.\n\nRearrange the fragments:\nwould / to know / how / I / you / happen / can get / exhibit information",
                        "correct_answer": _sentence_answers("Would you happen to know how I can get exhibit information?"),
                        "points": 1,
                    },
                    {
                        "sequence": 8,
                        "question_type": "short_answer",
                        "stem": "Let's go to that new gym this afternoon.\n\nRearrange the fragments:\nknow / you / do / is / usually crowded / if / it / at this time",
                        "correct_answer": _sentence_answers("Do you know if it is usually crowded at this time?"),
                        "points": 1,
                    },
                    {
                        "sequence": 9,
                        "question_type": "short_answer",
                        "stem": "I really enjoyed the documentary we watched yesterday.\n\nRearrange the fragments:\nyou / how / heard / it / they filmed / any details / have / about",
                        "correct_answer": _sentence_answers("Have you heard any details about how they filmed it?"),
                        "points": 1,
                    },
                    {
                        "sequence": 10,
                        "question_type": "short_answer",
                        "stem": "I'm applying for a position at that new technology hub.\n\nRearrange the fragments:\ndo / they / have / how many / you / open positions / know",
                        "correct_answer": _sentence_answers("Do you know how many open positions they have?"),
                        "points": 1,
                    },
                ],
            },
            {
                "section_type": "writing",
                "sequence": 11,
                "title": "Writing Task 2: Write an Email",
                "instructions": "建议用时 7 分钟。请完整作答，使用自然邮件格式。",
                "duration_minutes": 7,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "essay",
                        "stem": (
                            "You recently attended a workshop on digital marketing and found it to be very "
                            "informative. You want to thank the presenter, Ms. Clark, and ask for additional "
                            "resources to further your understanding of the topic.\n\n"
                            "Write an email to Ms. Clark. In your email, do the following:\n"
                            "1. Thank her for the workshop.\n"
                            "2. Explain in detail why you found the workshop informative.\n"
                            "3. Ask for additional resources or recommendations for further study.\n\n"
                            "Write as much as you can and in complete sentences.\n\n"
                            "To: Ms. Clark\nSubject: Appreciation and request for additional resources"
                        ),
                        "correct_answer": None,
                        "points": 10,
                        "reference_answer": (
                            "评分重点：1) 是否完成致谢、说明收获、索取资源三个交际目的；"
                            "2) 语气是否符合邮件语境；3) 内容是否有细节支撑；4) 句子衔接和段落组织；"
                            "5) 语法、拼写、标点和词汇准确度。"
                        ),
                    }
                ],
            },
            {
                "section_type": "writing",
                "sequence": 12,
                "title": "Writing Task 3: Academic Discussion",
                "instructions": "建议用时 10 分钟。有效回答建议不少于 100 词。",
                "duration_minutes": 10,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "essay",
                        "stem": (
                            "Your professor is teaching a class on environmental science. Write a post "
                            "responding to the professor's question.\n\n"
                            "In your response, you should do the following:\n"
                            "- Express and support your opinion.\n"
                            "- Make a contribution to the discussion in your own words.\n\n"
                            "An effective response will contain at least 100 words.\n\n"
                            "[Dr. Gupta]\n"
                            "Human activities like pollution and deforestation harm the environment. Some "
                            "argue we must reduce or eliminate these actions to mitigate their impact. Others "
                            "support technologies and initiatives that lessen the damage without stopping the "
                            "activities, such as pollution cleanup or forest restoration. What do you think is "
                            "the most effective way to address environmental issues: eliminating harmful "
                            "activities or minimizing their impact? Why?\n\n"
                            "[Student A]\n"
                            "The best way to protect the environment is to stop harmful activities like "
                            "pollution and deforestation. If we don't end them, the damage will continue and "
                            "get worse. Prevention is more effective than trying to fix problems after they "
                            "happen.\n\n"
                            "[Student B]\n"
                            "Human development has increased to the extent that stopping all harmful activities "
                            "in time for it to make a difference would be nearly impossible. Instead, we should "
                            "focus on smarter solutions that reduce harm."
                        ),
                        "correct_answer": None,
                        "points": 10,
                        "reference_answer": (
                            "评分重点：1) 立场是否清晰；2) 是否回应题干与两位同学观点；"
                            "3) 论证是否有展开和例子；4) 是否达到约 100 词并保持连贯；"
                            "5) 语法和词汇准确、自然。"
                        ),
                    }
                ],
            },
        ],
    }


def seed_paper(data: dict, creator_id: int | None):
    existing = EntranceTestPaper.query.filter_by(
        title=data["title"], exam_type=data["exam_type"]
    ).first()
    if existing:
        print(f"[SKIP] '{data['title']}' already exists (id={existing.id})")
        return existing

    paper = EntranceTestPaper(
        title=data["title"],
        exam_type=data["exam_type"],
        level=data["level"],
        description=data["description"],
        is_active=True,
        created_by=creator_id,
    )
    db.session.add(paper)
    db.session.flush()

    for sec_data in data["sections"]:
        section = EntranceTestSection(
            paper_id=paper.id,
            section_type=sec_data["section_type"],
            sequence=sec_data["sequence"],
            title=sec_data["title"],
            instructions=sec_data.get("instructions"),
            audio_url=sec_data.get("audio_url"),
            passage=sec_data.get("passage"),
            duration_minutes=sec_data.get("duration_minutes"),
        )
        db.session.add(section)
        db.session.flush()

        for q_data in sec_data["questions"]:
            question = EntranceTestQuestion(
                section_id=section.id,
                sequence=q_data["sequence"],
                question_type=q_data["question_type"],
                stem=q_data["stem"],
                options_json=q_data.get("options_json"),
                correct_answer=q_data.get("correct_answer"),
                points=q_data["points"],
                reference_answer=q_data.get("reference_answer"),
            )
            db.session.add(question)

    db.session.commit()
    print(f"[CREATED] '{data['title']}' (id={paper.id})")
    return paper


def main():
    materials_root = Path(os.environ.get("TOEFL_MATERIALS_DIR", DEFAULT_MATERIALS_DIR))
    if not materials_root.exists():
        print(f"Error: TOEFL materials directory not found: {materials_root}")
        sys.exit(1)

    with app.app_context():
        creator_id = _get_default_creator_id()
        if creator_id is None:
            print("Error: no user found in DB. Create an admin/teacher first.")
            sys.exit(1)

        media_urls = build_media_urls(materials_root)
        paper_data = build_paper_data(media_urls)
        paper = seed_paper(paper_data, creator_id)

        section_count = paper.sections.count()
        question_count = sum(section.questions.count() for section in paper.sections)
        print(f"Paper ready: id={paper.id}, sections={section_count}, questions={question_count}")
        print("Speaking media copied to uploads/entrance/audio for manual administration.")


if __name__ == "__main__":
    main()
