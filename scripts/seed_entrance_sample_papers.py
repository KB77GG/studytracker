#!/usr/bin/env python3
"""Seed 2 sample entrance test papers for local/prod integration testing.

Idempotent: checks by (title, exam_type) before inserting.

Papers:
  1. 通用英语 A2 诊断 (general / general_a2)
  2. IELTS 6.0-7.5 诊断 (ielts / ielts_60_75)

Each paper contains listening + reading + writing sections with a few
questions. Listening audio_url left blank — upload manually later via
uploads/entrance_audio/.
"""

import json
import os
import sys

# Make project root importable when run from scripts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import (
    db,
    User,
    EntranceTestPaper,
    EntranceTestSection,
    EntranceTestQuestion,
)


def _opts(pairs):
    return json.dumps(
        [{"key": k, "text": t} for k, t in pairs], ensure_ascii=False
    )


# ----------------------------------------------------------------------------
# Paper 1: 通用英语 A2 诊断
# ----------------------------------------------------------------------------
PAPER_GENERAL_A2 = {
    "title": "通用英语 A2 诊断",
    "exam_type": "general",
    "level": "general_a2",
    "description": "适用于未系统学习过雅思/托福、英语基础处于 A1-A2 的学生。",
    "sections": [
        {
            "section_type": "listening",
            "sequence": 1,
            "title": "Section 1: Short Conversations",
            "instructions": "你将听到 3 段简短对话，每段对话后选择正确答案。每段只播放一次。",
            "audio_url": "",
            "passage": None,
            "duration_minutes": 8,
            "questions": [
                {
                    "sequence": 1,
                    "question_type": "single_choice",
                    "stem": "Where is the woman going?",
                    "options_json": _opts([
                        ("A", "To the library"),
                        ("B", "To the supermarket"),
                        ("C", "To the post office"),
                        ("D", "To the hospital"),
                    ]),
                    "correct_answer": "B",
                    "points": 1,
                    "reference_answer": None,
                },
                {
                    "sequence": 2,
                    "question_type": "single_choice",
                    "stem": "What time will they meet?",
                    "options_json": _opts([
                        ("A", "6:30"),
                        ("B", "7:00"),
                        ("C", "7:30"),
                        ("D", "8:00"),
                    ]),
                    "correct_answer": "C",
                    "points": 1,
                    "reference_answer": None,
                },
                {
                    "sequence": 3,
                    "question_type": "short_answer",
                    "stem": "How much does the ticket cost? (answer in numbers, e.g. 15)",
                    "options_json": None,
                    "correct_answer": "15",
                    "points": 1,
                    "reference_answer": None,
                },
            ],
        },
        {
            "section_type": "reading",
            "sequence": 2,
            "title": "Section 2: Short Passage",
            "instructions": "阅读下面短文并回答问题。",
            "audio_url": None,
            "passage": (
                "Tom is a 12-year-old boy from London. Every morning he gets up at 7 o'clock "
                "and has breakfast with his parents. He goes to school by bus. His favorite "
                "subject is science because he likes doing experiments. After school, he "
                "usually plays football with his friends in the park. On weekends, he visits "
                "his grandparents in the countryside."
            ),
            "duration_minutes": 10,
            "questions": [
                {
                    "sequence": 1,
                    "question_type": "single_choice",
                    "stem": "How old is Tom?",
                    "options_json": _opts([
                        ("A", "10"),
                        ("B", "11"),
                        ("C", "12"),
                        ("D", "13"),
                    ]),
                    "correct_answer": "C",
                    "points": 1,
                    "reference_answer": None,
                },
                {
                    "sequence": 2,
                    "question_type": "single_choice",
                    "stem": "How does Tom go to school?",
                    "options_json": _opts([
                        ("A", "By car"),
                        ("B", "By bus"),
                        ("C", "By bike"),
                        ("D", "On foot"),
                    ]),
                    "correct_answer": "B",
                    "points": 1,
                    "reference_answer": None,
                },
                {
                    "sequence": 3,
                    "question_type": "short_answer",
                    "stem": "What is Tom's favorite subject?",
                    "options_json": None,
                    "correct_answer": "science",
                    "points": 1,
                    "reference_answer": None,
                },
                {
                    "sequence": 4,
                    "question_type": "single_choice",
                    "stem": "Where does Tom visit on weekends?",
                    "options_json": _opts([
                        ("A", "The library"),
                        ("B", "The park"),
                        ("C", "His grandparents' home in the countryside"),
                        ("D", "The school"),
                    ]),
                    "correct_answer": "C",
                    "points": 1,
                    "reference_answer": None,
                },
            ],
        },
        {
            "section_type": "writing",
            "sequence": 3,
            "title": "Section 3: Short Writing",
            "instructions": "请用英文写一段约 80-100 词的短文。",
            "audio_url": None,
            "passage": None,
            "duration_minutes": 15,
            "questions": [
                {
                    "sequence": 1,
                    "question_type": "essay",
                    "stem": (
                        "Write about your daily routine. Include when you get up, "
                        "what you do in the morning, at school, and in the evening. "
                        "(80-100 words)"
                    ),
                    "options_json": None,
                    "correct_answer": None,
                    "points": 10,
                    "reference_answer": (
                        "评分要点：时态正确使用（一般现在时）、基本词汇运用"
                        "（get up / have breakfast / go to school 等）、句子结构"
                        "完整、能表达至少 3 个时间段的活动。"
                    ),
                },
            ],
        },
    ],
}


