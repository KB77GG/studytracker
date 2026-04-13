#!/usr/bin/env python3
"""Seed a 30-minute TOEFL iBT quick entrance diagnostic."""

from __future__ import annotations

import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from seed_toefl_2026_entrance_diagnostic import (  # noqa: E402
    DEFAULT_MATERIALS_DIR,
    _get_default_creator_id,
    _opts,
    app,
    build_media_urls,
    seed_paper,
)


PAPER_TITLE = "新版 TOEFL iBT 快速诊断（30分钟版）"
PAPER_EXAM_TYPE = "toefl"
PAPER_LEVEL = "toefl_2026_quick_30m"


def build_quick_paper(media_urls: dict[str, str]) -> dict:
    return {
        "title": PAPER_TITLE,
        "exam_type": PAPER_EXAM_TYPE,
        "level": PAPER_LEVEL,
        "description": (
            "30 分钟内可完成的新版 TOEFL iBT 快速入学诊断。覆盖新版 Reading / Listening / "
            "Writing 核心题型，适合首轮分班、试听前测或家长现场咨询场景。口语建议另行进行教师面谈。"
        ),
        "sections": [
            {
                "section_type": "reading",
                "sequence": 1,
                "title": "Reading Task 1: Read in Daily Life (Email)",
                "instructions": "阅读邮件并回答问题。",
                "passage": (
                    "Subject: TechHub shipment\n\n"
                    "Dear Ms. Turner,\n\n"
                    "TechHub has shipped the order you placed on Thursday. It should arrive by "
                    "Monday. Please make sure the package contains what you ordered. Returns will "
                    "only be accepted within 3 business days of your package's arrival. Thank you "
                    "for your purchase.\n\nRegards,\nJames Lee"
                ),
                "duration_minutes": 3,
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
                "sequence": 2,
                "title": "Reading Task 2: Read in Daily Life (Notice)",
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
                "duration_minutes": 4,
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
                "sequence": 3,
                "title": "Reading Task 3: Read an Academic Passage",
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
                "duration_minutes": 6,
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
                "sequence": 4,
                "title": "Listening Task 1: Listen and Choose a Response",
                "instructions": "播放音频后选择最合适的回应。本快速版保留前 6 题。",
                "audio_url": media_urls["listening_choose_response"],
                "duration_minutes": 4,
                "questions": [
                    {"sequence": 1, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "I think so."), ("B", "He is tired."), ("C", "Yesterday evening."), ("D", "Last time.")]), "correct_answer": "A", "points": 1},
                    {"sequence": 2, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "It's on the table."), ("B", "Not right now."), ("C", "Yes, last Monday."), ("D", "Sure, let's have some.")]), "correct_answer": "B", "points": 1},
                    {"sequence": 3, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "Yes, in the computer."), ("B", "I had the same complaint."), ("C", "It's facing forward."), ("D", "I'll send it immediately.")]), "correct_answer": "D", "points": 1},
                    {"sequence": 4, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "Last night, I think."), ("B", "Perhaps soon."), ("C", "The soup is great."), ("D", "Not really.")]), "correct_answer": "D", "points": 1},
                    {"sequence": 5, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "Sure, I'm free."), ("B", "That's a good choice."), ("C", "Sorry-I forgot."), ("D", "We saved you a seat.")]), "correct_answer": "C", "points": 1},
                    {"sequence": 6, "question_type": "single_choice", "stem": "Choose the best response.", "options_json": _opts([("A", "This evening is fine."), ("B", "Sure, let's talk soon."), ("C", "No, in the conference room."), ("D", "I believe it was cancelled.")]), "correct_answer": "D", "points": 1},
                ],
            },
            {
                "section_type": "listening",
                "sequence": 5,
                "title": "Listening Task 2: Short Conversation",
                "instructions": "听一段对话并回答 2 个问题。",
                "audio_url": media_urls["listening_conversation_9_10"],
                "duration_minutes": 3,
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
                "sequence": 6,
                "title": "Listening Task 3: Announcement",
                "instructions": "听一段课堂通知并回答 2 个问题。",
                "audio_url": media_urls["listening_announcement_13_14"],
                "duration_minutes": 3,
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
                "section_type": "writing",
                "sequence": 7,
                "title": "Writing Task: Write an Email",
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
        ],
    }


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
        paper = seed_paper(build_quick_paper(media_urls), creator_id)

        total_minutes = sum((section.duration_minutes or 0) for section in paper.sections)
        section_count = paper.sections.count()
        question_count = sum(section.questions.count() for section in paper.sections)
        print(f"Paper ready: id={paper.id}, sections={section_count}, questions={question_count}, minutes={total_minutes}")


if __name__ == "__main__":
    main()
