#!/usr/bin/env python3
"""Seed 7 tiered IELTS entrance test papers by recombining existing
Cambridge listening JSON + reading jijing JSON banks under static/.

Idempotent: skipped if (title, exam_type) already exists.

Tiers (IELTS band ranges):
  - ielts_45_55   入门 4.5-5.5      (2 papers, A/B)
  - ielts_55_65   进阶 5.5-6.5      (2 papers, A/B)
  - ielts_65_75   标准 6.5-7.5      (1 new paper "B"; "A" already seeded as id=2)
  - ielts_75_plus 冲刺 7.5+         (2 papers, A/B)

Each paper = 1 listening section (~6-10 Q, audio reused) +
             1 reading passage (~5-13 Q) +
             1 writing Task 2 prompt (AI-authored). ~30 min total.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import (
    db,
    User,
    EntranceTestPaper,
    EntranceTestSection,
    EntranceTestQuestion,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTENING_DIR = os.path.join(PROJECT_ROOT, "static", "listening_tests")
READING_DIR = os.path.join(PROJECT_ROOT, "static", "reading_jijing")
AUDIO_URL_PREFIX = "/static/listening/"


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _is_usable(raw_q):
    title = (raw_q.get("title") or "").strip()
    answer = (raw_q.get("answer") or "").strip()
    if not title or not answer:
        return False
    # multi-answer (e.g. "B,E" — choose TWO) not auto-gradable by our system
    if "," in answer or "/" in answer:
        return False
    return True


def _convert_question(raw_q, seq):
    title = (raw_q.get("title") or "").strip()
    answer = (raw_q.get("answer") or "").strip()
    options = raw_q.get("options") or []
    analysis = raw_q.get("analysis")

    if options:
        return {
            "sequence": seq,
            "question_type": "single_choice",
            "stem": title,
            "options_json": json.dumps(options, ensure_ascii=False),
            "correct_answer": answer,
            "points": 1,
            "reference_answer": analysis,
        }
    # short answer — accept all listed alternative answers
    alts = raw_q.get("answers") or [answer]
    return {
        "sequence": seq,
        "question_type": "short_answer",
        "stem": title,
        "options_json": None,
        "correct_answer": "|".join(a.strip() for a in alts if a),
        "points": 1,
        "reference_answer": analysis,
    }


def _collect_questions(groups, max_q):
    """Walk groups → questions, filter usable, renumber sequences."""
    out = []
    seq = 1
    for g in groups:
        for raw_q in g.get("questions", []):
            if not _is_usable(raw_q):
                continue
            out.append(_convert_question(raw_q, seq))
            seq += 1
            if len(out) >= max_q:
                return out
    return out


def load_listening_section(filename, section_idx, max_q, sequence):
    path = os.path.join(LISTENING_DIR, filename)
    data = json.load(open(path, encoding="utf-8"))
    s = data["sections"][section_idx]
    audio_file = s.get("audio") or ""
    audio_url = AUDIO_URL_PREFIX + audio_file if audio_file else ""
    questions = _collect_questions(s.get("groups", []), max_q)
    if not questions:
        raise ValueError(f"No usable questions in {filename} section {section_idx}")
    return {
        "section_type": "listening",
        "sequence": sequence,
        "title": f"Section 1 · Listening ({s.get('title', '')})",
        "instructions": (
            "请戴耳机收听音频，音频只播放一次。\n"
            "填空题：每空填一个英文单词或数字（注意单复数、拼写）。\n"
            "选择题：选择最符合录音内容的选项。"
        ),
        "audio_url": audio_url,
        "passage": None,
        "duration_minutes": 12,
        "questions": questions,
    }


def _build_passage_text(content):
    parts = []
    title = (content.get("title") or "").strip()
    if title:
        parts.append(f"【{title}】\n")
    for para in content.get("paragraphs", []):
        label = (para.get("label") or "").strip()
        text = (para.get("text") or "").strip()
        if not text:
            continue
        if label:
            parts.append(f"{label}. {text}")
        else:
            parts.append(text)
    return "\n\n".join(parts)


def load_reading_passage(filename, passage_idx, max_q, sequence):
    path = os.path.join(READING_DIR, filename)
    data = json.load(open(path, encoding="utf-8"))
    p = data["passages"][passage_idx]
    passage_text = _build_passage_text(p.get("content", {}))
    questions = _collect_questions(p.get("groups", []), max_q)
    if not questions:
        raise ValueError(f"No usable questions in {filename} passage {passage_idx}")
    return {
        "section_type": "reading",
        "sequence": sequence,
        "title": "Section 2 · Reading",
        "instructions": (
            "阅读下面的文章并回答问题。\n"
            "判断题：T = TRUE / F = FALSE / NG = NOT GIVEN（填字母）。\n"
            "选择题：从给定选项中选择最符合文章内容的字母。\n"
            "填空题：根据文章内容填写关键词（不超过 3 个单词）。"
        ),
        "audio_url": None,
        "passage": passage_text,
        "duration_minutes": 14,
        "questions": questions,
    }


def build_writing_section(prompt, reference_outline, sequence):
    return {
        "section_type": "writing",
        "sequence": sequence,
        "title": "Section 3 · Writing Task 2",
        "instructions": "写一篇议论文（建议字数 150-250 词；时间紧张可只写开头段和提纲）。",
        "audio_url": None,
        "passage": None,
        "duration_minutes": 8,
        "questions": [
            {
                "sequence": 1,
                "question_type": "essay",
                "stem": prompt,
                "options_json": None,
                "correct_answer": None,
                "points": 9,
                "reference_answer": reference_outline,
            }
        ],
    }


# ---------------------------------------------------------------------------
# 7 papers definition
# ---------------------------------------------------------------------------

# Writing prompts (AI-authored), tier difficulty rising
W_PROMPTS = {
    "ielts_45_55_A": (
        "Some people think students should study only the subjects they are interested in. "
        "Others believe students should study a wide range of subjects. "
        "Discuss both views and give your own opinion."
    ),
    "ielts_45_55_B": (
        "In many countries, people now use smartphones to communicate instead of meeting in person. "
        "Do the advantages of this trend outweigh the disadvantages? "
        "Give your opinion with reasons and examples."
    ),
    "ielts_55_65_A": (
        "Some people argue that governments should spend more money on protecting the environment, "
        "while others think the money should be used to improve education and healthcare. "
        "Discuss both views and give your own opinion."
    ),
    "ielts_55_65_B": (
        "In many cities, traffic congestion is getting worse. "
        "Some say building more roads is the answer; others believe public transport should be improved. "
        "Discuss both approaches and state which one you think is more effective."
    ),
    "ielts_65_75_B": (
        "Some people believe that modern technology has made traditional cultural practices less important, "
        "while others argue that technology can help preserve and spread culture. "
        "Discuss both views and give your own opinion."
    ),
    "ielts_75_plus_A": (
        "It is sometimes argued that economic growth is the most reliable measure of a country's success, "
        "yet rising GDP often coincides with widening inequality and environmental decline. "
        "To what extent should governments prioritise economic growth over other measures of national well-being? "
        "Support your view with reasons and concrete examples."
    ),
    "ielts_75_plus_B": (
        "In an age of abundant information, the ability to filter and evaluate sources has arguably become "
        "more valuable than the capacity to memorise facts. "
        "To what extent do you agree that schools should redesign their curriculum to prioritise "
        "critical thinking and media literacy over traditional knowledge acquisition?"
    ),
}

W_OUTLINE = (
    "评分参考（按 IELTS Task 2 四维度）：\n"
    "1) Task Response — 是否清晰回应题目所有部分并给出立场；\n"
    "2) Coherence & Cohesion — 段落结构、连接词使用；\n"
    "3) Lexical Resource — 话题词汇多样性、用词准确；\n"
    "4) Grammatical Range & Accuracy — 句式复杂度、语法正确率。\n"
    "时间紧张时，重点观察学生是否能给出清晰立场、合理论据结构与衔接逻辑。"
)


PAPER_PLAN = [
    # ---------------- 4.5-5.5 入门 ----------------
    {
        "title": "IELTS 4.5-5.5 入门诊断 A（生活场景）",
        "exam_type": "ielts",
        "level": "ielts_45_55",
        "description": "适用于雅思预估 4.5-5.5 段学生。听力来自剑桥雅思 10 Section 1（日常生活场景），阅读为中等长度学术文章，写作为单观点议论文。约 30 分钟。",
        "listening_src": ("ielts10_test1.json", 0, 8),
        "reading_src": ("reading_jijing_10_test_78.json", 0, 7),
        "writing_key": "ielts_45_55_A",
    },
    {
        "title": "IELTS 4.5-5.5 入门诊断 B（旅行咨询）",
        "exam_type": "ielts",
        "level": "ielts_45_55",
        "description": "适用于雅思预估 4.5-5.5 段学生（备选卷）。听力来自剑桥雅思 11 Section 1，阅读为科普类文章，写作为科技/沟通主题。约 30 分钟。",
        "listening_src": ("ielts11_test1.json", 0, 8),
        "reading_src": ("reading_jijing_11_test_103.json", 0, 7),
        "writing_key": "ielts_45_55_B",
    },
    # ---------------- 5.5-6.5 进阶 ----------------
    {
        "title": "IELTS 5.5-6.5 进阶诊断 A（独白介绍）",
        "exam_type": "ielts",
        "level": "ielts_55_65",
        "description": "适用于雅思预估 5.5-6.5 段学生。听力来自剑桥雅思 13 Section 2（公共场所半学术独白），阅读为科普类，写作为环境/教育主题双观点对比。约 30 分钟。",
        "listening_src": ("ielts13_test1.json", 1, 8),
        "reading_src": ("reading_jijing_13_test_6.json", 0, 7),
        "writing_key": "ielts_55_65_A",
    },
    {
        "title": "IELTS 5.5-6.5 进阶诊断 B（服务介绍）",
        "exam_type": "ielts",
        "level": "ielts_55_65",
        "description": "适用于雅思预估 5.5-6.5 段学生（备选卷）。听力来自剑桥雅思 14 Section 2，阅读为社会议题文章，写作为城市交通双观点对比。约 30 分钟。",
        "listening_src": ("ielts14_test1.json", 1, 8),
        "reading_src": ("reading_jijing_14_test_23.json", 0, 7),
        "writing_key": "ielts_55_65_B",
    },
    # ---------------- 6.5-7.5 标准 (补充 B；A 是已有 id=2) ----------------
    {
        "title": "IELTS 6.5-7.5 标准诊断 B（学术讨论）",
        "exam_type": "ielts",
        "level": "ielts_65_75",
        "description": "适用于雅思预估 6.5-7.5 段学生（补充卷，与现有 IELTS 6.0-7.5 诊断互为平行卷）。听力来自剑桥雅思 17 Section 3（学生学术讨论），阅读为职场议题，写作为文化/科技双观点。约 30 分钟。",
        "listening_src": ("ielts17_test1.json", 2, 8),
        "reading_src": ("reading_jijing_16_test_97.json", 1, 7),
        "writing_key": "ielts_65_75_B",
    },
    # ---------------- 7.5+ 冲刺 ----------------
    {
        "title": "IELTS 7.5+ 冲刺诊断 A（深度讨论）",
        "exam_type": "ielts",
        "level": "ielts_75_plus",
        "description": "适用于雅思预估 7.5 分以上学生。听力来自剑桥雅思 18 Section 3（学术研究讨论），阅读为新闻分析类文章，写作为经济发展与社会因果抽象分析。约 30 分钟。",
        "listening_src": ("ielts18_test1.json", 2, 8),
        "reading_src": ("reading_jijing_18_test_53.json", 2, 7),
        "writing_key": "ielts_75_plus_A",
    },
    {
        "title": "IELTS 7.5+ 冲刺诊断 B（学术辩论）",
        "exam_type": "ielts",
        "level": "ielts_75_plus",
        "description": "适用于雅思预估 7.5 分以上学生（备选卷）。听力来自剑桥雅思 18 Section 3，阅读为团队协作机制深度文章，写作为信息时代教育课程改革。约 30 分钟。",
        "listening_src": ("ielts18_test2.json", 2, 8),
        "reading_src": ("reading_jijing_22_test_90.json", 2, 7),
        "writing_key": "ielts_75_plus_B",
    },
]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def _get_default_creator_id():
    user = User.query.filter(User.role.in_(("admin", "teacher"))).first()
    if not user:
        user = User.query.first()
    return user.id if user else None


def _verify_source_files():
    missing = []
    for plan in PAPER_PLAN:
        lfile, _, _ = plan["listening_src"]
        rfile, _, _ = plan["reading_src"]
        if not os.path.isfile(os.path.join(LISTENING_DIR, lfile)):
            missing.append(f"listening: {lfile}")
        if not os.path.isfile(os.path.join(READING_DIR, rfile)):
            missing.append(f"reading: {rfile}")
    return missing


def _build_paper_data(plan):
    lfile, lidx, lmax = plan["listening_src"]
    rfile, ridx, rmax = plan["reading_src"]
    listening = load_listening_section(lfile, lidx, lmax, sequence=1)
    reading = load_reading_passage(rfile, ridx, rmax, sequence=2)
    writing = build_writing_section(
        W_PROMPTS[plan["writing_key"]], W_OUTLINE, sequence=3
    )
    return {
        "title": plan["title"],
        "exam_type": plan["exam_type"],
        "level": plan["level"],
        "description": plan["description"],
        "sections": [listening, reading, writing],
    }


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
    n_q = sum(len(s["questions"]) for s in data["sections"])
    print(f"  [CREATED] '{data['title']}' (id={paper.id}, {n_q} questions)")
    return paper


def main():
    missing = _verify_source_files()
    if missing:
        print("Error: missing source files:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    with app.app_context():
        creator_id = _get_default_creator_id()
        if not creator_id:
            print("Error: no user in DB to own the papers. Create an admin first.")
            sys.exit(1)

        print(f"Seeding IELTS tiered papers (creator user id={creator_id})...")
        for plan in PAPER_PLAN:
            try:
                data = _build_paper_data(plan)
            except Exception as e:
                print(f"  [ERROR] {plan['title']}: {e}")
                continue
            seed_paper(data, creator_id)
        print("Done.")


if __name__ == "__main__":
    main()