# ----------------------------------------------------------------------------
# Paper 2: IELTS 6.0-7.5 诊断
# ----------------------------------------------------------------------------
PAPER_IELTS_60_75 = {
    "title": "IELTS 6.0-7.5 诊断",
    "exam_type": "ielts",
    "level": "ielts_60_75",
    "description": "适用于已系统学习过雅思、目标分数 6.0-7.5 的学生。",
    "sections": [
        {
            "section_type": "listening",
            "sequence": 1,
            "title": "Section 1: Academic Lecture",
            "instructions": "你将听到一段学术讲座，根据内容回答问题。音频只播放一次。",
            "audio_url": "",
            "passage": None,
            "duration_minutes": 10,
            "questions": [
                {
                    "sequence": 1,
                    "question_type": "single_choice",
                    "stem": "What is the main topic of the lecture?",
                    "options_json": _opts([
                        ("A", "Climate change impacts"),
                        ("B", "Renewable energy technologies"),
                        ("C", "Urban planning strategies"),
                        ("D", "Agricultural innovations"),
                    ]),
                    "correct_answer": "B",
                    "points": 1,
                    "reference_answer": None,
                },
                {
                    "sequence": 2,
                    "question_type": "short_answer",
                    "stem": "Complete the sentence: Solar panels convert sunlight into _______. (one word)",
                    "options_json": None,
                    "correct_answer": "electricity",
                    "points": 1,
                    "reference_answer": None,
                },
                {
                    "sequence": 3,
                    "question_type": "short_answer",
                    "stem": "By what year does the speaker predict wind power will dominate? (a year)",
                    "options_json": None,
                    "correct_answer": "2040|by 2040",
                    "points": 1,
                    "reference_answer": None,
                },
            ],
        },
        {
            "section_type": "reading",
            "sequence": 2,
            "title": "Section 2: Academic Reading Passage",
            "instructions": "Read the passage and answer the questions.",
            "audio_url": None,
            "passage": (
                "The concept of 'deep work', introduced by computer scientist Cal Newport, "
                "refers to professional activities performed in a state of distraction-free "
                "concentration that push cognitive capabilities to their limit. Newport argues "
                "that in an era of constant digital interruption, the ability to focus without "
                "distraction has become both increasingly rare and increasingly valuable. "
                "Research in cognitive psychology supports his claim: when workers are frequently "
                "interrupted, the quality of their output drops significantly, and the time "
                "needed to return to a state of full concentration after an interruption averages "
                "around 23 minutes. Organizations that restructure workflows to protect deep work "
                "periods report measurable gains in both productivity and employee satisfaction."
            ),
            "duration_minutes": 15,
            "questions": [
                {
                    "sequence": 1,
                    "question_type": "single_choice",
                    "stem": "Who introduced the concept of 'deep work'?",
                    "options_json": _opts([
                        ("A", "A cognitive psychologist"),
                        ("B", "Cal Newport, a computer scientist"),
                        ("C", "An organizational consultant"),
                        ("D", "A productivity coach"),
                    ]),
                    "correct_answer": "B",
                    "points": 1,
                    "reference_answer": None,
                },
                {
                    "sequence": 2,
                    "question_type": "short_answer",
                    "stem": "How many minutes on average does it take to return to full concentration after an interruption? (a number)",
                    "options_json": None,
                    "correct_answer": "23",
                    "points": 1,
                    "reference_answer": None,
                },
                {
                    "sequence": 3,
                    "question_type": "single_choice",
                    "stem": "According to the passage, organizations that protect deep work periods experience:",
                    "options_json": _opts([
                        ("A", "Higher costs but better quality"),
                        ("B", "Gains in productivity and employee satisfaction"),
                        ("C", "Reduced employee turnover only"),
                        ("D", "No measurable changes"),
                    ]),
                    "correct_answer": "B",
                    "points": 1,
                    "reference_answer": None,
                },
            ],
        },
        {
            "section_type": "writing",
            "sequence": 3,
            "title": "Section 3: IELTS Writing Task 2",
            "instructions": "Write at least 250 words.",
            "audio_url": None,
            "passage": None,
            "duration_minutes": 40,
            "questions": [
                {
                    "sequence": 1,
                    "question_type": "essay",
                    "stem": (
                        "Some people believe that the internet has brought people closer "
                        "together, while others argue that it has made people more isolated. "
                        "Discuss both views and give your own opinion. (at least 250 words)"
                    ),
                    "options_json": None,
                    "correct_answer": None,
                    "points": 9,
                    "reference_answer": (
                        "评分要点（按 IELTS 四维度）：1) Task Response — 清晰讨论双方观点并给出立场；"
                        "2) Coherence & Cohesion — 段落结构清晰，使用连接词；"
                        "3) Lexical Resource — 话题词汇多样（social interaction, digital communication 等）；"
                        "4) Grammatical Range — 复杂句式、正确时态。目标 6.5+ 需 250+ 词。"
                    ),
                },
            ],
        },
    ],
}


SAMPLE_PAPERS = [PAPER_GENERAL_A2, PAPER_IELTS_60_75]


def _get_default_creator_id():
    """Pick an admin/teacher user id to own the seeded papers."""
    user = User.query.filter(User.role.in_(("admin", "teacher"))).first()
    if not user:
        user = User.query.first()
    return user.id if user else None


def seed_paper(data, creator_id):
    existing = EntranceTestPaper.query.filter_by(
        title=data["title"], exam_type=data["exam_type"]
    ).first()
    if existing:
        print(f"  [SKIP] '{data['title']}' already exists (id={existing.id})")
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
            instructions=sec_data["instructions"],
            audio_url=sec_data.get("audio_url"),
            passage=sec_data.get("passage"),
            duration_minutes=sec_data["duration_minutes"],
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
    print(f"  [CREATED] '{data['title']}' (id={paper.id})")
    return paper


def main():
    with app.app_context():
        creator_id = _get_default_creator_id()
        if not creator_id:
            print("Error: no user in DB to own the papers. Create an admin first.")
            sys.exit(1)

        print(f"Seeding entrance test sample papers (creator user id={creator_id})...")
        for data in SAMPLE_PAPERS:
            seed_paper(data, creator_id)
        print("Done.")


if __name__ == "__main__":
    main()
