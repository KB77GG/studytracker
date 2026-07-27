#!/usr/bin/env python3
"""Build TOEFL practice v2 packages from source-backed extraction artifacts.

The script intentionally writes only data/toefl_practice_v2. It does not touch
legacy StudyTracker TOEFL data, production routes, or runtime databases.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXAM_KEY = "2026-01-21_B"
PROGRESS_KEY = "2026-01-21-B"
EXAM_ID = "toefl:2026-01-21-b"
SOURCE_FOLDER = "1.21新托福真题B 卷"
PAPER = f"{SOURCE_FOLDER}/新托福2026年真题02.pdf"
ANSWER_PDF = f"{SOURCE_FOLDER}/参考答案-新托福2026真题02.pdf"
TRANSCRIPT_PDF = f"{SOURCE_FOLDER}/听力原文-新托福2026真题02.pdf"
LISTENING_M1_AUDIO = f"{SOURCE_FOLDER}/2026新托福真题01ListeningModule1.mp3"
LISTENING_M2_AUDIO = f"{SOURCE_FOLDER}/2026新托福真题01ListeningModule2.mp3"
SPEAKING_AUDIO = f"{SOURCE_FOLDER}/2026新托福真题01SpeakingModule1.mp3"
READING_CACHE = "tmp/pdfs/reading_structured/extracted/02_2026_01_21_B.json"
READING_REPAIR_Q21 = "tmp/pdfs/reading_structured/repairs/02_2026_01_21_B_003.json"
READING_REPAIR_Q23 = "tmp/pdfs/reading_structured/repairs/02_2026_01_21_B_005.json"
READING_REPAIR_Q27 = "tmp/pdfs/reading_structured/repairs/02_2026_01_21_B_009.json"
READING_EXTRA_SOURCE_PATHS = [READING_REPAIR_Q21, READING_REPAIR_Q23, READING_REPAIR_Q27]
LISTENING_MD = "新托福分科刷题材料/整理输出/托福真题整理_听力.md"
WRITING_MD = "新托福分科刷题材料/整理输出/托福真题整理_写作.md"
SPEAKING_MD = "新托福分科刷题材料/整理输出/托福真题整理_口语.md"
SPEAKING_TRANSCRIPT_JSON = "新托福分科刷题材料/整理输出/口语转写_修订版/transcripts/2026-01-21_B_part1.json"
LISTENING_SECTION_HEADING = "## 2026-01-21 B卷"
LISTENING_SECTION_STOP_MARKER = "### 来源：1.21新托福真题B 卷/听力原文"
LISTENING_PROMPT_UPPER = {"m1": 12, "m2": 3}
READING_PAGE_OVERRIDES: dict[tuple[str, int], int] = {}
READING_M2_START_PAGE: int | None = None
READING_NUMBER_REPAIRS: dict[tuple[str, int, str], int] = {}
LISTENING_PAGE_OVERRIDES: dict[tuple[str, int], int] = {}
LISTENING_STEM_OVERRIDES: dict[tuple[str, int], str] = {}
GRADING_BLOCKED_READING: set[tuple[str, int]] = set()
GRADING_BLOCKED_LISTENING: set[tuple[str, int]] = set()
ANSWER_EVIDENCE_OVERRIDES: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
SPEAKING_CONTENT_STATUS = "needs_review"
EXAM_TITLE = "2026-01-21 TOEFL Real Exam B"
EXAM_DATE = "2026-01-21"
EXAM_VARIANT = "B"
PROGRESS_NOTES = "120 atomic questions rebuilt from source; Reading M2 Q12 remains source-blocked, and a speaking audio/paper mismatch requires review before reintegration."
BLOCKING_REASONS = [
    "Reading M2 Q12 is absent from the current source paper and extraction.",
    "Speaking audio transcript conflicts with the paper/answer-PDF grocery-store scene and needs manual source review.",
]
LATEST_BLOCKER_TEXT = "Reading M2 Q12 is absent from the source paper/extraction; speaking audio transcript conflicts with paper/answer PDF scene text."
QA_CHECK_SPECS = [
    {"id": "atomic-count", "status": "pass", "detail": "120 expected atomic questions are represented."},
    {"id": "answer-separation", "status": "pending", "detail": "Validator will check public content for answer leakage."},
    {"id": "reading-source", "status": "blocked", "detail": "Reading M2 Q12 is absent from the source paper/extraction; M2 Q13 was visually recovered from paper page 12."},
    {"id": "listening-source", "status": "pass", "detail": "Listening M1 Q1/M1 Q7/M2 Q1 options were visually recovered from rendered source pages."},
    {"id": "media", "status": "pass", "detail": "Listening and speaking audio files exist and have readable ffprobe durations."},
    {"id": "speaking-source-conflict", "status": "blocked", "detail": "The speaking audio transcript says class registration/hobbies, while the paper and answer PDF indicate grocery store/hobbies."},
    {"id": "inline-reading-contract", "status": "pass", "detail": "Complete-the-words groups define inline token rendering without public answer fields."},
]
BLOCKED_REASON_BY_ITEM: dict[tuple[str, str, int], str] = {}

READING_ANSWERS = {
    "m1": [
        "actions", "plet", "th", "tions", "ial", "he", "tical", "omic", "ienced", "nges",
        "le", "lishes", "er", "rge", "ning", "are", "nd", "he", "larly", "ok",
        "C", "C", "B", "A", "A", "C", "D", "B", "D", "C", "C", "B", "B", "D", "A",
    ],
    "m2": ["ther", "ke", "saw", "nd", "ift", "quakes", "ation", "tains", "anic", "tists", "C", "B", "D", "A", "C"],
}
LISTENING_ANSWERS = {
    "m1": ["C", "D", "D", "C", "D", "D", "B", "D", "A", "B", "C", "B", "C", "D", "C", "B", "C", "C", "B", "D", "C", "D", "C", "D", "C", "A", "B", "C", "C", "B", "B", "A"],
    "m2": ["A", "A", "B", "A", "B", "B", "C", "A", "D", "B", "D", "D", "D", "B", "D"],
}
FILL_PREFIXES = {
    "m1": ["popul", "com", "wi", "tradi", "soc", "T", "poli", "econ", "exper", "cha", "ma", "estab", "ov", "la", "span", "squ", "a", "t", "regu", "lo"],
    "m2": ["toge", "li", "", "a", "sh", "earth", "form", "moun", "volc", "Scien"],
}
FILL_DISPLAY = {
    "m1_01": (
        "The history of the South Pacific is marked by diverse cultures and significant events. Indigenous "
        "{q01:popul} developed {q02:com} societies {q03:wi} rich {q04:tradi} and {q05:soc} structures. "
        "{q06:T} region's {q07:poli} and {q08:econ} landscapes {q09:exper} profound {q10:cha} following "
        "colonization by European powers. Studying this history allows for a greater understanding of cultural interactions and the ongoing effects of historical events on contemporary South Pacific societies."
    ),
    "m1_02": (
        "Tigers are solitary animals known for their territorial behavior; males use scent markings and vocalizations to define their territories. "
        "Each {q11:ma} tiger {q12:estab} control {q13:ov} a {q14:la} territory {q15:span} several {q16:squ} miles "
        "{q17:a} patrols {q18:t} area {q19:regu} to {q20:lo} for prey and maintain dominance. "
        "This behavior helps reduce conflicts over prey, but tigers are known to fiercely defend their territory from intruders when necessary."
    ),
    "m2_01": (
        "Tectonic plates are large pieces of Earth's outer shell that move slowly over the planet's surface, and their study is fundamental in understanding Earth's geological activity. "
        "These plates fit {q01:toge} much {q02:li} a jig{q03:} puzzle {q04:a} constantly {q05:sh}, causing {q06:earth} in the {q07:form} of {q08:moun}, and {q09:volc} eruptions. "
        "{q10:Scien} analyze these movements to better understand natural disasters and how Earth's surface changes over time."
    ),
}
READING_GROUPS = {
    "m1": [
        (1, 10, "complete_words", "South Pacific History"),
        (11, 20, "complete_words", "Tiger Territories"),
        (21, 22, "read_in_daily_life", "FitLife Gym Membership"),
        (23, 24, "read_in_daily_life", "Blundin University Career Fair"),
        (25, 27, "academic_passage", "AI-Generated Art on Campus"),
        (28, 30, "read_in_daily_life", "Downtown School of Data Skills"),
        (31, 35, "academic_passage", "Augmented Reality for Training"),
    ],
    "m2": [
        (1, 10, "complete_words", "Tectonic Plates"),
        (11, 15, "academic_passage", "Formation of Sedimentary Rocks"),
    ],
}
READING_MC_OVERRIDES = {
    ("m1", 21): {
        "stem": "What benefits does a quarterly member have that a monthly member lacks?",
        "options": ["Equipment access and guest passes", "Personal training discounts only", "Group classes and swimming privileges", "Free trial and minimum commitment"],
        "confidence": "visually_recovered",
        "extra_sources": [READING_REPAIR_Q21],
    },
    ("m1", 23): {
        "stem": "What did Ryan do yesterday?",
        "options": ["He took a class at a university.", "He attended a job fair.", "He was interviewed by a manager.", "He hired some summer interns."],
        "confidence": "visually_recovered",
        "extra_sources": [READING_REPAIR_Q23],
    },
    ("m1", 24): {
        "stem": "What does Ryan ask his team to do?",
        "options": ["Share their opinions of some job candidates", "Review a summer internship program", "Update their resumes by Friday", "Introduce themselves to new interns"],
        "confidence": "reviewed_repair",
    },
    ("m1", 25): {
        "stem": "What is the main topic of the article?",
        "options": ["An art exhibit highlighting technology-driven creativity", "A debate over mixing art and technology", "How students are learning traditional painting", "A plan to replace the art gallery with a data center"],
        "confidence": "visually_recovered",
    },
    ("m1", 27): {
        "stem": "What can be inferred about the impact of the exhibit's interactive portion?",
        "options": ["It asks visitors to consider the ethical implications of using AI to create art.", "It has caused visitors to switch majors from art to computer science.", "It has led to calls to replace traditional art with AI art.", "It tries to help visitors feel comfortable using AI in their creative endeavors."],
        "confidence": "visually_recovered",
        "extra_sources": [READING_REPAIR_Q27],
    },
    ("m1", 30): {
        "stem": "Beth has worked with formulas for years and is ready to learn advanced data skills. She should enroll in",
        "options": ["Section A, B, or C", "Section D or E", "Section F", "Section G"],
        "confidence": "reviewed_repair",
    },
    ("m1", 31): {
        "stem": 'The word "groundbreaking" in the passage is closest in meaning to',
        "options": ["educational", "practical", "revolutionary", "interesting"],
        "confidence": "reviewed_repair",
    },
    ("m1", 32): {
        "stem": "What is the function of AR as described in the passage?",
        "options": ["AR artificially enhances human performance", "AR produces realistic experiences in a learning environment", "AR enables unskilled humans to interact with complex machines", "AR produces a digital record of real-world content"],
        "confidence": "reviewed_repair",
    },
    ("m1", 33): {
        "stem": "AR reduces which of the following problems associated with traditional training environments?",
        "options": ["Their inability to simulate authentic experiences", "Their physical dangers", "Their inaccessibility to many learners", "Their high financial costs"],
        "confidence": "reviewed_repair",
    },
    ("m1", 35): {
        "stem": "What is one problem the passage mentions related to the use of AR?",
        "options": ["The costs associated with making it useful to particular clients", "Disagreement among experts regarding its accuracy", "A lack of measurable benefits in its present stage of development", "The absence of existing training programs into which it may be integrated"],
        "confidence": "reviewed_repair",
    },
    ("m2", 13): {
        "stem": "What is the role of groundwater in sedimentary rock formation?",
        "options": [
            "It provides the compaction needed for the sedimentation process.",
            "It eventually dissolves the particles in sedimentary rocks.",
            "It carries sediments to new locations.",
            "It deposits minerals that bind sediments together.",
        ],
        "confidence": "visually_recovered",
    },
}
BLOCKED_READING = {("m2", 12)}

LISTENING_GROUPS = {
    "m1": [
        (1, 12, "listen_and_choose", "Choose the Best Response"),
        (13, 14, "conversation", "University Orchestra Concert"),
        (15, 16, "conversation", "Parking Garage Ticket"),
        (17, 18, "conversation", "Kitchenware Store Gift"),
        (19, 20, "announcement", "Environmental Science Report"),
        (21, 22, "announcement", "School Art Exhibit Tour"),
        (23, 24, "announcement", "Library Closure"),
        (25, 28, "lecture", "Inertia and Bicycle Turns"),
        (29, 32, "lecture", "Industrial European Cities"),
    ],
    "m2": [
        (1, 3, "listen_and_choose", "Choose the Best Response"),
        (4, 5, "conversation", "Mural Project"),
        (6, 7, "conversation", "Yoga Class Cancellation"),
        (8, 11, "lecture", "Multispecies Anthropology"),
        (12, 15, "lecture", "Eastgate Centre"),
    ],
}
BLOCKED_LISTENING: set[tuple[str, int]] = set()
LISTENING_OPTION_OVERRIDES = {
    ("m1", 1): ["The last appointment is at 2 p.m.", "The wait time is three hours.", "Near the registrar's office.", "She's following the doctor's advice."],
    ("m1", 5): ["This is an excellent poem.", "No, it's not always true.", "Yes, I bought a new one.", "I have too much work."],
    ("m1", 6): ["Yes, that was most likely true.", "All companies offer similar benefits.", "I was too busy.", "I wanted to help my fellow students."],
    ("m1", 7): ["I've been there once.", "I've been too busy to organize it.", "The new furniture looks great.", "It should arrive tomorrow."],
    ("m1", 8): ["It's a device that runs on solar power.", "Yes, they usually go out to eat.", "I thought it was a powerful speech.", "It looks like the streetlights outside the dorm are still on."],
    ("m1", 9): ["I think Emily should.", "Everyone needs to register online.", "It was a lively class.", "There is new homework."],
    ("m1", 11): ["Yes, I think it is.", "A very noisy concert.", "Sure, sorry about that.", "No, I'm not going to return it."],
    ("m1", 12): ["My order was placed yesterday.", "Let's check in the main office.", "There are a lot of new clubs this year.", "One box and four bags."],
    ("m1", 14): ["He is worried that he might get cold.", "He thinks the tickets are too expensive.", "He would like a seat close to the stage.", "He will sit in the grass with the woman's friends."],
    ("m1", 16): ["A parking ticket on her car", "Signs about parking rules", "A change in parking garage hours", "An email about faculty parking"],
    ("m1", 17): ["A new recipe book", "A set of kitchen knives", "A gift for a friend", "A cooking class"],
    ("m1", 19): ["To remind students of a deadline", "To point out the requirements for an assignment", "To invite students to office hours", "To discuss environmental science topics"],
    ("m1", 32): ["Property became easier to buy and sell.", "Modern forms of transportation became available.", "New spaces were created for expanding central markets.", "New laws were passed that separated residential and industrial areas."],
    ("m2", 1): ["Let's see what's on the agenda first.", "We need to send invitations.", "The club room is more spacious.", "Friday is better."],
    ("m2", 2): ["I need to clean them up first.", "I don't think Tim took notes either.", "Class ran long.", "I didn't expect so many people to be there."],
    ("m2", 3): ["Yes, I need them immediately.", "I have no idea where I left them.", "No, it's actually quite far from here.", "You can put them in here."],
    ("m2", 9): ["It led to the development of multispecies anthropology.", "It was the first study to examine Arctic hunting rituals.", "It challenged common views about rituals.", "Its view of the animal-human relationship was too simple."],
    ("m2", 11): ["How a study was influenced by a researcher's personal background", "How culture influences human foraging practices", "How humans have damaged the natural environment", "How research methods have changed"],
}

WRITING_ORDERED = {
    1: "have you applied for it yet?",
    2: "have you started the application process ?",
    3: "do you know if she included the schedule ?",
    4: "what will you be discussing ?",
    5: "what topic are you writing about ?",
    6: "what time does the game start ?",
    7: "I was not able to complete it before the deadline.",
    8: "Do you know if the new due date has been announced ?",
    9: "Sorry, but I have not had time to look at it yet.",
    10: "The dates when it is scheduled conflict with my other commitments .",
}
WRITING_SENTENCE_ITEMS = {
    1: ("I saw a job posting for a part-time position at the student bookstore.", ["yet?", "for", "you", "have", "it", "applied"]),
    2: ("I'm thinking of applying for a scholarship.", ["application", "started", "you", "have", "the", "process"]),
    3: ("Hannah mentioned the upcoming research conference in her email.", ["know", "the", "schedule", "do", "if", "she", "you", "included"]),
    4: ("I have a meeting with my advisor this afternoon.", ["you", "?", "what", "discussing", "be", "will"]),
    5: ("I need to finish my essay by Friday.", ["are", "?", "writing", "you", "about", "topic", "what"]),
    6: ("Tomorrow is the big game between our school and the rival team.", ["does", "?", "the", "what", "game", "start", "time"]),
    7: ("Did you finish the assignment on time?", ["the", "deadline.", "not", "it", "before", "to", "complete", "able", "was"]),
    8: ("The assignment deadline has been extended.", ["Do", "the", "new", "due", "date", "know", "has", "been", "announced", "you", "if"]),
    9: ("Did you get a chance to review the report?", ["Sorry,", "but", "I", "yet.", "to", "look", "not", "at", "time", "have", "had", "it"]),
    10: ("Why aren't you attending the conference?", ["The", "dates", "it", "conflict", "with", "other", "commitments", "when", "is", "scheduled", "my"]),
}
WRITING_MANUAL_PROMPTS = {
    11: (
        "You recently joined a student organization at your university that focuses on environmental conservation. "
        "The group is planning an upcoming event to raise awareness about recycling and reducing waste. You have some ideas for activities and would like to share them with the group leader, Julia. "
        "Write an email to Julia. Describe your ideas for the awareness event, explain why you believe these activities will be effective, and offer to help organize and implement the activities. "
        "To: Julia. Subject: Ideas for recycling awareness event. Write as much as you can and in complete sentences."
    ),
    12: (
        "Your professor is teaching a class on psychology and asks you to write a post responding to the discussion. "
        "Dr. Achebe asks: We've been discussing the role of nature versus nurture in human development. Some experts believe that genetics play the most significant role in shaping who we are, while others argue that our environment and experiences are more important. Which do you think has a greater impact on human development: nature or nurture? Why? "
        "Claire argues that nurture has a greater impact because surroundings and experiences shape beliefs and personalities. Paul argues that nature has a more significant role because genetics determine many aspects of personality, intelligence, and physical abilities. "
        "Express and support your opinion, contribute to the discussion in your own words, and write at least 100 words."
    ),
}
WRITING_PAGES = {1: 56, 2: 56, 3: 57, 4: 57, 5: 58, 6: 58, 7: 59, 8: 59, 9: 60, 10: 60, 11: 62, 12: 63}
WRITING_FIXED_TEXT: dict[int, dict[str, str]] = {}

SPEAKING_REPEAT_AUDIO_TRANSCRIPT = [
    "Enter your name and student ID number.",
    "Browse the course catalog to choose your classes.",
    "You can use the schedule planner tool to avoid time conflicts.",
    "If a class is already full, a pop-up message will appear.",
    "Contact the instructor to see if more seats can be added.",
    "You can still add or drop classes up until the second week of the new semester.",
    "For your records, print out a list of your classes or email a copy to yourself.",
]
SPEAKING_INTERVIEW_AUDIO_TRANSCRIPT = [
    "To begin, do you have a hobby or interest that you regularly spend time doing?",
    "If you were to select a new hobby, what would you choose and why?",
    "Now tell me what might prevent you from starting this new pastime.",
    "Some people believe it is better to have one interest outside of work or school, that you dedicate yourself to, rather than multiple smaller ones. What do you think about that, and why?",
]
SPEAKING_PAGES = {1: 66, 2: 67, 3: 68, 4: 69, 5: 70, 6: 71, 7: 72, 8: 73, 9: 74, 10: 74, 11: 75}

C_EXAM_CONFIG: dict[str, Any] = {
    "EXAM_KEY": "2026-01-21_C",
    "PROGRESS_KEY": "2026-01-21-C",
    "EXAM_ID": "toefl:2026-01-21-c",
    "SOURCE_FOLDER": "1.21新托福真题C卷",
    "PAPER": "1.21新托福真题C卷/新托福2026年真题03.pdf",
    "ANSWER_PDF": "1.21新托福真题C卷/参考答案-新托福2026真题03.pdf",
    "TRANSCRIPT_PDF": "1.21新托福真题C卷/听力原文-新托福2026真题03.pdf",
    "LISTENING_M1_AUDIO": "1.21新托福真题C卷/新托福2026真题03ListeningModule1.mp3",
    "LISTENING_M2_AUDIO": "1.21新托福真题C卷/新托福2026真题03ListeningModule2.mp3",
    "SPEAKING_AUDIO": "1.21新托福真题C卷/新托福2026真题03SpeakingModule1.mp3",
    "READING_CACHE": "tmp/pdfs/reading_structured/extracted/03_2026_01_21_C.json",
    "READING_EXTRA_SOURCE_PATHS": [
        "tmp/pdfs/reading_structured/repairs/03_2026_01_21_C_005.json",
        "tmp/pdfs/reading_structured/repairs/03_2026_01_21_C_007.json",
        "tmp/pdfs/reading_structured/repairs/03_2026_01_21_C_013.json",
    ],
    "SPEAKING_TRANSCRIPT_JSON": "新托福分科刷题材料/整理输出/口语转写_修订版/transcripts/2026-01-21_C_part1.json",
    "LISTENING_SECTION_HEADING": "## 2026-01-21 C卷",
    "LISTENING_SECTION_STOP_MARKER": "### 来源：1.21新托福真题C卷/听力原文",
    "LISTENING_PROMPT_UPPER": {"m1": 12, "m2": 7},
    "EXAM_TITLE": "2026-01-21 TOEFL Real Exam C",
    "EXAM_VARIANT": "C",
    "PROGRESS_NOTES": "120 atomic questions rebuilt from source; Reading M1 Q24 remains blocked because the visible source meaning conflicts with the answer PDF.",
    "BLOCKING_REASONS": [
        "Reading M1 Q24 has a source/answer-key conflict: the answer PDF says D, while the visible option semantics support 'Having little spending money' (option B).",
    ],
    "LATEST_BLOCKER_TEXT": "Reading M1 Q24 has an unresolved answer-key/source conflict.",
    "QA_CHECK_SPECS": [
        {"id": "atomic-count", "status": "pass", "detail": "120 expected atomic questions are represented."},
        {"id": "answer-separation", "status": "pending", "detail": "Validator will check public content for answer leakage."},
        {"id": "reading-source", "status": "blocked", "detail": "Reading M1 Q24 is present but excluded from auto-grading because the answer PDF conflicts with the visible source meaning."},
        {"id": "listening-source", "status": "pass", "detail": "Listening M2 Q1 and M2 Q5 options were visually recovered from rendered source pages."},
        {"id": "media", "status": "pass", "detail": "Listening and speaking audio files exist and have readable ffprobe durations."},
        {"id": "speaking-source", "status": "pass", "detail": "Speaking audio transcript aligns with the paper's email-system and exercise-program scenes."},
        {"id": "inline-reading-contract", "status": "pass", "detail": "Complete-the-words groups define inline token rendering without public answer fields."},
    ],
    "READING_ANSWERS": {
        "m1": [
            "ther", "rature", "act", "ation", "uals", "nation", "ny", "mone", "ease", "ing",
            "le", "lishes", "er", "rge", "ning", "are", "nd", "he", "larly", "ok",
            "B", "A", "B", "D", "B", "D", "C", "C", "B", "D", "B", "B", "B", "A", "C",
        ],
        "m2": ["mine", "nets", "xies", "ations", "els", "ribe", "nts", "ely", "ea", "ich", "D", "A", "C", "B", "C"],
    },
    "FILL_PREFIXES": {
        "m1": ["toge", "tempe", "imp", "migr", "rit", "hiber", "ma", "hor", "incr", "spr", "ma", "estab", "ov", "la", "span", "squ", "a", "t", "regu", "lo"],
        "m2": ["exa", "pla", "gala", "observ", "mod", "desc", "eve", "wid", "id", "wh"],
    },
    "FILL_DISPLAY": {
        "m1_01": (
            "The reaction of plants and animals to sunlight and seasonal changes, known as photoperiodism or seasonality, is vital to many biological and behavioral processes. "
            "Photoperiods, {q01:toge} with {q02:tempe} changes, {q03:imp} seasonal {q04:migr}, mating {q05:rit}, and {q06:hiber}. "
            "In {q07:ma} birds, {q08:hor} levels {q09:incr} in {q10:spr}, which leads to an increase in singing frequency in males and mating behaviors. "
            "Photoperiodism allows plants and animals to respond to changes in the environment associated with changing seasons and varying day length."
        ),
        "m1_02": (
            "Tigers are solitary animals known for their territorial behavior; males use scent markings and vocalizations to define their territories. "
            "Each {q11:ma} tiger {q12:estab} control {q13:ov} a {q14:la} territory {q15:span} several {q16:squ} miles "
            "{q17:a} patrols {q18:t} area {q19:regu} to {q20:lo} for prey and maintain dominance. "
            "This behavior helps reduce conflicts over prey, but tigers are known to fiercely defend their territory from intruders when necessary. Often hunting at night, tigers use stealth and their excellent night vision to their advantage."
        ),
        "m2_01": (
            "Cosmology is the study of how the universe began, changed over time, and might evolve in the future. "
            "Scientists {q01:exa} stars, {q02:pla}, and {q03:gala}, using {q04:observ} and {q05:mod} to {q06:desc} cosmic {q07:eve}. "
            "One {q08:wid} accepted {q09:id} is the big bang, {q10:wh} suggests the universe started from a single point and has been expanding ever since. "
            "Ongoing research helps improve our understanding of space, time, and the forces shaping the cosmos, revealing new discoveries about the vast universe."
        ),
    },
    "READING_GROUPS": {
        "m1": [
            (1, 10, "complete_words", "Photoperiodism"),
            (11, 20, "complete_words", "Tiger Territories"),
            (21, 22, "read_in_daily_life", "Blundin University Career Fair"),
            (23, 24, "product_review", "WaveSound Earbuds"),
            (25, 27, "read_in_daily_life", "Downtown School of Data Skills"),
            (28, 30, "schedule", "University Health and Wellness Conference"),
            (31, 35, "academic_passage", "Radio Astronomy"),
        ],
        "m2": [
            (1, 10, "complete_words", "Cosmology"),
            (11, 15, "academic_passage", "Green Roof Benefits"),
        ],
    },
    "READING_MC_OVERRIDES": {
        ("m1", 21): {
            "stem": "What did Ryan do yesterday?",
            "options": ["He took a class at a university.", "He attended a job fair.", "He was interviewed by a manager.", "He hired some summer interns."],
            "confidence": "source_exact",
        },
        ("m1", 22): {
            "stem": "What does Ryan ask his team to do?",
            "options": ["Share their opinions of some job candidates", "Review a summer internship program", "Update their resumes by Friday", "Introduce themselves to new interns"],
            "confidence": "reviewed_repair",
        },
        ("m1", 23): {
            "stem": "According to the reviewer, what is one of the benefits of the WaveSound Earbuds compared to other products?",
            "options": ["They are more reliable.", "They offer better value.", "They are more luxurious.", "They sound better."],
            "confidence": "reviewed_repair",
            "extra_sources": ["tmp/pdfs/reading_structured/repairs/03_2026_01_21_C_005.json"],
        },
        ("m1", 24): {
            "stem": "What aspect of student life does being \"on a shoestring\" refer to?",
            "options": ["Balancing work and academics", "Having little spending money", "Studying for long periods of time", "Preparing for a future career"],
            "confidence": "reviewed_repair",
            "extra_sources": ["tmp/pdfs/reading_structured/repairs/03_2026_01_21_C_007.json"],
        },
        ("m1", 25): {
            "stem": "Peter has no experience with spreadsheets and cannot attend class on Wednesdays. He should enroll in",
            "options": ["Section A", "Section B", "Section C", "Section D"],
            "confidence": "source_exact",
        },
        ("m1", 26): {
            "stem": "What does Michelle need before enrolling in Section D?",
            "options": ["Experience creating new spreadsheet formulas", "A research position that requires creating formulas", "Training in how to present complex data", "Previous experience using spreadsheets"],
            "confidence": "source_exact",
        },
        ("m1", 27): {
            "stem": "Beth has worked with formulas for years and is ready to learn advanced data skills. She should enroll in",
            "options": ["Section A, B, or C", "Section D or E", "Section F", "Section G"],
            "confidence": "source_exact",
        },
        ("m1", 28): {
            "stem": "What is the main purpose of the schedule?",
            "options": ["To provide information on a conference keynote address", "To provide conference registration details", "To list events happening at a conference", "To provide information about refreshments at a conference"],
            "confidence": "reviewed_repair",
        },
        ("m1", 29): {
            "stem": "All of the following are reasons why someone might choose to attend the event EXCEPT",
            "options": ["to learn how to concentrate better on their studies", "to gather materials for applying to medical school", "to speak directly with people in the health industry", "to gain access to wellness resources"],
            "confidence": "reviewed_repair",
            "extra_sources": ["tmp/pdfs/reading_structured/repairs/03_2026_01_21_C_013.json"],
        },
        ("m1", 30): {
            "stem": "What is likely true about most of the attendees?",
            "options": ["They will receive free healthcare services at the event.", "They work in the health industry.", "They are visiting from other regions.", "They are students."],
            "confidence": "reviewed_repair",
        },
        ("m1", 32): {
            "stem": "The word \"transformative\" in the passage is closest in meaning to",
            "options": ["meaning to", "groundbreaking", "exciting", "concerning"],
            "confidence": "source_exact",
        },
        ("m1", 33): {
            "stem": "According to the passage, radio astronomy helps scientists study all of the following EXCEPT",
            "options": ["the beginnings of the universe", "how to prevent the explosions of large stars", "the last stages of stars", "the way matter behaves under extreme conditions"],
            "confidence": "reviewed_repair",
        },
        ("m1", 34): {
            "stem": "Why does the author mention \"the global spread of wireless technology\"?",
            "options": ["To suggest that the issue of technological interference is not likely to end soon", "To argue that technological interference is not as severe as was once thought", "To support the argument that optical telescopes are more reliable than radio telescopes", "To highlight the sophisticated tools astronomers use to detect cosmic signals"],
            "confidence": "source_exact",
        },
        ("m1", 35): {
            "stem": "According to the passage, what is one way to address the issue of technological interference?",
            "options": ["Revive the use of optical telescopes", "Limit wireless routers to certain frequencies", "Place observatories far away from urban areas", "Mandate specific quiet times when the use of wireless technology is prohibited"],
            "confidence": "reviewed_repair",
        },
        ("m2", 15): {
            "stem": "Where would the sentence best fit? Select a location to add the sentence in the passage.",
            "options": ["Location A", "Location B", "Location C", "Location D"],
            "confidence": "reviewed_repair",
        },
    },
    "BLOCKED_READING": set(),
    "GRADING_BLOCKED_READING": {("m1", 24)},
    "READING_PAGE_OVERRIDES": {
        **{("m1", 26): 6, ("m1", 27): 7, ("m1", 28): 8, ("m1", 29): 8, ("m1", 30): 9, ("m1", 31): 9, ("m1", 32): 10, ("m1", 33): 10, ("m1", 34): 10, ("m1", 35): 11},
        **{("m2", number): 12 for number in range(1, 12)},
        **{("m2", number): 13 for number in range(12, 15)},
        ("m2", 15): 14,
    },
    "LISTENING_ANSWERS": {
        "m1": ["A", "A", "D", "C", "D", "B", "C", "D", "D", "B", "C", "A", "A", "D", "C", "D", "A", "B", "B", "A", "C", "C", "C", "D", "B", "A", "C", "B", "C", "A", "B", "C"],
        "m2": ["A", "B", "B", "D", "A", "B", "A", "A", "D", "A", "C", "A", "B", "C", "A"],
    },
    "LISTENING_GROUPS": {
        "m1": [
            (1, 12, "listen_and_choose", "Choose the Best Response"),
            (13, 14, "conversation", "Campus Housing Cost"),
            (15, 16, "conversation", "University Orchestra Concert"),
            (17, 18, "conversation", "Tutoring Appointment"),
            (19, 20, "announcement", "Student Organization Event Policy"),
            (21, 22, "announcement", "Fashion Design Internship"),
            (23, 24, "announcement", "Art Exhibit Tour"),
            (25, 28, "lecture", "Scarlet Badis"),
            (29, 32, "lecture", "Bicycle Inertia"),
        ],
        "m2": [
            (1, 7, "listen_and_choose", "Choose the Best Response"),
            (8, 9, "conversation", "Laptop Repair"),
            (10, 11, "conversation", "Theater Ticket"),
            (12, 13, "announcement", "Photography Contest"),
            (14, 15, "announcement", "Community Service Club"),
        ],
    },
    "BLOCKED_LISTENING": set(),
    "LISTENING_OPTION_OVERRIDES": {
        ("m1", 1): ["They're not in this section.", "Yes, she prefers fiction.", "The Second World War.", "I'm in the library."],
        ("m1", 2): ["There's a good Thai restaurant near campus.", "I had to eat my lunch during class.", "I haven't eaten there.", "I had leftovers for dinner yesterday."],
        ("m1", 3): ["The membership dues.", "The auditorium on the second floor.", "Last night it rained a lot.", "At least five said they would come."],
        ("m1", 4): ["What size did you buy?", "It was a good-looking design.", "I'll give him the list of what we need.", "This year it starts earlier than usual."],
        ("m1", 5): ["Yes, sometimes I do.", "You should update it before you run into problems.", "The new version has been out for just a month or so I think.", "I'm having trouble getting used to the new one, honestly."],
        ("m1", 6): ["Two blocks over, why?", "It's on campus.", "I move in next week.", "I'll give them a call."],
        ("m1", 7): ["I left my yoga mat in the car.", "I downloaded a fitness app.", "I look forward to going to all of the classes now.", "They make delicious health shakes at the gym cafe."],
        ("m1", 8): ["It's a device that runs on solar power.", "Yes, they usually go out to eat.", "I thought it was a powerful speech.", "It looks like the streetlights outside the dorm are still on."],
        ("m1", 9): ["No, I don't mind if you borrow it.", "They purchased the new printer last week.", "We should receive our grades tomorrow.", "Yes, it was very insightful."],
        ("m1", 10): ["The pictures came out quite well.", "Yes, I'm really excited.", "I worked all last week.", "No, I prefer natural flavors."],
        ("m1", 11): ["Yes, I think it is.", "A very noisy concert.", "Sure, sorry about that.", "No, I'm not going to return it."],
        ("m1", 12): ["Sure. I'd be happy to.", "No, I don't need any help.", "It's incomplete.", "I'll ask you some other time."],
        ("m2", 1): ["In fifteen minutes.", "I really like these actors.", "You should buy tickets for Sunday.", "It's an action film."],
        ("m2", 5): ["Early Wednesday morning.", "In the study abroad office.", "A few miles away.", "All students must attend."],
        ("m1", 13): ["A price increase", "A newspaper club meeting", "A new dormitory building", "A new housing director"],
        ("m1", 14): ["Speak with a university official", "Make a payment", "Read a newspaper article", "Find off-campus housing"],
        ("m1", 15): ["The location of a new park", "Their favorite types of music", "Their plans to attend an event", "The best places to listen to music"],
        ("m1", 16): ["He is worried that he might get cold.", "He thinks the tickets are too expensive.", "He would like a seat close to the stage.", "He will sit in the grass with the woman's friends."],
        ("m1", 17): ["To provide a reminder", "To cancel an appointment", "To review a work schedule", "To discuss a job opportunity"],
        ("m1", 18): ["To confirm a request", "To suggest an alternative", "To schedule an interview", "To clarify a misunderstanding"],
        ("m1", 19): ["It aims to reduce the number of student events.", "It is designed to ensure proper event planning.", "It will be enforced starting next semester.", "It was implemented because of budget cuts."],
        ("m1", 20): ["They were sometimes submitted for approval at the last minute.", "They were often canceled because of a lack of proper planning.", "They did not involve the Student Affairs Office.", "They usually created extra work for student clubs."],
        ("m1", 21): ["It has been open for many years.", "It was started by a fashion design student at the university.", "It targets a narrow market.", "It is moving to a new location."],
        ("m1", 22): ["To purchase young adult clothing", "To view a new logo", "To learn about a contest", "To provide some feedback"],
        ("m1", 23): ["To ask for volunteers", "To give information about a museum's history", "To explain the plan for a tour", "To request donations"],
        ("m1", 24): ["Take students to the next floor", "Discuss an artist", "Collect feedback from visitors", "Hand out some printed information"],
        ("m1", 25): ["The ways that the scarlet badis male defends itself against larger fish", "The characteristics of scarlet badis males in captive environments", "The ways that scarlet badis choose their territories", "The breeding behaviors of male and female scarlet badis"],
        ("m1", 26): ["They are not usually violent toward each other.", "They may be hunted by land animals.", "They swim at a slower speed than those in aquariums.", "They have a brighter color than those in aquariums."],
        ("m1", 27): ["They should be the same plants as those found in streams in India.", "They should be orange-red to match male scarlet badis.", "They help keep male scarlet badis separate from one another.", "They are the primary food source for the scarlet badis."],
        ("m1", 28): ["They may dance during the breeding season.", "They sometimes look very similar to males.", "They usually have orange-red coloring.", "They can be aggressive toward males."],
        ("m1", 29): ["To show how easy it is to conduct a physics experiment", "To describe the discovery of a law of physics", "To explain two physical forces acting on a moving bicycle", "To offer reasons why many physicists like bicycle riding"],
        ("m1", 30): ["It is more complicated than it seems.", "It is the hardest skill to learn.", "It is easier to turn right than left.", "It is important to go slowly."],
        ("m1", 31): ["Go faster", "Avoid falling down", "See more clearly around corners", "Prevent uneven wear on the wheels"],
        ("m1", 32): ["Slide out significantly on some turns in the road", "Keep their bikes relatively upright at high speeds", "Shift their weight just enough to work against inertia", "Change the direction of only their front wheel"],
        ("m2", 2): ["It lasts four hours.", "Later this afternoon.", "Yes, I already booked my session.", "It's open to all students."],
        ("m2", 3): ["It starts at noon sharp.", "Professor Clark will give it.", "It's on the topic of biology.", "It should be an hour long."],
        ("m2", 4): ["Sure, I have time right now.", "Maybe tomorrow will work.", "I will be available all day.", "I was on vacation."],
        ("m2", 6): ["I was too busy to get it done.", "The plants are beautiful.", "It starts at four p.m.", "I'd better hurry to class."],
        ("m2", 7): ["There are drums and saxophones on display.", "Yes, my family enjoyed the dinosaur exhibit.", "Yesterday, at three p.m.", "The scalpel is an important medical instrument."],
        ("m2", 8): ["To a computer repair shop", "To the campus technology center", "To a restaurant down the street", "To a sales center"],
        ("m2", 9): ["Do some work", "Buy a laptop", "Make an appointment", "Share some information"],
        ("m2", 10): ["Why she has been very busy", "Why she is interested in a specific theater performance", "Why she would like to invite the man to visit her", "Why she is not planning to see a theater performance"],
        ("m2", 11): ["It might not be very interesting.", "It might be rescheduled for a different day of the week.", "Tickets for it might soon become unavailable.", "Reviews of it might not be very accurate."],
        ("m2", 12): ["Tall city buildings", "A campus picnic", "Flowers in a vase", "Landscapes in nature"],
        ("m2", 13): ["A voting process", "A submission process", "A deadline", "A website address"],
        ("m2", 14): ["They will become shorter.", "They will require students to confirm their attendance in advance.", "They will be held more frequently.", "They will move from an afternoon schedule to an evening schedule."],
        ("m2", 15): ["New volunteer opportunities", "A list of student clubs", "Directions to a local park", "A permission form"],
    },
    "LISTENING_STEM_OVERRIDES": {
        ("m1", 13): "What information did the man just learn about?",
        ("m1", 14): "What is the man planning to do?",
        ("m1", 15): "What are the man and the woman talking about?",
        ("m1", 16): "What does the man imply when he says, \"I'll bring a blanket too\"?",
        ("m1", 17): "Why is the woman calling the man?",
        ("m1", 18): "Why does the man say that he gets off at 3:00?",
        ("m1", 19): "What can be inferred about the new policy?",
        ("m1", 20): "What can be concluded about previously held events?",
        ("m1", 21): "What can be inferred about the business mentioned by the speaker?",
        ("m1", 22): "Why should listeners visit the website?",
        ("m1", 23): "What is the purpose of the announcement?",
        ("m1", 24): "What will the speaker probably do next?",
        ("m1", 25): "What does the speaker mainly discuss?",
        ("m1", 26): "What does the speaker imply about scarlet badis that live in streams?",
        ("m1", 27): "What point does the speaker make about plants in aquariums?",
        ("m1", 28): "What can be inferred about female scarlet badis?",
        ("m1", 29): "What is the purpose of the talk?",
        ("m1", 30): "What does the speaker suggest about turning?",
        ("m1", 31): "What does leaning in help a cyclist to do?",
        ("m1", 32): "What do professional cyclists try to do when turning?",
        ("m2", 8): "Where did the man most likely go?",
        ("m2", 9): "What does the man say that he will do?",
        ("m2", 10): "What is the woman explaining when she mentions her new apartment?",
        ("m2", 11): "What warning does the man give the woman about a theater performance?",
        ("m2", 12): "What would most likely be shown in a photo submitted for the contest?",
        ("m2", 13): "What change does the speaker mention?",
        ("m2", 14): "What does the speaker say about a club's meetings?",
        ("m2", 15): "What will students find in their email?",
    },
    "LISTENING_PAGE_OVERRIDES": {
        **{("m1", number): 14 + number for number in range(1, 13)},
        ("m1", 13): 28, ("m1", 14): 29, ("m1", 15): 31, ("m1", 16): 31,
        ("m1", 17): 33, ("m1", 18): 33, ("m1", 19): 34, ("m1", 20): 35,
        ("m1", 21): 36, ("m1", 22): 36, ("m1", 23): 37, ("m1", 24): 38,
        ("m1", 25): 39, ("m1", 26): 39, ("m1", 27): 40, ("m1", 28): 40,
        ("m1", 29): 41, ("m1", 30): 42, ("m1", 31): 42, ("m1", 32): 43,
        ("m2", 1): 44, ("m2", 2): 45, ("m2", 3): 45, ("m2", 4): 46, ("m2", 5): 46,
        ("m2", 6): 47, ("m2", 7): 48, ("m2", 8): 49, ("m2", 9): 50, ("m2", 10): 52,
        ("m2", 11): 52, ("m2", 12): 53, ("m2", 13): 54, ("m2", 14): 55, ("m2", 15): 55,
    },
    "WRITING_ORDERED": {
        1: "it's the one that has the software that I need for my project.",
        2: "I bought the one that has a built-in charger .",
        3: "Can you tell me whether it will reopen by the end of the month ?",
        4: "are you going to have time to edit the report?",
        5: "I do not usually go to those events .",
        6: "I haven't decided yet , but it does sound interesting",
        7: "I have not completed all the modules yet.",
        8: "Unfortunately, I did not have time for a visit .",
        9: "I worked with a company that aimed to reduce carbon emissions .",
        10: "I haven't checked the final score of the game yet.",
    },
    "WRITING_SENTENCE_ITEMS": {
        1: ("Why are you using that laptop?", ["project.", "it's", "the", "my", "software", "that", "I", "need", "for", "one", "that", "has", "the"]),
        2: ("Which backpack did you buy?", ["I", "bought", "the", "one", "charger", "that", "built-in", "a", "what", "has"]),
        3: ("The library will be closed for renovations next week.", ["the", "month", "of", "will", "reopen", "by", "the", "end", "whether", "it", "tell", "me"]),
        4: ("I have to finish this report by tomorrow.", ["the", "report?", "are", "edit", "to", "time", "you", "have", "going", "to"]),
        5: ("Are you attending the networking event tonight?", ["usually", "am", "not", "to", "those", "do", "events", "go"]),
        6: ("Have you thought about joining the debate club?", ["decided", "yet", "interesting", "does", "sound", "but", "it", "I", "haven't"]),
        7: ("Are you finished with the training course?", ["I", "not", "completed", "have", "all", "never", "the", "modules", "yet."]),
        8: ("Did you go to the library today?", ["a", "visit", "did", "had", "time", "I", "have", "not", "for"]),
        9: ("Which internship did you have during the summer?", ["aimed", "to", "reduce", "carbon", "emissions", "I", "that", "with", "a", "company"]),
        10: ("Who won the university's cricket match last night?", ["the", "I", "checked", "score", "final", "haven't", "of", "the", "game"]),
    },
    "WRITING_MANUAL_PROMPTS": {
        11: (
            "You and your friend, Jasmine, are planning to host a fundraising event for a local children's hospital. "
            "You have some ideas for activities and entertainment to include in the event, but you need Jasmine's input to finalize the plans. "
            "You also want to discuss the best time to meet and organize the details. "
            "Write an email to Jasmine. Describe the ideas you have for the fundraising event, explain why you think these activities will be successful, and suggest a time to meet and discuss the plans in more detail. "
            "To: Jasmine. Subject: Fundraising event planning. Write as much as you can and in complete sentences."
        ),
        12: (
            "Your professor is teaching a class on marketing. Write a post responding to the professor's question. "
            "Dr. Gupta asks: We've been discussing various strategies to build brand loyalty. One effective strategy is offering personalized services and products to customers, which can make customers feel valued and understood. Do you think personalization is the key to building strong brand loyalty? Why or why not? "
            "Claire believes personalization is essential because tailored services and products make customers feel valued and more likely to stick with the brand. "
            "Andrew argues that personalization is important but not the only factor, because customer service, product quality and pricing also play a significant role. "
            "Express and support your opinion, contribute to the discussion in your own words, and write at least 100 words."
        ),
    },
    "SPEAKING_REPEAT_AUDIO_TRANSCRIPT": [
        "Check your inbox for new messages.",
        "Select Compose to write your e-mail.",
        "Select from your contacts list to add recipients to your note.",
        "Review sent items to confirm your messages were delivered.",
        "Use folders to organize your correspondence efficiently.",
        "Set up a few topical filters to manage incoming communications.",
        "To be safe, remember to log out to keep your electronic mail secure in our system.",
    ],
    "SPEAKING_INTERVIEW_AUDIO_TRANSCRIPT": [
        "First, do you think exercising daily is important for good health? Why or why not?",
        "Imagine you are going to recommend or create an exercise program for a friend or family member who does not currently exercise. What kind of exercise or fitness routine would you recommend? Why?",
        "For that same friend or family member, what do you think might challenge them the most about a regular exercise program? How would you help them through this challenge?",
        "Some people believe that it is important to have some sort of reward after a good week of exercising. What do you think would be a good reward for the program you created and why?",
    ],
    "SPEAKING_PAGES": {1: 65, 2: 66, 3: 66, 4: 67, 5: 67, 6: 68, 7: 68, 8: 69, 9: 70, 10: 71, 11: 71},
    "SPEAKING_CONTENT_STATUS": "reviewed_repair",
    "BLOCKED_REASON_BY_ITEM": {
        ("reading", "m1", 24): "Answer key conflicts with visible source semantics; exclude from auto-grading until the source or key is corrected.",
        ("listening", "m2", 1): "Source paper/OCR does not provide four visible answer options.",
        ("listening", "m2", 5): "Source paper/OCR does not provide four visible answer options.",
    },
}

A27_EXAM_CONFIG: dict[str, Any] = {
    "EXAM_KEY": "2026-01-27_A",
    "PROGRESS_KEY": "2026-01-27-A",
    "EXAM_ID": "toefl:2026-01-27-a",
    "SOURCE_FOLDER": "1.27新托福A卷",
    "PAPER": "1.27新托福A卷/新托福2026真题04.pdf",
    "ANSWER_PDF": "1.27新托福A卷/参考答案-新托福2026真题04.pdf",
    "TRANSCRIPT_PDF": "1.27新托福A卷/听力原文-新托福2026真题04.pdf",
    "LISTENING_M1_AUDIO": "1.27新托福A卷/新托福2026真题04ListeningModule1.mp3",
    "LISTENING_M2_AUDIO": "1.27新托福A卷/新托福2026真题04ListeningModule2.mp3",
    "SPEAKING_AUDIO": "1.27新托福A卷/新托福2026真题04speakingModule1.mp3",
    "READING_CACHE": "tmp/pdfs/reading_structured/extracted/04_2026_01_27_A.json",
    "READING_EXTRA_SOURCE_PATHS": [
        "tmp/pdfs/reading_structured/repairs/04_2026_01_27_A_003.json",
        "tmp/pdfs/reading_structured/repairs/04_2026_01_27_A_018.json",
    ],
    "SPEAKING_TRANSCRIPT_JSON": "新托福分科刷题材料/整理输出/口语转写_修订版/transcripts/2026-01-27_A_part1.json",
    "LISTENING_SECTION_HEADING": "## 2026-01-27 A卷",
    "LISTENING_SECTION_STOP_MARKER": "### 来源：1.27新托福A卷/听力原文-新托福2026真题04.pdf",
    "LISTENING_PROMPT_UPPER": {"m1": 12, "m2": 3},
    "EXAM_TITLE": "2026-01-27 TOEFL Real Exam A",
    "EXAM_DATE": "2026-01-27",
    "EXAM_VARIANT": "A",
    "PROGRESS_NOTES": "120 atomic questions rebuilt from source; Listening M1 Q1/M1 Q2/M2 Q1 options and 12 OCR-polluted option tails were visually recovered from rendered source pages.",
    "BLOCKING_REASONS": [],
    "LATEST_BLOCKER_TEXT": "No unresolved source-content blockers; subject review is still required before release.",
    "QA_CHECK_SPECS": [
        {"id": "atomic-count", "status": "pass", "detail": "120 expected atomic questions are represented."},
        {"id": "answer-separation", "status": "pending", "detail": "Validator will check public content for answer leakage."},
        {"id": "reading-source", "status": "pass", "detail": "Reading OCR numbering issues were repaired from rendered source pages; no reading items are blocked."},
        {"id": "listening-source", "status": "pass", "detail": "Listening M1 Q1/M1 Q2/M2 Q1 options and 12 OCR-polluted option tails were visually recovered from rendered source pages."},
        {"id": "media", "status": "pass", "detail": "Listening and speaking audio files exist and have readable ffprobe durations."},
        {"id": "speaking-source", "status": "pass", "detail": "Speaking audio transcript aligns with the woodworking and childhood-education scenes in the source."},
        {"id": "inline-reading-contract", "status": "pass", "detail": "Complete-the-words groups define inline token rendering without public answer fields."},
    ],
    "READING_ANSWERS": {
        "m1": [
            "ch", "ists", "ny", "f", "r", "ich", "ally", "all", "e", "th",
            "ation", "he", "iated", "ace", "nd", "uency", "ions", "ke", "ve", "able",
            "A", "A", "B", "A", "B", "B", "D", "B", "C", "D", "C", "D", "B", "B", "C",
        ],
        "m2": ["s", "own", "is", "ages", "he", "ean", "ich", "lously", "lines", "ected", "D", "A", "B", "B", "D"],
    },
    "FILL_PREFIXES": {
        "m1": ["Ea", "cons", "ti", "o", "wate", "wh", "usu", "sm", "b", "wi", "innov", "t", "assoc", "sp", "a", "freq", "miss", "li", "ha", "reus"],
        "m2": ["i", "kn", "h", "voy", "t", "Oc", "wh", "meticu", "coast", "coll"],
    },
    "FILL_DISPLAY": {
        "m1_01": (
            "Although there are many different types of clouds, they are all composed of the same basic substance. "
            "{q01:Ea} cloud {q02:cons} of {q03:ti} drops {q04:o} {q05:wate} or ice, {q06:wh} are {q07:usu} too {q08:sm} to {q09:b} seen {q10:wi} the naked eye. "
            "These particles cluster together and form an invisible gas known as water vapor. Some of this vapor attaches to microscopic bits of dust or ice floating in the atmosphere. "
            "When enough of these elements combine, they create a visible cloud."
        ),
        "m1_02": (
            "Space exploration has advanced significantly with the development of rockets that can be reused. "
            "Traditional rockets were discarded after a single use, but new designs allow them to return to Earth and be refurbished for multiple missions. "
            "This {q11:innov} reduces {q12:t} cost {q13:assoc} with {q14:sp} launches {q15:a} increases {q16:freq} of {q17:miss}. "
            "Companies {q18:li} SpaceX {q19:ha} pioneered {q20:reus} rocket technology, successfully launching and landing rockets. "
            "These advancements pave the way for more ambitious projects, including potential manned missions to Mars and beyond."
        ),
        "m2_01": (
            "James Cook was a British naval officer, explorer, and cartographer born in 1728. "
            "He {q01:i} best {q02:kn} for {q03:h} three {q04:voy} across {q05:t} Pacific {q06:Oc}, during {q07:wh} he {q08:meticu} mapped {q09:coast} and {q10:coll} data on astronomy, natural history, and oceanography. "
            "Cook is the first European to circumnavigate New Zealand and make contact with the Hawaiian islands. "
            "He is also notable for implementing health measures aboard his ships, such as dietary changes to prevent the disease scurvy."
        ),
    },
    "READING_GROUPS": {
        "m1": [
            (1, 10, "complete_words", "Cloud Formation"),
            (11, 20, "complete_words", "Reusable Rockets"),
            (21, 22, "read_in_daily_life", "Dorm Safety Drill"),
            (23, 25, "notice", "Woods Science Library Renovation"),
            (26, 30, "academic_passage", "Engineering Earth's Climate"),
            (31, 35, "academic_passage", "Harmonic Analysis"),
        ],
        "m2": [
            (1, 10, "complete_words", "James Cook"),
            (11, 15, "academic_passage", "Bird Migration"),
        ],
    },
    "READING_MC_OVERRIDES": {
        ("m1", 21): {
            "stem": "What is the main purpose of the notice?",
            "options": ["To announce a safety procedure", "To request feedback", "To advertise a new service", "To explain renovations"],
            "confidence": "reviewed_repair",
            "extra_sources": ["tmp/pdfs/reading_structured/repairs/04_2026_01_27_A_003.json"],
        },
        ("m1", 23): {
            "stem": "What can be inferred about the renovation?",
            "options": ["It will take more than six weeks", "It is necessary for expansion", "It will enhance the digital resources", "It is funded by the community center"],
            "confidence": "reviewed_repair",
        },
        ("m1", 24): {
            "stem": "Where should patrons bring back their borrowed books during the renovation?",
            "options": ["The community center", "The special meeting rooms", "The library staff desk", "The regular drop-off location"],
            "confidence": "reviewed_repair",
        },
        ("m1", 26): {
            "stem": "Which of the following is true of Earth systems engineering and management (ESEM)?",
            "options": ["It finds solutions for problems by allowing natural processes to work themselves out.", "It uses the resources of multiple disciplines to accomplish its goals.", "It focuses exclusively on counteracting global warming.", "It is also known as geoengineering."],
            "confidence": "source_exact",
        },
        ("m1", 27): {
            "stem": "What is the basic difference between the two categories of geoengineering techniques?",
            "options": ["SRM merely manages solar radiation, while CDR removes it altogether.", "SRM injects aerosols into the stratosphere, while CDR deploys reflective mirrors.", "SRM lowers greenhouse gas concentrations, while CDR directly captures CO2.", "SRM reduces the effects of global warming, while CDR reduces its causes."],
            "confidence": "visually_recovered",
        },
        ("m1", 28): {
            "stem": 'The word "feasibility" in the passage is closest in meaning to',
            "options": ["cost", "workability", "specialty", "risk"],
            "confidence": "visually_recovered",
        },
        ("m1", 29): {
            "stem": "What is one ongoing question raised by geoengineering?",
            "options": ["What types of collaboration are required in order to develop safe strategies", "Whether existing experimental techniques can be sustained", "Who bears responsibility for implementing changes", "Whether it can be integrated with environmental management"],
            "confidence": "visually_recovered",
        },
        ("m1", 30): {
            "stem": "Careful consideration is needed to assess the long-term impacts. Where would the sentence best fit? Select a location to add the sentence in the passage.",
            "options": ["Location A", "Location B", "Location C", "Location D"],
            "confidence": "visually_recovered",
        },
        ("m1", 32): {
            "stem": "All of the following are mentioned about harmonic analysis EXCEPT:",
            "options": ["It involves the way functions and signals are represented", "It has practical uses in several areas", "It can reveal unseen structures in complex signals", "It is more effective in music than in finance"],
            "confidence": "source_exact",
        },
        ("m1", 33): {
            "stem": "In which of the following ways does the Fourier transform benefit signal processing?",
            "options": ["By making signals travel far", "By making signals clearer", "By protecting signals from noise", "By increasing the frequency of signals"],
            "confidence": "reviewed_repair",
        },
        ("m1", 35): {
            "stem": "They enable the reduction of file sizes without significant loss of quality. Where would the sentence best fit? Select a location to add the sentence in the passage.",
            "options": ["Location A", "Location B", "Location C", "Location D"],
            "confidence": "visually_recovered",
        },
        ("m2", 11): {
            "stem": "The passage implies that bird migration began when",
            "options": ["wintering grounds were closer to breeding grounds than they are now", "areas suitable for breeding were smaller than they are now", "there were many more birds than there are now", "climates were generally much colder than they are now"],
            "confidence": "reviewed_repair",
            "extra_sources": ["tmp/pdfs/reading_structured/repairs/04_2026_01_27_A_018.json"],
        },
        ("m2", 13): {
            "stem": "The passage supports all of the following statements about Arctic terns EXCEPT:",
            "options": ["They take different migration routes depending on resource availability", "They migrate over longer distances than all other birds do", "They spend much of their lives in regions around Earth's poles", "They eat mostly small animals living in sea water"],
            "confidence": "reviewed_repair",
        },
        ("m2", 14): {
            "stem": "Why does the passage provide information about rock ptarmigans?",
            "options": ["To emphasize the usefulness of snow burrows in their habitat", "To contrast their behavior to that of Arctic terns", "To show that birch and willow trees provide food to both migratory and sedentary birds", "To provide another example of migratory birds"],
            "confidence": "reviewed_repair",
        },
    },
    "BLOCKED_READING": set(),
    "GRADING_BLOCKED_READING": set(),
    "READING_PAGE_OVERRIDES": {
        **{("m1", number): 2 for number in range(1, 21)},
        **{("m1", number): 3 for number in range(21, 23)},
        **{("m1", number): 4 for number in range(23, 26)},
        **{("m1", number): 5 for number in range(26, 29)},
        **{("m1", number): 6 for number in range(29, 32)},
        **{("m1", number): 7 for number in range(32, 35)},
        ("m1", 35): 8,
        **{("m2", number): 9 for number in range(1, 13)},
        **{("m2", number): 10 for number in range(13, 16)},
    },
    "LISTENING_ANSWERS": {
        "m1": ["A", "C", "C", "D", "C", "D", "D", "A", "C", "B", "B", "A", "C", "B", "C", "B", "B", "C", "D", "A", "D", "A", "C", "D", "D", "A", "B", "B", "C", "B", "A", "B"],
        "m2": ["B", "D", "B", "B", "C", "C", "A", "D", "D", "A", "C", "B", "B", "B", "A"],
    },
    "LISTENING_GROUPS": {
        "m1": [
            (1, 12, "listen_and_choose", "Choose the Best Response"),
            (13, 14, "conversation", "Roommate Search"),
            (15, 16, "conversation", "Conference Flight"),
            (17, 18, "conversation", "Restaurant Recommendation"),
            (19, 20, "announcement", "Club Attendance Policy"),
            (21, 22, "announcement", "Fitness Center Closing"),
            (23, 24, "announcement", "Graduation Workshop Requirement"),
            (25, 28, "lecture", "Sleep and Cognitive Function"),
            (29, 32, "lecture", "Positive Reinforcement"),
        ],
        "m2": [
            (1, 3, "listen_and_choose", "Choose the Best Response"),
            (4, 5, "conversation", "Printer Problem"),
            (6, 7, "conversation", "Resume for Interview"),
            (8, 11, "lecture", "The Renaissance"),
            (12, 15, "lecture", "Urbanization and Sustainable Planning"),
        ],
    },
    "BLOCKED_LISTENING": set(),
    "LISTENING_OPTION_OVERRIDES": {
        ("m1", 1): ["I'll need to confirm that.", "Sure, next time will do.", "Deadlines are crucial.", "Probably in the atrium."],
        ("m1", 2): ["Yes, they're about to graduate.", "No, it's not required.", "It's happening soon.", "Annie is in her dorm room."],
        ("m1", 3): ["Let's all wear team shirts.", "The outing will take place next weekend.", "Should we vote on options?", "It's for the team's anniversary."],
        ("m1", 4): ["It takes over an hour to complete.", "I already filled it out.", "Tomorrow morning is the deadline.", "Through the hiring website."],
        ("m1", 5): ["He works at a call center.", "Here's a bus token.", "The one that leaves from Maple Street Station.", "The last stop before Springfield."],
        ("m1", 6): ["The student union opens at 8 a.m.", "Try knocking louder.", "The house number is on the door.", "I don't have a key."],
        ("m1", 8): ["I believe it's Dr. Thomas.", "Dr. Yoshida is on the phone.", "It was informative.", "We can go today."],
        ("m1", 9): ["I've already eaten.", "Because calculus class was canceled.", "Let me find it first.", "Is that what it looks like?"],
        ("m1", 10): ["Neil wrote a book.", "Professor Cameron did.", "I didn't see that book.", "Let's check for discounts."],
        ("m1", 12): ["Through the course's website.", "That form is outdated.", "A small registration fee.", "Today if you can."],
        ("m1", 15): ["She was attending a conference.", "She has been too busy at work.", "She is waiting to get a better deal.", "She thought the man was going to book the flight for her."],
        ("m1", 16): ["She is going to finalize a contract.", "She cannot afford to miss the conference.", "The professors are coming from overseas.", "The professors will likely not understand her research."],
        ("m1", 17): ["A place to have a business meeting", "A place to celebrate a special occasion", "A new recipe to try at home", "A gift for his advisor"],
        ("m1", 18): ["Order a chicken dish", "Look for a different restaurant", "Make a reservation soon", "Cook a meal at home"],
        ("m1", 20): ["Loss of club membership", "A fine of 75 dollars", "The need to attend a special meeting", "Complaints from other club members"],
        ("m1", 24): ["Preparing a sample resumé", "Visiting the career center", "Scheduling an interview", "Registering early for workshops"],
        ("m1", 26): ["It occurs mainly during deep sleep stages.", "It affects problem-solving abilities.", "It happens primarily in people with sleep disorders.", "It allows the brain to process emotional experiences."],
        ("m1", 27): ["To highlight common symptoms of stress", "To point out the impact of sleep deprivation on emotional regulation", "To explain the effects of sleep hygiene on problem-solving abilities", "To illustrate the various stages of sleep"],
        ("m1", 29): ["The difficulty of setting goals for animals", "The relationship between motivation and long-term behavior", "The application of a psychological theory about rewards", "The guidelines for identifying problematic behavior"],
        ("m1", 32): ["To advocate for gentle parenting techniques", "To warn against reinforcing unwanted behavior", "To explain how small actions lead to big changes", "To describe the consequences of inconsistent feedback"],
        ("m2", 1): ["The beach is crowded.", "It's a short drive away.", "I love swimming in the ocean.", "I spent the day there yesterday."],
        ("m2", 2): ["Will it rain on those days?", "I'm eating too.", "Yes, yesterday.", "Are you sure?"],
        ("m2", 3): ["This is the main entrance.", "The hours are posted on their website.", "I should go home to study for an exam.", "It's closed tomorrow for cleaning."],
        ("m2", 15): ["It has reduced the city's reliance on imported food.", "It has generated additional revenue for the city.", "It has created many additional jobs for city residents.", "It allows residents to grow their own produce."],
    },
    "LISTENING_PAGE_OVERRIDES": {
        ("m1", 1): 12, ("m1", 2): 13, ("m1", 3): 14, ("m1", 4): 14,
        ("m1", 5): 15, ("m1", 6): 16, ("m1", 7): 17, ("m1", 8): 18,
        ("m1", 9): 19, ("m1", 10): 20, ("m1", 11): 21, ("m1", 12): 22,
        ("m1", 13): 24, ("m1", 14): 24, ("m1", 15): 26, ("m1", 16): 27,
        ("m1", 17): 29, ("m1", 18): 29, ("m1", 19): 30, ("m1", 20): 31,
        ("m1", 21): 32, ("m1", 22): 32, ("m1", 23): 33, ("m1", 24): 34,
        ("m1", 25): 35, ("m1", 26): 35, ("m1", 27): 36, ("m1", 28): 36,
        ("m1", 29): 37, ("m1", 30): 38, ("m1", 31): 38, ("m1", 32): 39,
        ("m2", 1): 40, ("m2", 2): 41, ("m2", 3): 42, ("m2", 4): 44,
        ("m2", 5): 44, ("m2", 6): 46, ("m2", 7): 46, ("m2", 8): 47,
        ("m2", 9): 48, ("m2", 10): 48, ("m2", 11): 49, ("m2", 12): 50,
        ("m2", 13): 50, ("m2", 14): 51, ("m2", 15): 51,
    },
    "WRITING_ORDERED": {
        1: "Unfortunately, I never had a chance to read the book .",
        2: "Sorry, I have not had a chance to begin reading it yet.",
        3: "I'm trying to finish a report before the deadline .",
        4: "the options were not very appealing to me.",
        5: "I am not available during those dates.",
        6: "I do not remember where I left my backpack .",
        7: "No, I haven't had a chance to buy it .",
        8: "He wanted to know how I did my research .",
        9: "there was a huge traffic on the highway .",
        10: "She wanted to find out what city Konrad is moving to.",
    },
    "WRITING_SENTENCE_ITEMS": {
        1: ("Are you going to the book club meeting tonight?", ["never", "a", "chance", "not", "had", "the", "book", "to", "read", "I"]),
        2: ("Did you finish the book I lent you?", ["not", "reading", "a", "chance", "have", "had", "does", "it", "to", "begin"]),
        3: ("Why aren't you joining us for lunch?", ["trying", "before", "the", "deadline", "a", "report", "I'm", "to", "finish"]),
        4: ("Did you like the new offerings in the university cafeteria?", ["the", "very", "were", "not", "options", "appealing"]),
        5: ("Will you be attending the conference next week?", ["those", "will", "available", "I", "not", "am", "during"]),
        6: ("Where did you leave your backpack?", ["when", "my", "do", "not", "remember", "where", "left", "backpack"]),
        7: ("Did you get the newly updated textbook for class?", ["buy", "I", "haven't", "it", "yet", "to", "a", "chance", "had"]),
        8: ("What did the professor ask about your thesis?", ["did", "how", "research", "my", "I", "to", "know", "wanted"]),
        9: ("Why were you late for the freshman orientation?", ["huge", "on", "traffic", "there", "was", "a", "the", "highway"]),
        10: ("What did Jee-Wha ask you after class?", ["to", "find", "out", "there", "Konrad", "is", "what", "moving", "city"]),
    },
    "WRITING_FIXED_TEXT": {
        1: {"prefix": "Unfortunately,"},
        2: {"prefix": "Sorry, I", "suffix": "yet."},
        4: {"suffix": "to me."},
        5: {"suffix": "dates."},
        7: {"prefix": "No,"},
        8: {"prefix": "He"},
        10: {"prefix": "She wanted"},
    },
    "WRITING_MANUAL_PROMPTS": {
        11: (
            "Your professor, Dr. Smith, recently assigned a group project due in two weeks. "
            "You are frustrated because not all of your group members are contributing equally to the project. "
            "Write an email to Dr. Smith. Describe the issue you are facing with your group members, describe your specific contribution to the project, and explain why you and the group have been unable to address this issue. "
            "To: Dr. Smith. Subject: Issues with group project. Write as much as you can and in complete sentences."
        ),
        12: (
            "Your professor is teaching a class on economics. Write a post responding to the professor's question. "
            "Dr. Gupta asks: We often discuss the impact of government intervention in the economy. Some argue that government regulations and policies can improve economic stability and protect consumers. Others believe that too much intervention can stifle innovation and lead to inefficiencies. What do you think is the most effective role of government in the economy? "
            "Claire argues that government intervention is important for ensuring economic stability and protecting consumers. Andrew argues that too much government intervention can hinder economic growth and innovation. "
            "Express and support your opinion, contribute to the discussion in your own words, and write at least 100 words."
        ),
    },
    "WRITING_PAGES": {1: 52, 2: 52, 3: 53, 4: 53, 5: 54, 6: 54, 7: 55, 8: 55, 9: 56, 10: 56, 11: 57, 12: 58},
    "SPEAKING_REPEAT_AUDIO_TRANSCRIPT": [
        "Welcome to the wood shop.",
        "This tool box contains everything you should need.",
        "You will learn to use your saw in our classes.",
        "Your screwdriver can be used with all of our carpentry machines.",
        "All wood will need to be smooth, so use the sand paper provided.",
        "Use only what is needed so that your supplies last all quarter.",
        "Before you leave the class room, be sure to put all your tools back into the tool box.",
    ],
    "SPEAKING_INTERVIEW_AUDIO_TRANSCRIPT": [
        "First, did you enjoy your school experience as a child?",
        "Tell me about a school project or activity you participated in. What made that project or activity special?",
        "Tell me a little about the technology you used during your childhood education. Do you feel like that technology prepared you for life after school? Why or why not?",
        "Some people believe that the current education system needs significant changes to better prepare children for the future, focusing more on skills like problem solving and teamwork, instead of mainly teaching facts. Do you agree or disagree with this viewpoint? Why?",
    ],
    "SPEAKING_PAGES": {1: 60, 2: 61, 3: 61, 4: 62, 5: 62, 6: 63, 7: 63, 8: 65, 9: 65, 10: 66, 11: 66},
    "SPEAKING_CONTENT_STATUS": "reviewed_repair",
    "BLOCKED_REASON_BY_ITEM": {
        ("listening", "m1", 1): "Source paper/OCR does not provide four visible answer options.",
        ("listening", "m1", 2): "Source paper/OCR does not provide four visible answer options.",
        ("listening", "m2", 1): "Source paper/OCR does not provide four visible answer options.",
    },
}


A27_B_EXAM_CONFIG: dict[str, Any] = {
    "EXAM_KEY": "2026-01-27_B",
    "PROGRESS_KEY": "2026-01-27-B",
    "EXAM_ID": "toefl:2026-01-27-b",
    "SOURCE_FOLDER": "1.27新托福B卷",
    "PAPER": "1.27新托福B卷/2026新托福真题01.pdf",
    "ANSWER_PDF": "1.27新托福B卷/参考答案-2026新托福真题02.pdf",
    "TRANSCRIPT_PDF": "1.27新托福B卷/听力原文-2026新托福真题02.pdf",
    "LISTENING_M1_AUDIO": "1.27新托福B卷/2026新托福真题02ListeningModule1.mp3",
    "LISTENING_M2_AUDIO": "1.27新托福B卷/2026新托福真题02ListeningModule2.mp3",
    "SPEAKING_AUDIO": "1.27新托福B卷/2026新托福真题02SpeakingModule1.mp3",
    "READING_CACHE": "tmp/pdfs/reading_structured/extracted/05_2026_01_27_B.json",
    "READING_EXTRA_SOURCE_PATHS": [
        "tmp/pdfs/reading_structured/repairs/05_2026_01_27_B_004.json",
        "tmp/pdfs/reading_structured/repairs/05_2026_01_27_B_018.json",
    ],
    "SPEAKING_TRANSCRIPT_JSON": "新托福分科刷题材料/整理输出/口语转写_修订版/transcripts/2026-01-27_B_part1.json",
    "LISTENING_SECTION_HEADING": "## 2026-01-27 B卷",
    "LISTENING_SECTION_STOP_MARKER": "### 来源：1.27新托福B卷/听力原文-2026新托福真题02.pdf",
    "LISTENING_PROMPT_UPPER": {"m1": 12, "m2": 3},
    "EXAM_TITLE": "2026-01-27 TOEFL Real Exam B",
    "EXAM_DATE": "2026-01-27",
    "EXAM_VARIANT": "B",
    "PROGRESS_NOTES": "120 atomic questions rebuilt from source; Listening M1 Q25 remains blocked because the source OCR/PDF exposes only the lecture-intro screen, not the question/options.",
    "BLOCKING_REASONS": [
        "Listening M1 Q25 has an answer-key entry but no recoverable question stem or four options in the source paper/OCR/web extraction.",
    ],
    "LATEST_BLOCKER_TEXT": "Listening M1 Q25 lacks a visible source question stem and options.",
    "QA_CHECK_SPECS": [
        {"id": "atomic-count", "status": "pass", "detail": "120 expected atomic questions are represented."},
        {"id": "answer-separation", "status": "pending", "detail": "Validator will check public content for answer leakage."},
        {"id": "reading-source", "status": "pass", "detail": "Reading OCR navigation artifacts were repaired from rendered source text and repair crops; no reading items are blocked."},
        {"id": "listening-source", "status": "blocked", "detail": "Listening M1 Q25 exposes only the political-science podcast intro screen; its question/options are absent from source OCR and source-root HTML."},
        {"id": "media", "status": "pass", "detail": "Listening and speaking audio files exist and have readable ffprobe durations."},
        {"id": "speaking-source", "status": "pass", "detail": "Speaking audio transcript aligns with the university open-house and education-experiences scenes in the source."},
        {"id": "inline-reading-contract", "status": "pass", "detail": "Complete-the-words groups define inline token rendering without public answer fields."},
    ],
    "READING_M2_START_PAGE": 9,
    "READING_ANSWERS": {
        "m1": [
            "re", "re", "or", "duct", "ay", "t", "nsive", "ease", "rsely", "ess",
            "ains", "ageous", "ease", "uency", "ation", "apt", "eir", "ich", "o", "rsity",
            "C", "A", "C", "C", "A", "A", "B", "D", "C", "C", "C", "A", "A", "C", "D",
        ],
        "m2": ["ern", "as", "und", "y", "ho", "ew", "at", "t", "or", "o", "A", "C", "C", "D", "A"],
    },
    "FILL_PREFIXES": {
        "m1": ["the", "mo", "f", "pro", "m", "i", "expe", "incr", "Conve", "exc", "expl", "advant", "incr", "freq", "popul", "ad", "th", "wh", "t", "dive"],
        "m2": ["mod", "w", "aro", "b", "w", "n", "th", "i", "f", "t"],
    },
    "FILL_DISPLAY": {
        "m1_01": (
            "Supply and demand are fundamental concepts in economics because they determine the price and availability of goods or services. "
            "When {q01:the} is {q02:mo} demand {q03:f} a {q04:pro}, suppliers {q05:m} make {q06:i} more {q07:expe} to {q08:incr} profits. "
            "{q09:Conve}, an {q10:exc} supply can lead to price reductions. Market equilibrium occurs when supply matches demand, resulting in stable prices. "
            "The real world, however, is rarely as simple as this. Various factors influence these dynamics, including consumer preferences, production costs, and external events."
        ),
        "m1_02": (
            "Fossils provide invaluable evidence of evolutionary history, documenting species that lived millions of years ago. "
            "Paleontologists examine these remains to understand how organisms have changed over time. Natural selection {q11:expl} how {q12:advant} traits {q13:incr} in {q14:freq} in a {q15:popul}. "
            "Species {q16:ad} to {q17:th} environments, {q18:wh} leads {q19:t} incredible {q20:dive} observed in the biological world today through the mechanism of natural selection. "
            "The ongoing study of evolution continues to reveal how life on Earth has developed and diversified."
        ),
        "m2_01": (
            "The piano has a rich history that spans over 300 years, evolving from earlier keyboard instruments like the clavichord and harpsichord. "
            "The {q01:mod} piano {q02:w} invented {q03:aro} 1700 {q04:b} Bartolomeo Cristofori, {q05:w} developed a {q06:n} mechanism {q07:th} made {q08:i} possible {q09:f} players {q10:t} control the dynamics-soft and loud sounds-by varying the pressure on the keys. "
            "Later key improvements include the addition of a cast iron frame and felt-covered hammers, which allowed for greater volume and durability. These changes made the piano a central instrument in both classical and popular music."
        ),
    },
    "READING_GROUPS": {
        "m1": [
            (1, 10, "complete_words", "Supply and Demand"),
            (11, 20, "complete_words", "Evolutionary Fossils"),
            (21, 22, "read_in_daily_life", "Graphic Designer Internship"),
            (23, 24, "directions", "Directions to the Student Center"),
            (25, 27, "email", "Upcoming Meeting Room"),
            (28, 30, "notice", "Maple Heights Maintenance"),
            (31, 35, "academic_passage", "Value Theory"),
        ],
        "m2": [
            (1, 10, "complete_words", "Piano History"),
            (11, 15, "academic_passage", "Green Chemistry Innovations"),
        ],
    },
    "READING_MC_OVERRIDES": {
        ("m1", 22): {
            "stem": "What should Mr. Ahmed bring with him?",
            "options": ["Identification documents", "An application", "A list of references", "Account information"],
            "confidence": "reviewed_repair",
            "extra_sources": ["tmp/pdfs/reading_structured/repairs/05_2026_01_27_B_004.json"],
        },
        ("m1", 24): {
            "stem": "What is the final destination?",
            "options": ["The stadium", "Maple Street", "The Student Center", "The library"],
            "confidence": "reviewed_repair",
        },
        ("m1", 26): {
            "stem": "What can be inferred about the meeting?",
            "options": ["It already underwent a scheduling change.", "Its date has not been determined.", "It has more than eight attendees.", "Its goal is to design shirts for an upcoming campus event."],
            "confidence": "reviewed_repair",
        },
        ("m1", 28): {
            "stem": "On which day of the week will maintenance activities NOT take place?",
            "options": ["Monday", "Friday", "Wednesday", "Saturday"],
            "confidence": "reviewed_repair",
        },
        ("m1", 29): {
            "stem": "For which of the following will residents be notified in advance?",
            "options": ["Upgrades to the electrical system", "Presence of loud equipment", "Workers entering dormitory rooms", "Changes in work hours"],
            "confidence": "reviewed_repair",
        },
        ("m1", 31): {
            "stem": "According to the passage, value theory is concerned with all of the following EXCEPT",
            "options": ["how to determine what is good", "whether values are personal preferences", "how to distinguish between values and principles", "the difference between intrinsic and instrumental value"],
            "confidence": "reviewed_repair",
        },
        ("m1", 32): {
            "stem": 'What does the phrase "This consequentialist framework" refer to?',
            "options": ["The view that the consequences of an action determine its morality", "Theories that foreground the happiness of the individual in assigning value", "The underlying view that theories of value have an impact on making life decisions", "The debate about how best to balance competing outcomes of happiness and utility"],
            "confidence": "reviewed_repair",
        },
        ("m1", 34): {
            "stem": "According to the passage, what is one main criticism of utilitarianism?",
            "options": ["Its implementation may benefit public policy, but it is less helpful for economic decisions.", "Its priority of making healthcare more accessible creates higher costs for most people.", "In its efforts to benefit large numbers of people, it may harm some individuals.", "There is little evidence that it leads to improved healthcare for the majority."],
            "confidence": "reviewed_repair",
        },
        ("m1", 35): {
            "stem": "What does the passage suggest about value pluralism?",
            "options": ["It was a popular system for making decisions until quite recently.", "It gives primary consideration to compassion while autonomy plays a secondary role.", "It states that ethical decisions require the input of multiple decision-makers.", "It argues that ethical decisions should not be based on just one criterion."],
            "confidence": "reviewed_repair",
        },
        ("m2", 12): {
            "stem": 'The word "breakthrough" in the passage is closest in meaning to',
            "options": ["source", "damage", "advancement", "revision"],
            "confidence": "reviewed_repair",
        },
        ("m2", 13): {
            "stem": "According to the passage, what is an important difference between plastics derived from petroleum and plastics made from corn starch?",
            "options": ["The types of products they can be used for", "The conditions needed for their production", "The length of time it can take for them to break down", "The amount of catalysts used in their production"],
            "confidence": "reviewed_repair",
        },
        ("m2", 15): {
            "stem": "The passage indicates that using water as a solvent is beneficial for all of the following reasons EXCEPT:",
            "options": ["It can produce catalysts more safely", "It can reduce the need for toxic solvents", "It can result in more sustainable processes", "It can increase the speed of reactions"],
            "confidence": "reviewed_repair",
        },
    },
    "BLOCKED_READING": set(),
    "GRADING_BLOCKED_READING": set(),
    "READING_PAGE_OVERRIDES": {
        **{("m1", number): 1 for number in range(1, 11)},
        **{("m1", number): 2 for number in range(11, 22)},
        **{("m1", number): 3 for number in range(22, 24)},
        **{("m1", number): 4 for number in range(24, 26)},
        **{("m1", number): 5 for number in range(26, 28)},
        **{("m1", number): 6 for number in range(28, 31)},
        **{("m1", number): 7 for number in range(31, 34)},
        **{("m1", number): 8 for number in range(34, 36)},
        **{("m2", number): 9 for number in range(1, 12)},
        **{("m2", number): 10 for number in range(12, 15)},
        ("m2", 15): 11,
    },
    "LISTENING_ANSWERS": {
        "m1": ["A", "C", "C", "D", "C", "D", "D", "A", "A", "C", "B", "B", "C", "A", "A", "B", "B", "C", "D", "A", "A", "C", "D", "A", "C", "A", "D", "C", "C", "B", "A", "B"],
        "m2": ["B", "D", "B", "C", "C", "A", "C", "B", "C", "C", "A", "B", "C", "A", "D"],
    },
    "LISTENING_GROUPS": {
        "m1": [
            (1, 12, "listen_and_choose", "Choose the Best Response"),
            (13, 14, "conversation", "Game Photos"),
            (15, 16, "conversation", "System Upgrade"),
            (17, 18, "conversation", "Restaurant Recommendation"),
            (19, 20, "announcement", "Fitness Center Closing"),
            (21, 22, "announcement", "End-of-Semester Celebration"),
            (23, 24, "announcement", "International Club Film Screening"),
            (25, 28, "lecture", "Soft Power"),
            (29, 32, "lecture", "Positive Reinforcement"),
        ],
        "m2": [
            (1, 3, "listen_and_choose", "Choose the Best Response"),
            (4, 5, "conversation", "Furniture Recommendation"),
            (6, 7, "conversation", "Study Abroad Jet Lag"),
            (8, 11, "lecture", "Expressionism"),
            (12, 15, "lecture", "Isolation in Literature"),
        ],
    },
    "BLOCKED_LISTENING": {("m1", 25)},
    "LISTENING_OPTION_OVERRIDES": {
        ("m1", 1): ["It was due yesterday.", "My partner is due to be here soon.", "The teaching assistant grades the projects.", "I finished editing mine."],
        ("m1", 2): ["Some of us will be late.", "It'll be about outsider art.", "I think it will be Professor Patel.", "It'll be in the auditorium."],
        ("m1", 4): ["It takes over an hour to complete.", "I already filled it out.", "Tomorrow morning is the deadline.", "Through the hiring website."],
        ("m1", 6): ["I will be studying in the library.", "How many classes are you taking?", "Can I borrow your history book?", "Thanks for the reminder."],
        ("m1", 7): ["It was on sale.", "My old one stopped working.", "It's really fast.", "Online."],
        ("m1", 8): ["I believe it's Dr. Thomas.", "Dr. Yoshida is on the phone.", "It was informative.", "We can go today."],
        ("m1", 10): ["They made a movie based on the book.", "I just wish I could dedicate more time to it.", "I'm not very interested in the characters.", "There are no more reservations available."],
        ("m1", 12): ["It's a collaborative document.", "Some students only just arrived now.", "I'll confirm the minutes.", "I look forward to it."],
        ("m1", 15): ["Over the weekend", "During lunch", "On Friday", "The next morning"],
        ("m1", 17): ["A place to have a business meeting", "A place to celebrate a special occasion", "A new recipe to try at home", "A gift for his advisor"],
        ("m1", 18): ["Order a chicken dish", "Look for a different restaurant", "Make a reservation soon", "Cook a meal at home"],
        ("m1", 20): ["The fitness center will be closed.", "The fitness center will hire additional employees.", "The dumbbells in the fitness center will be replaced.", "A new morning class will begin at the fitness center."],
        ("m1", 22): ["To suggest games or activities", "To indicate whether they will be attending", "To offer to help set up", "To donate prizes"],
        ("m1", 24): ["Writing a brief paper", "Submitting a film review", "Researching a cultural topic", "Presenting a class project"],
        ("m1", 27): ["It reveals certain limitations of cultural diplomacy.", "It may reflect a short-term trend.", "It is unrelated to Nye's concept of soft power.", "It shows how attraction can expand a nation's influence."],
        ("m1", 32): ["To advocate for gentle parenting techniques", "To warn against reinforcing unwanted behavior", "To explain how small actions lead to big changes", "To describe the consequences of inconsistent feedback"],
        ("m2", 2): ["I can fix that easily.", "The professor said the test would be easy.", "No, I like to use two monitors.", "Someone at the computer lab could help."],
        ("m2", 5): ["Pay for a delivery", "Look at a map", "Give the man some information", "Go to a store"],
        ("m2", 7): ["Take an extra course", "Research other study abroad options", "Transfer course credit", "Review her travel plan"],
        ("m2", 11): ["It focused too much on personal experience.", "It restricted artists from exploring new ideas.", "It lacked emotional intensity.", "It followed traditional aesthetics."],
        ("m2", 13): ["He finds solace only in nature.", "He is considered a tragic figure in literature.", "He is an outcast because of his appearance.", "He is a common subject in studies of isolation in literature."],
        ("m2", 15): ["Jane does not recognize that she has been isolated.", "Jane manages to make friends at boarding school.", "Jane has chosen to isolate herself.", "Jane uses isolation to her advantage."],
    },
    "LISTENING_STEM_OVERRIDES": {
        ("m2", 7): "What does Alyssa need to do?",
    },
    "LISTENING_PAGE_OVERRIDES": {
        ("m1", 1): 12, ("m1", 2): 13, ("m1", 3): 14, ("m1", 4): 15,
        ("m1", 5): 16, ("m1", 6): 17, ("m1", 7): 18, ("m1", 8): 19,
        ("m1", 9): 20, ("m1", 10): 21, ("m1", 11): 22, ("m1", 12): 23,
        ("m1", 13): 25, ("m1", 14): 26, ("m1", 15): 28, ("m1", 16): 28,
        ("m1", 17): 30, ("m1", 18): 30, ("m1", 19): 31, ("m1", 20): 32,
        ("m1", 21): 33, ("m1", 22): 33, ("m1", 23): 34, ("m1", 24): 35,
        ("m1", 25): 35, ("m1", 26): 36, ("m1", 27): 36, ("m1", 28): 37,
        ("m1", 29): 38, ("m1", 30): 38, ("m1", 31): 39, ("m1", 32): 39,
        ("m2", 1): 41, ("m2", 2): 41, ("m2", 3): 42, ("m2", 4): 44,
        ("m2", 5): 44, ("m2", 6): 46, ("m2", 7): 47, ("m2", 8): 48,
        ("m2", 9): 48, ("m2", 10): 49, ("m2", 11): 49, ("m2", 12): 50,
        ("m2", 13): 51, ("m2", 14): 51, ("m2", 15): 52,
    },
    "WRITING_ORDERED": {
        1: "do you know if they have enough volunteers ?",
        2: "That's right. I am not sure what I want to do in the future .",
        3: "He wanted to know when the professor would be available to meet .",
        4: "what changes are you planning to make ?",
        5: "I was in class when you called me .",
        6: "I'm enrolled in the one that covers advanced mathematics .",
        7: "it wasn't available online .",
        8: "did the professor assign an interesting topic to you ?",
        9: "do you need to borrow my notes ?",
        10: "No, I missed it because of a late class .",
    },
    "WRITING_SENTENCE_ITEMS": {
        1: ("The students are organizing a charity run this weekend.", ["you", "enough", "volunteers", "they", "do", "know", "have", "if"]),
        2: ("I hear you're thinking of changing your course of study.", ["sure", "to", "do", "not", "want", "what", "I", "in", "the", "future"]),
        3: ("What did Julio ask you?", ["when", "be", "available", "to", "know", "to", "meet", "would", "wanted", "the", "professor"]),
        4: ("My roommate and I are going to rearrange our dorm room.", ["are", "to", "changes", "planning", "make", "what", "you"]),
        5: ("Why didn't you answer your phone?", ["called", "me", "class", "when", "you", "was", "I", "in"]),
        6: ("Which course are you taking next semester?", ["I'm", "enrolled", "advanced", "in", "the", "mathematics", "one", "that", "covers"]),
        7: ("Did you find the information you were looking for?", ["it", "online", "wasn't", "available"]),
        8: ("I have to write a research paper for my class.", ["the", "professor", "assign", "did", "you", "an", "topic", "to", "interesting"]),
        9: ("I have an exam early tomorrow morning.", ["you", "notes", "do", "borrow", "need", "to", "my"]),
        10: ("Did you see the latest episode of the series?", ["class", "late", "because", "of", "a", "I", "missed"]),
    },
    "WRITING_FIXED_TEXT": {
        2: {"prefix": "That's right. I am"},
        3: {"prefix": "He"},
        6: {"prefix": "I'm enrolled"},
        10: {"prefix": "No,"},
    },
    "WRITING_MANUAL_PROMPTS": {
        11: (
            "You are a university student living in a dormitory. Recently, you have noticed that the internet connection in your dormitory is very slow and often disconnects. "
            "This issue is making it difficult for you to complete your assignments and attend online classes. You want to report this problem to the dormitory manager, Mr. Evans, and request a solution. "
            "Write an email to Mr. Evans. Describe the issue with the internet connection, explain how this problem is affecting your studies, and request that the internet connection be improved as soon as possible. "
            "To: Mr Evans. Subject: Internet connection issues in dormitory. Write as much as you can and in complete sentences."
        ),
        12: (
            "Your professor is teaching a class on international relations. Write a post responding to the professor's question. "
            "Dr. Diaz asks: We've been examining the role of international organizations, such as the United Nations, in promoting global peace and security. Some argue that these organizations are essential for maintaining international order, while others believe they are ineffective and should be reformed. What is your opinion on the effectiveness of international organizations in promoting global peace and security? "
            "Andrew believes international organizations are crucial for promoting peace because they provide a forum for dialogue and can help mediate conflicts before they escalate. Claire argues that international organizations often struggle to enforce decisions and can be slow to respond to crises, so they need significant reforms. "
            "Express and support your opinion, contribute to the discussion in your own words, and write at least 100 words."
        ),
    },
    "WRITING_PAGES": {1: 52, 2: 53, 3: 53, 4: 54, 5: 54, 6: 55, 7: 55, 8: 56, 9: 56, 10: 57, 11: 58, 12: 59},
    "SPEAKING_REPEAT_AUDIO_TRANSCRIPT": [
        "Welcome to our campus tour.",
        "The enrollment office is straight ahead.",
        "Next door, you will see the library.",
        "The cafeteria has many meal options available.",
        "The university lecture halls are located over here.",
        "If you have any questions, please stop by the information desk.",
        "Lastly, please also remember to check the event schedule at the entrance.",
    ],
    "SPEAKING_INTERVIEW_AUDIO_TRANSCRIPT": [
        "First, which do you think is more important for a college, offering a wide variety of courses or having small class sizes?",
        "Imagine that you are preparing for a test. Would you prefer to study by yourself or with the group? What would make you choose one over the other?",
        "Some people believe that online courses offer more flexibility and accessibility compared to those offered in traditional classroom settings, and are therefore superior. What are your thoughts on this? Do you agree or disagree? Why?",
        "Online courses are becoming increasingly popular, and there are now full-degree programs offered by universities where every class is available online only. Do you think online learning will someday completely replace in-person learning? Explain your thoughts.",
    ],
    "SPEAKING_PAGES": {1: 61, 2: 63, 3: 64, 4: 65, 5: 66, 6: 67, 7: 68, 8: 69, 9: 69, 10: 70, 11: 70},
    "SPEAKING_CONTENT_STATUS": "reviewed_repair",
    "BLOCKED_REASON_BY_ITEM": {
        ("listening", "m1", 25): "Source paper/OCR exposes only the podcast intro screen; the actual question stem and four answer options are absent, so exclude from auto-grading denominator.",
    },
}


A28_EXAM_CONFIG: dict[str, Any] = {
    "EXAM_KEY": "2026-01-28_A",
    "PROGRESS_KEY": "2026-01-28-A",
    "EXAM_ID": "toefl:2026-01-28-a",
    "SOURCE_FOLDER": "1.28新托福真题A卷",
    "PAPER": "1.28新托福真题A卷/2026新托福真题05.pdf",
    "ANSWER_PDF": "1.28新托福真题A卷/2026新托福真题05-参考答案.pdf",
    "TRANSCRIPT_PDF": "1.28新托福真题A卷/2026新托福真题05-听力原文.pdf",
    "LISTENING_M1_AUDIO": "1.28新托福真题A卷/2026新托福真题05-听力音频-Module1.mp3",
    "LISTENING_M2_AUDIO": "1.28新托福真题A卷/2026新托福真题05-听力音频-Module2.mp3",
    "SPEAKING_AUDIO": "1.28新托福真题A卷/2026新托福真题05-口语音频.mp3",
    "READING_CACHE": "tmp/pdfs/reading_structured/extracted/06_2026_01_28_A.json",
    "READING_EXTRA_SOURCE_PATHS": [
        "tmp/pdfs/reading_structured/repairs/06_2026_01_28_A_004.json",
        "tmp/pdfs/reading_structured/repairs/06_2026_01_28_A_010.json",
    ],
    "SPEAKING_TRANSCRIPT_JSON": "新托福分科刷题材料/整理输出/口语转写_修订版/transcripts/2026-01-28_A_part1.json",
    "LISTENING_SECTION_HEADING": "## 2026-01-28 A卷",
    "LISTENING_SECTION_STOP_MARKER": "### 来源：1.28新托福真题A卷/2026新托福真题05-听力原文.pdf",
    "LISTENING_PROMPT_UPPER": {"m1": 12, "m2": 3},
    "EXAM_TITLE": "2026-01-28 TOEFL Real Exam A",
    "EXAM_DATE": "2026-01-28",
    "EXAM_VARIANT": "A",
    "PROGRESS_NOTES": "120 atomic questions rebuilt from source; Reading M2 Q6 and Listening M1 Q24 were repaired from corroborating source text/transcript evidence after the answer PDF conflicted.",
    "BLOCKING_REASONS": [],
    "LATEST_BLOCKER_TEXT": "No unresolved source-content blockers; subject review is still required before release.",
    "QA_CHECK_SPECS": [
        {"id": "atomic-count", "status": "pass", "detail": "120 expected atomic questions are represented."},
        {"id": "answer-separation", "status": "pending", "detail": "Validator will check public content for answer leakage."},
        {"id": "reading-source", "status": "pass", "detail": "Reading M2 Q6 is graded as 'orate' from the visible 'elab' prefix and corroborating full source text ('elaborate')."},
        {"id": "listening-source", "status": "pass", "detail": "Listening option screens are visible or visually recovered from rendered source pages."},
        {"id": "listening-answer-conflict", "status": "pass", "detail": "Listening M1 Q24 is graded as A from the source transcript's explicit credited-sources requirement; the conflicting answer-PDF key is not used as grading evidence."},
        {"id": "media", "status": "pass", "detail": "Listening and speaking audio files exist and have readable ffprobe durations."},
        {"id": "speaking-source", "status": "pass", "detail": "Speaking audio transcript aligns with the botanical-garden and entertainment-preferences scenes in the source."},
        {"id": "inline-reading-contract", "status": "pass", "detail": "Complete-the-words groups define inline token rendering without public answer fields."},
    ],
    "READING_ANSWERS": {
        "m1": [
            "lude", "ys", "ple", "nals", "ow", "ore", "ieve", "ory", "uage", "used",
            "dents", "e", "y", "tors", "s", "nges", "ss", "rophic", "ing", "lps",
            "B", "B", "C", "B", "D", "C", "B", "A", "B", "D", "C", "C", "B", "D", "B",
        ],
        "m2": ["iefs", "pire", "tions", "ient", "tings", "orate", "ecture", "tory", "ve", "ual", "C", "B", "C", "B", "B"],
    },
    "FILL_PREFIXES": {
        "m1": ["inc", "wa", "peo", "sig", "h", "st", "retr", "mem", "lang", "prod", "inci", "b", "b", "fac", "a", "cha", "lo", "catast", "Stud", "he"],
        "m2": ["bel", "ins", "crea", "anc", "pain", "elab", "archit", "his", "ha", "vis"],
    },
    "FILL_DISPLAY": {
        "m1_01": (
            "Human cognition refers to the mental processes involved in acquiring, processing, storing, and using knowledge. "
            "These {q01:inc} the {q02:wa} that {q03:peo} interpret sensory {q04:sig} (perception), {q05:h} we {q06:st} and {q07:retr} information ({q08:mem}), "
            "how {q09:lang} is {q10:prod} (speech), and how humans analyze and solve problems. "
            "Researchers study cognitive functions to uncover how the brain processes information and how these processes influence behavior. "
            "Insights from cognitive science can improve educational methods and help develop interventions for cognitive disorders."
        ),
        "m1_02": (
            "Extinctions are a natural part of Earth's history, marking the end of species that die out and paving the way for new ones. "
            "These {q11:inci} can {q12:b} caused {q13:b} varying {q14:fac}, such {q15:a} environmental {q16:cha}, habitat {q17:lo}, and {q18:catast} events. "
            "{q19:Stud} extinctions {q20:he} scientists understand biodiversity and the resilience of ecosystems. "
            "Notable extinctions, like the one that wiped out most of the dinosaurs, offer insights into how life on Earth can dramatically shift. "
            "Modern conservation efforts aim to prevent human-induced extinctions and preserve remaining species."
        ),
        "m2_01": (
            "Throughout history, art and religion have been deeply intertwined. "
            "Religious {q01:bel} often {q02:ins} artistic {q03:crea} from {q04:anc} cave {q05:pain} to {q06:elab} cathedral {q07:archit}. "
            "Throughout {q08:his}, artists {q09:ha} used {q10:vis} imagery to express spiritual ideas and convey religious stories. "
            "Iconography, the study of symbols and images in art, helps us understand the meaning behind religious artwork. "
            "Churches, temples, and other places of worship are often adorned with intricate designs that reflect the convictions and practices of their communities."
        ),
    },
    "READING_GROUPS": {
        "m1": [
            (1, 10, "complete_words", "Human Cognition"),
            (11, 20, "complete_words", "Extinctions"),
            (21, 22, "email", "Sunset Resort Stay"),
            (23, 25, "notice", "Fitness Club Rules"),
            (26, 30, "academic_passage", "Noise Control in Urban Areas"),
            (31, 35, "academic_passage", "Stoicism in Ancient Philosophy"),
        ],
        "m2": [
            (1, 10, "complete_words", "Art and Religion"),
            (11, 15, "academic_passage", "Expert Systems"),
        ],
    },
    "READING_MC_OVERRIDES": {
        ("m1", 22): {
            "stem": "What can Ms. Anderson expect from the staff during her stay?",
            "options": ["Assistance with transportation to nearby cities", "Helping plan local activities and outings", "Guidance on exclusive dining options", "Information about local customs"],
            "confidence": "visually_recovered",
            "extra_sources": ["tmp/pdfs/reading_structured/repairs/06_2026_01_28_A_004.json"],
        },
        ("m1", 28): {
            "stem": "What can be inferred about noise pollution in the European cities mentioned in the passage?",
            "options": ["It was likely a factor in causing stress-related health issues among residents.", "It has not been as effectively managed there as it has been in other places.", "It has been controlled most successfully by adding green walls to buildings.", "It has been funded primarily through the efforts of urban planners."],
            "confidence": "reviewed_repair",
        },
        ("m1", 29): {
            "stem": "Identify the sentence in paragraph 4 that names specific architectural elements built with noise-canceling materials. Select the sentence to make your choice.",
            "options": ["Sentence 1", "Sentence 2", "Sentence 3", "Sentence 4"],
            "confidence": "visually_recovered",
            "extra_sources": ["tmp/pdfs/reading_structured/repairs/06_2026_01_28_A_010.json"],
        },
        ("m1", 30): {
            "stem": "One common source is traffic, which includes cars, buses, motorcycles, and trucks. Where would the sentence best fit? Select a location to add the sentence in the passage.",
            "options": ["Location A", "Location B", "Location C", "Location D"],
            "confidence": "visually_recovered",
        },
        ("m1", 32): {
            "stem": 'The word "equanimity" in the passage is closest in meaning to',
            "options": ["meaning to", "concern", "calmness", "exceptions"],
            "confidence": "source_exact",
        },
        ("m1", 33): {
            "stem": "Why does the author mention public speaking?",
            "options": ["To provide an example of taking a \"Stoic pause\" in high-stakes situations", "To show how cognitive-behavioral therapy incorporates Stoic ideas", "To illustrate the contrast between rational and irrational thoughts from the Stoic point of view", "To suggest that Stoics believe certain emotions can be beneficial"],
            "confidence": "source_exact",
        },
        ("m1", 34): {
            "stem": "What is the relationship between paragraph 2 and 1?",
            "options": ["Paragraph 2 discusses an alternative theory to the one presented in paragraph 1.", "Paragraph 2 explains a concept introduced in paragraph 1.", "Paragraph 2 describes solutions to an issue presented in paragraph 1.", "Paragraph 2 discusses the modern applications of the principles discussed in paragraph 1."],
            "confidence": "source_exact",
        },
        ("m1", 35): {
            "stem": "Taking a step back to analyze the situation helps you react in a more measured and mindful way. Where would the sentence best fit? Select a location to add the sentence in the passage.",
            "options": ["Location A", "Location B", "Location C", "Location D"],
            "confidence": "visually_recovered",
        },
        ("m2", 15): {
            "stem": "Additionally, their performance may decline in unfamiliar or rapidly changing environments where new information is constantly emerging. Where would the sentence best fit? Select a location to add the sentence in the passage.",
            "options": ["Location A", "Location B", "Location C", "Location D"],
            "confidence": "visually_recovered",
        },
    },
    "BLOCKED_READING": set(),
    "GRADING_BLOCKED_READING": set(),
    "READING_PAGE_OVERRIDES": {
        **{("m1", number): 2 for number in range(1, 21)},
        ("m1", 21): 3,
        **{("m1", number): 4 for number in range(22, 24)},
        **{("m1", number): 5 for number in range(24, 26)},
        **{("m1", number): 6 for number in range(26, 28)},
        **{("m1", number): 7 for number in range(28, 30)},
        **{("m1", number): 8 for number in range(30, 32)},
        **{("m1", number): 9 for number in range(32, 35)},
        ("m1", 35): 10,
        **{("m2", number): 11 for number in range(1, 12)},
        **{("m2", number): 12 for number in range(12, 14)},
        **{("m2", number): 13 for number in range(14, 16)},
    },
    "LISTENING_ANSWERS": {
        "m1": ["A", "C", "B", "A", "B", "D", "C", "A", "A", "D", "D", "B", "B", "B", "D", "D", "B", "D", "B", "C", "B", "C", "C", "A", "A", "D", "C", "B", "B", "A", "B", "C"],
        "m2": ["D", "D", "C", "D", "C", "D", "D", "D", "C", "A", "B", "B", "B", "C", "A"],
    },
    "LISTENING_GROUPS": {
        "m1": [
            (1, 12, "listen_and_choose", "Choose the Best Response"),
            (13, 14, "conversation", "Car Maintenance"),
            (15, 16, "conversation", "Art Store Closing"),
            (17, 18, "conversation", "Apartment Hunt"),
            (19, 20, "announcement", "University Gym Schedule"),
            (21, 22, "announcement", "Administrative Forms"),
            (23, 24, "announcement", "Digital Storytelling Project"),
            (25, 28, "lecture", "Decalcomania"),
            (29, 32, "lecture", "Inattentional Blindness"),
        ],
        "m2": [
            (1, 3, "listen_and_choose", "Choose the Best Response"),
            (4, 5, "conversation", "Conference Train"),
            (6, 7, "conversation", "Restaurant and Camping Vacation"),
            (8, 11, "lecture", "Trilobites"),
            (12, 15, "lecture", "Bioacoustics"),
        ],
    },
    "BLOCKED_LISTENING": set(),
    "GRADING_BLOCKED_LISTENING": set(),
    "ANSWER_EVIDENCE_OVERRIDES": {
        ("reading", "m2", 6): [
            {"path": "1.28新托福真题A卷/2026新托福真题05.pdf", "page": 11, "confidence": "reviewed_repair"},
            {"path": "tmp/pdfs/reading_rebuild_qa/text.txt", "confidence": "reviewed_repair"},
            {"path": "tmp/pdfs/reading_structured/wechat_complete_words_full.json", "confidence": "reviewed_repair"},
        ],
        ("listening", "m1", 24): [
            {"path": "1.28新托福真题A卷/2026新托福真题05.pdf", "page": 25, "confidence": "reviewed_repair"},
            {"path": "1.28新托福真题A卷/2026新托福真题05-听力原文.pdf", "confidence": "source_exact"},
        ],
    },
    "LISTENING_OPTION_OVERRIDES": {
        ("m1", 1): ["About two hours.", "This weekend.", "It was expensive.", "As far as I know."],
        ("m1", 2): ["Yes, the meeting is tomorrow.", "When is the conference?", "Do you have a sweater?", "No, it's not very old."],
        ("m1", 3): ["I have to work on my lab report for chemistry class.", "I want to go to the exhibit my professor recommended.", "Do you want to take the bus with me?", "I had tickets for the production last week."],
        ("m1", 4): ["It was loud.", "Sure, that sounds like a plan.", "No, it wasn't.", "Yes, where are they?"],
        ("m1", 5): ["Three meters long.", "In the supply cabinet.", "Close to the deadline.", "On Tuesday morning."],
        ("m1", 6): ["Timing your presentation is always helpful.", "They arrived last week.", "The presentation is saved on a USB drive.", "I'm pretty busy next week."],
        ("m1", 7): ["On Platform B.", "Yes, the bus is running a little late.", "It's a kilometer north of Fleet Street.", "I'll get the next flight."],
        ("m1", 8): ["I need help.", "Please clean your desk.", "No, I have other plans.", "Yes, I got the invite."],
        ("m1", 9): ["I haven't worked with her much yet.", "Yes, it should be lots of fun.", "She was in the cafeteria.", "Every Friday at noon, I think."],
        ("m1", 10): ["The construction is loud.", "I set my alarm for 8 a.m.", "I heard the announcement.", "I don't have a favorite."],
        ("m1", 11): ["The chairs were replaced recently.", "I organize my supplies by color.", "There are some great articles in the paper.", "We should check our current inventory."],
        ("m1", 12): ["Yes, we practice every day.", "That sounds great.", "No, but David does.", "My class starts at 10 a.m."],
        ("m1", 13): ["She thinks her tire pressure is low.", "She is going on a trip.", "She spilled oil in the backseat.", "She wants to sell it next month."],
        ("m1", 14): ["Go to the grocery store", "Visit a website", "Check out a library book", "Park her car in a garage"],
        ("m1", 15): ["To deliver art supplies to her", "To invite her to go to the mall", "To ask her for painting lessons", "To tell her about a store closure"],
        ("m1", 16): ["Shop online more frequently", "Relocate to Porterville", "Create a painting for the man", "Purchase art supplies in another town"],
        ("m1", 17): ["It has a nice view.", "It is located near the university.", "The landlord is helpful.", "The lease terms are flexible."],
        ("m1", 18): ["Swim in the pool", "Tour a university museum", "Meet her neighbors", "See the landlord"],
        ("m1", 19): ["It depends on the day of the week.", "It is not the same for all types of equipment.", "It was decided based on student feedback.", "It will change soon."],
        ("m1", 20): ["A rule about reporting damage", "A rule about cleaning equipment after use", "A rule about wearing suitable clothing", "A rule about not using machines for too long"],
        ("m1", 21): ["To solicit ideas for improving administrative efficiency", "To describe new administrative procedures", "To answer student questions about a new administrative office", "To address student concerns about campus accessibility standards"],
        ("m1", 22): ["Forms were accepted only before noon.", "Submission of forms required visiting several offices.", "It was acceptable to submit paper forms.", "Forms were accepted only through the mail."],
        ("m1", 23): ["An analysis of a music video", "Digital media uses", "A personal story", "A famous painting"],
        ("m1", 24): ["Its sources must be credited.", "It should include an interview.", "It should include a written transcript.", "It should feature original music."],
        ("m1", 25): ["A unique art form that began relatively recently", "The life and career of an important artist", "Features of different painting surfaces", "The development of figurative art"],
        ("m1", 26): ["To express his admiration for ancient pottery", "To point out where a technique was invented", "To identify an inspiration for Max Ernst's artwork", "To provide an example of a place with ancient artwork"],
        ("m1", 27): ["Creating an image and then applying it onto multiple surfaces", "Creating a drawing on paper and then copying it onto canvas", "Pressing two surfaces together and then pulling them apart", "Letting paint dry on a paper surface and then drawing on top of it"],
        ("m1", 28): ["It used a variety of colors and materials.", "It involved a lack of control on the artist's part.", "It was made popular by the Surrealist Movement.", "It had the ability to create similar patterns across various artworks."],
        ("m1", 29): ["A psychological technique designed to help people increase their attention span", "The tendency to not notice something happening around you when you are focused on something else", "The ability of some people to perform a surprisingly large number of tasks at the same time", "The large number of distractions in modern life"],
        ("m1", 30): ["Count basketball passes made by players", "Spot the person in the gorilla suit", "Predict the result of a game", "Stop the video when a player dropped the ball"],
        ("m1", 31): ["To better understand other people's behavior", "To avoid dangerous situations", "To improve focus on all tasks at once", "To avoid selective attention at work"],
        ("m1", 32): ["To identify a new study on inattentional blindness", "To suggest that inattentional blindness always involves sounds", "To explain that inattentional blindness is derived from a valuable ability", "To illustrate a way of avoiding inattentional blindness"],
        ("m2", 1): ["It's very good for your health.", "Dr. Stevens is very nice.", "Hospitals are important.", "There is one on campus."],
        ("m2", 2): ["I work from home most days.", "I have a meeting on Tuesday.", "I'm enjoying it.", "Two weeks ago."],
        ("m2", 3): ["I met with the presenter this morning.", "All students have to present.", "The presenter was very knowledgeable.", "I need to review my notes beforehand."],
        ("m2", 4): ["He finds driving alone boring.", "He'd like to finish reading a book on the train.", "He does not own a car.", "He wants to do some work as he travels."],
        ("m2", 5): ["Take the train to the conference with him", "Get some work done on the train", "Bring a book with her on the train", "Rent a car when she arrives at the conference"],
        ("m2", 6): ["He really likes its sushi.", "Its location is inconvenient for him.", "Its chef deserves an award.", "It is too expensive for him."],
        ("m2", 7): ["He loves sleeping in his sleeping bag at campsites.", "He is saving money for a new bed in his home.", "Some hotels are not very comfortable.", "He is unenthusiastic about the woman's idea."],
        ("m2", 8): ["To point out how trilobites adapted to life in the sea", "To help explain why trilobites went extinct", "To emphasize how hard trilobites' exoskeletons were", "To describe what trilobites looked like"],
        ("m2", 9): ["They were helpful for producing sharp images.", "They were an unusual characteristic in trilobites.", "They were effective for seeing movement.", "They covered only a small area of the trilobite's head."],
        ("m2", 10): ["Adult trilobites had an eye in the middle of the forehead.", "Trilobites had three joints on each of their legs.", "Trilobites grew more body segments throughout their lives.", "Young trilobites slowly developed hard exoskeletons."],
        ("m2", 11): ["Its exoskeleton was lighter than expected.", "Its poor condition provided a benefit.", "It was the first fossil discovered of a trilobite in a larval stage.", "It was found near fully-preserved trilobite fossils."],
        ("m2", 12): ["How scientists identify species using sound recordings", "Research into sound-based communication in animals", "The use of audio technology in wildlife research", "The impact of environmental noise on animal communication"],
        ("m2", 13): ["The age of each whale in a group", "How large the whale population is", "The intended purpose of whale communication", "Whether whales are experiencing environmental stress"],
        ("m2", 14): ["They vary depending on the time of year.", "They are used mainly for long-distance communication.", "They reflect important aspects of bird societies.", "They are more complicated than the songs of whales."],
        ("m2", 15): ["To highlight a challenge in bioacoustics research", "To show how sound affects animal behavior", "To explain why it is more difficult to study land animals than ocean animals", "To show how human activity affects animal communication"],
    },
    "LISTENING_PAGE_OVERRIDES": {
        ("m1", 1): 14, ("m1", 2): 15, ("m1", 3): 15, ("m1", 4): 16,
        ("m1", 5): 16, ("m1", 6): 17, ("m1", 7): 17, ("m1", 8): 18,
        ("m1", 9): 18, ("m1", 10): 19, ("m1", 11): 19, ("m1", 12): 20,
        ("m1", 13): 21, ("m1", 14): 21, ("m1", 15): 22, ("m1", 16): 22,
        ("m1", 17): 23, ("m1", 18): 23, ("m1", 19): 23, ("m1", 20): 23,
        ("m1", 21): 24, ("m1", 22): 24, ("m1", 23): 25, ("m1", 24): 25,
        ("m1", 25): 26, ("m1", 26): 26, ("m1", 27): 27, ("m1", 28): 27,
        ("m1", 29): 28, ("m1", 30): 28, ("m1", 31): 28, ("m1", 32): 28,
        ("m2", 1): 29, ("m2", 2): 30, ("m2", 3): 30, ("m2", 4): 31,
        ("m2", 5): 31, ("m2", 6): 32, ("m2", 7): 32, ("m2", 8): 33,
        ("m2", 9): 34, ("m2", 10): 34, ("m2", 11): 34, ("m2", 12): 35,
        ("m2", 13): 35, ("m2", 14): 36, ("m2", 15): 36,
    },
    "WRITING_ORDERED": {
        1: "Can you tell me whether he provided a reason ?",
        2: "I'm reading an exciting book that my friend recommended .",
        3: "the one that involves community outreach and education is my focus right now.",
        4: "do you know when they will announce the results ?",
        5: "do you konw if she provided any additional resources ?",
        6: "have you updated your résumé yet?",
        7: "do you know if it is usually on time ?",
        8: "the place where I live now is much quieter than my old one .",
        9: "do you know if she has accepted it ?",
        10: "what topics will the class cover ?",
    },
    "WRITING_SENTENCE_ITEMS": {
        1: ("Tom said he'll be late to the internship meeting.", ["tell", "a", "reason", "whether", "provided", "me", "he"]),
        2: ("Which book are you reading?", ["exciting", "a", "that", "book", "an", "recommended", "my", "friend"]),
        3: ("Which project are you working on with your internship?", ["now.", "community", "outreach", "that", "involves", "the", "one", "is", "my", "and", "education", "focus", "right"]),
        4: ("I submitted my application for the scholarship yesterday.", ["they", "the", "results", "know", "do", "will", "announce", "when"]),
        5: ("The guest speaker at the seminar was very knowledgeable.", ["any", "additional", "resources", "provided", "you", "if", "do", "she"]),
        6: ("I need to find an internship soon.", ["your", "updated", "you", "résumé", "have", "updates"]),
        7: ("We need to hurry to catch the bus to the university.", ["time", "on", "is", "if", "it", "usually", "know", "do", "you"]),
        8: ("I heard you moved to an off-campus apartment. How is it?", ["is", "much", "quieter", "my", "the", "place", "where", "one", "old", "I", "live", "now", "than"]),
        9: ("Sarah mentioned that she received a scholarship.", ["if", "do", "has", "accepted", "it", "she", "know"]),
        10: ("I'm planning to take a photography course this semester.", ["what", "will", "cover", "topics", "the", "class"]),
    },
    "WRITING_FIXED_TEXT": {
        1: {"prefix": "Can you"},
        2: {"prefix": "I'm reading"},
        3: {"suffix": "now."},
        4: {"suffix": "?"},
        5: {"prefix": "konw"},
        6: {"suffix": "yet?"},
        9: {"prefix": "you"},
    },
    "WRITING_MANUAL_PROMPTS": {
        11: (
            "Your friend, Alex, has been feeling overwhelmed with university assignments. "
            "You have noticed that he is struggling to keep up with his workload and is not taking proper care of his health. "
            "You want to offer some helpful advice. Write an email to Alex. Describe to Alex what you have recently noticed about him, explain why it is important to maintain good health, and suggest some specific strategies Alex can use to manage his stress and workload. "
            "To: Alex. Subject: Managing stress and workload. Write as much as you can and in complete sentences."
        ),
        12: (
            "Your professor is teaching a class on sociology. Write a post responding to the professor's question. "
            "Dr. Diaz asks: We often discuss the influence of social media on modern society. Social media platforms can connect people globally and promote the exchange of ideas. However, they can also lead to misinformation and negatively impact mental health. Do you think social media has a more positive or negative impact on society? Why? "
            "Kelly believes social media has a positive impact on society because it keeps people connected with friends and family, lets people share experiences, and helps people access information quickly. Paul argues that social media has a negative impact because it can contribute to mental health problems like anxiety and depression, people often compare themselves to others on social media, and misinformation can spread quickly. "
            "Express and support your opinion, contribute to the discussion in your own words, and write at least 100 words."
        ),
    },
    "WRITING_PAGES": {1: 36, 2: 37, 3: 37, 4: 37, 5: 38, 6: 38, 7: 38, 8: 39, 9: 39, 10: 39, 11: 40, 12: 41},
    "SPEAKING_REPEAT_AUDIO_TRANSCRIPT": [
        "You can buy tickets at the entrance.",
        "The Rose Garden is beautiful this season.",
        "The pond is a popular spot for sitting and relaxing.",
        "Visit the greenhouse for a variety of exotic plants.",
        "Check the bulletin board for information about guided tours.",
        "The gift shop offers souvenirs and gardening books at reasonable prices.",
        "Enjoy your lunch at our cafe, which has outdoor seating overlooking the grounds.",
    ],
    "SPEAKING_INTERVIEW_AUDIO_TRANSCRIPT": [
        "What kind of movies do your family or friends generally like to watch? For example, do they prefer action movies, comedies, dramas, or other types?",
        "When you watch a movie, do you prefer to watch after work or school on weekdays, or do you like to watch during the weekends? Why?",
        "In the past, people mostly watched movies in theaters. Today, many people watch movies at home. Do you think that movie theaters will continue to exist in the future? Why or why not?",
        "Some people believe that movies can be a powerful tool for educating people and raising awareness about important issues. Do you agree with this idea? Or do you think there are other, more effective ways to educate people? Explain why you think so.",
    ],
    "SPEAKING_PAGES": {1: 43, 2: 45, 3: 46, 4: 47, 5: 48, 6: 49, 7: 50, 8: 51, 9: 51, 10: 52, 11: 52},
    "SPEAKING_CONTENT_STATUS": "reviewed_repair",
    "BLOCKED_REASON_BY_ITEM": {
        ("reading", "m2", 6): "Answer key lists 'tings' for a visible 'elab' prefix, which would form an invalid word; exclude from auto-grading until reviewed.",
        ("listening", "m1", 24): "Answer key says B, but source question/transcript support the credited-sources option; exclude from auto-grading until reviewed.",
    },
}


B28_EXAM_CONFIG: dict[str, Any] = {
    "EXAM_KEY": "2026-01-28_B",
    "PROGRESS_KEY": "2026-01-28-B",
    "EXAM_ID": "toefl:2026-01-28-b",
    "SOURCE_FOLDER": "1.28新托福真题B卷",
    "PAPER": "1.28新托福真题B卷/2.1新托福真题01.pdf",
    "ANSWER_PDF": "1.28新托福真题B卷/参考答案-2026新托福真题01.pdf",
    "TRANSCRIPT_PDF": "1.28新托福真题B卷/听力原文-2026新托福真题01.pdf",
    "LISTENING_M1_AUDIO": "1.28新托福真题B卷/2026新托福真题01ListeningModule1.mp3",
    "LISTENING_M2_AUDIO": "1.28新托福真题B卷/2026新托福真题01ListeningModule2.mp3",
    "SPEAKING_AUDIO": "1.28新托福真题B卷/2026新托福真题01SpeakingModule1.mp3",
    "READING_CACHE": "tmp/pdfs/reading_structured/extracted/07_2026_01_28_B.json",
    "READING_EXTRA_SOURCE_PATHS": [
        "tmp/pdfs/reading_structured/repairs/07_2026_01_28_B_003.json",
        "tmp/pdfs/reading_structured/repairs/07_2026_01_28_B_010.json",
    ],
    "SPEAKING_TRANSCRIPT_JSON": "新托福分科刷题材料/整理输出/口语转写_修订版/transcripts/2026-01-28_B_part1.json",
    "LISTENING_SECTION_HEADING": "## 2026-01-28 B卷",
    "LISTENING_SECTION_STOP_MARKER": "### 来源：1.28新托福真题B卷/听力原文-2026新托福真题01.pdf",
    "LISTENING_PROMPT_UPPER": {"m1": 12, "m2": 3},
    "EXAM_TITLE": "2026-01-28 TOEFL Real Exam B",
    "EXAM_DATE": "2026-01-28",
    "EXAM_VARIANT": "B",
    "PROGRESS_NOTES": "120 atomic questions rebuilt directly from B-volume PDF/audio/transcript sources; Reading M1 Q33's OCR navigation tail was removed after visual page review.",
    "BLOCKING_REASONS": [],
    "LATEST_BLOCKER_TEXT": "No unresolved source blockers in this package.",
    "QA_CHECK_SPECS": [
        {"id": "atomic-count", "status": "pass", "detail": "120 expected atomic questions are represented."},
        {"id": "answer-separation", "status": "pending", "detail": "Validator will check public content for answer leakage."},
        {"id": "reading-source", "status": "pass", "detail": "Reading content was recovered from rendered raw PDF pages, including documented OCR-number repair and the M1 Q33 navigation-tail cleanup."},
        {"id": "listening-source", "status": "pass", "detail": "Listening prompts/options were reconciled against the raw paper and listening transcript PDF."},
        {"id": "media", "status": "pass", "detail": "Listening and speaking audio files exist and have readable ffprobe durations."},
        {"id": "speaking-source", "status": "pass", "detail": "Speaking audio transcript aligns with class-registration and hobbies prompts in the source answer PDF."},
        {"id": "inline-reading-contract", "status": "pass", "detail": "Complete-the-words groups define inline token rendering without public answer fields."},
    ],
    "READING_ANSWERS": {
        "m1": ["mpass", "ects", "uding", "sition", "lls", "ial", "ne", "s", "rst", "ich", "as", "mon", "ists", "ate", "wn", "y", "eral", "ther", "cess", "me", "B", "D", "B", "A", "C", "C", "C", "B", "D", "C", "C", "B", "A", "A", "D"],
        "m2": ["ever", "over", "erged", "as", "eath", "n", "at", "o", "ars", "rchers", "C", "D", "B", "B", "D"],
    },
    "FILL_PREFIXES": {
        "m1": ["enco", "asp", "incl", "acqui", "ski", "soc", "O", "i", "fi", "wh", "w", "com", "art", "cre", "o", "b", "sev", "toge", "pro", "ti"],
        "m2": ["how", "disc", "subm", "w", "ben", "i", "th", "t", "ye", "Resea"],
    },
    "FILL_DISPLAY": {
        "m1_01": (
            "Child development milestones are key indicators of a child's growth. They {q01:enco} various {q02:asp} of development, "
            "{q03:incl} language {q04:acqui}, motor {q05:ski}, and {q06:soc} interactions. {q07:O} example {q08:i} taking a {q09:fi} step, {q10:wh} typically occurs around the age of twelve months. "
            "These milestones are useful in helping parents and caretakers monitor a child's progress. It is important to remember, however, that these milestones only provide a general guide, and each child develops at their own pace."
        ),
        "m1_02": (
            "Pigments are substances that provide color to materials, and they can be derived from various natural sources, such as minerals and plants. "
            "It {q11:w} once {q12:com} for {q13:art} to {q14:cre} their {q15:o} paints {q16:b} mixing {q17:sev} pigments {q18:toge}. "
            "This {q19:pro} was {q20:ti}-consuming and required detailed knowledge of pigments—their chemical properties, how they interact with different media, and their durability over time. But it also allowed painters to give their artworks a truly unique color palette."
        ),
        "m2_01": (
            "Archaeologists typically study human history and prehistory through the excavation of artifacts buried underground. Sometimes, {q01:how}, they {q02:disc} artifacts {q03:subm} underwater. "
            "A stone wall {q04:w} found {q05:ben} the Baltic Sea {q06:i} 2012 {q07:th} dates {q08:t} over 10,000 {q09:ye} ago. {q10:Resea} believe it was used by hunter-gatherer societies to guide and trap reindeer. "
            "The wall consists of approximately 1,670 stones and is considered one of the oldest documented hunting structures made by humans."
        ),
    },
    "READING_GROUPS": {
        "m1": [(1, 10, "complete_words", "Child Development Milestones"), (11, 20, "complete_words", "Pigments"), (21, 22, "advertisement", "Explore Rome Tour"), (23, 24, "label", "Organic Almond Butter"), (25, 27, "social_media_post", "Melbourne Summer Art Fair"), (28, 30, "receipt", "Trendie Boutique Receipt"), (31, 35, "academic_passage", "The Flynn Effect")],
        "m2": [(1, 10, "complete_words", "Underwater Archaeology"), (11, 15, "academic_passage", "Coral Reef Restoration")],
    },
    "READING_M2_START_PAGE": 9,
    "READING_NUMBER_REPAIRS": {("m1", 21, "What will attendees need to pay for?"): 27},
    "READING_MC_OVERRIDES": {
        ("m1", 21): {"stem": "What can be inferred about the tour package?", "options": ["It is inexpensive.", "It is popular.", "It includes transportation to and from Rome.", "It is intended only for large groups."], "confidence": "visually_recovered", "extra_sources": ["tmp/pdfs/reading_structured/repairs/07_2026_01_28_B_003.json"]},
        ("m1", 23): {"stem": "What is the weight of the product?", "options": ["100 g", "250 g", "500 g", "1000 g"], "confidence": "visually_recovered"},
        ("m1", 25): {"stem": 'The phrase "what\'s in store" in the post is closest in meaning to', "options": ["meaning to", "what will be for sale", "what will be happening", "what will be new this year"], "confidence": "visually_recovered"},
        ("m1", 27): {"stem": "What will attendees need to pay for?", "options": ["Admission", "Supplies", "Refreshments", "Entertainment"], "confidence": "visually_recovered"},
        ("m1", 28): {"stem": "What is the most expensive item?", "options": ["A scarf", "A handbag", "A pair of sunglasses", "A t-shirt"], "confidence": "visually_recovered", "extra_sources": ["tmp/pdfs/reading_structured/repairs/07_2026_01_28_B_010.json"]},
        ("m1", 33): {"stem": "According to some researchers, the Flynn Effect may be a sign that", "options": ["people are becoming better at taking tests", "IQ tests have become easier over time", "test-takers thrive in stimulating environments", "school systems have developed better examinations"], "confidence": "visually_recovered"},
        ("m1", 35): {"stem": "Changes in educational practices or shifts in societal values could account for the downturn. Where would the sentence best fit? Select a location to add the sentence in the passage.", "options": ["Location A", "Location B", "Location C", "Location D"], "confidence": "visually_recovered"},
    },
    "BLOCKED_READING": set(),
    "GRADING_BLOCKED_READING": set(),
    "READING_PAGE_OVERRIDES": {**{("m1", n): 2 for n in range(1, 21)}, **{("m1", n): 3 for n in range(21, 23)}, **{("m1", n): 4 for n in range(23, 25)}, **{("m1", n): 5 for n in range(25, 28)}, **{("m1", n): 6 for n in range(28, 30)}, **{("m1", n): 7 for n in range(30, 33)}, **{("m1", n): 8 for n in range(33, 36)}, **{("m2", n): 9 for n in range(1, 11)}, **{("m2", n): 10 for n in range(11, 14)}, **{("m2", n): 11 for n in range(14, 16)}},
    "LISTENING_ANSWERS": {
        "m1": ["A", "C", "A", "C", "D", "D", "A", "C", "B", "D", "A", "B", "C", "C", "B", "D", "D", "B", "A", "B", "D", "C", "A", "A", "A", "C", "B", "B", "B", "A", "B", "C"],
        "m2": ["B", "B", "B", "C", "B", "B", "A", "B", "A", "D", "C", "B", "C", "C", "B"],
    },
    "LISTENING_GROUPS": {
        "m1": [(1, 12, "listen_and_choose", "Choose the Best Response"), (13, 14, "conversation", "Eco Lodge Visit"), (15, 16, "conversation", "Apartment Hunt"), (17, 18, "conversation", "Campus Concert"), (19, 20, "announcement", "International Club Debate"), (21, 22, "announcement", "University Gym Schedule"), (23, 24, "announcement", "Bowling Tournament"), (25, 28, "lecture", "Music in Ancient Greece"), (29, 32, "lecture", "Inattentional Blindness")],
        "m2": [(1, 3, "listen_and_choose", "Choose the Best Response"), (4, 5, "conversation", "Campus Health Center"), (6, 7, "conversation", "Art Museum Exhibition"), (8, 11, "lecture", "Solomon Asch and Social Influence"), (12, 15, "lecture", "Precautionary Principle")],
    },
    "BLOCKED_LISTENING": set(),
    "GRADING_BLOCKED_LISTENING": set(),
    "LISTENING_OPTION_OVERRIDES": {
        ("m1", 1): ["Next to the student union.", "Seven days a week.", "It closes soon.", "I was sick yesterday."],
        ("m1", 2): ["Yes, the meeting is tomorrow.", "When is the conference?", "Do you have a sweater?", "No, it's not very old."],
        ("m1", 3): ["Because of storm damage.", "That's one possible solution.", "The quad is open all day tomorrow.", "It's usually late in the evening."],
        ("m1", 4): ["It was loud.", "Sure, that sounds like a plan.", "No, it wasn't.", "Yes, where are they?"],
        ("m1", 5): ["That's a good point.", "It was mentioned in passing.", "As far as I recall.", "Sure, but I think you already have it."],
        ("m1", 6): ["Timing your presentation is always helpful.", "They arrived last week.", "The presentation is saved on a USB drive.", "I'm pretty busy next week."],
        ("m1", 7): ["Later this evening.", "At the campus theater.", "Yes, let's go together.", "It's a popular band."],
        ("m1", 8): ["The cab ride takes about 30 minutes.", "I'm getting off at the next stop.", "At 6:45 P.M.", "Platform B."],
        ("m1", 9): ["Sure, let's look at some sculpture.", "I wish there were more pieces to see.", "It's the last week of the art exhibit.", "It will feature mostly French paintings."],
        ("m1", 10): ["The construction is loud.", "I set my alarm for 8 a.m.", "I heard the announcement.", "I don't have a favorite."],
        ("m1", 11): ["Several times every season.", "Sometimes it is very tiring.", "Yes, I prefer studying from home.", "The airport is busy in the mornings."],
        ("m1", 12): ["I usually eat dinner at 6 P.M.", "It was my first time there.", "Was he interesting?", "Yes, how about tomorrow?"],
        ("m1", 13): ["A lodge has no more guest spots.", "She has no hiking boots.", "A mountain road is closed.", "A campsite is closed for maintenance."],
        ("m1", 14): ["Bringing a backpack", "Taking a taxi", "Checking a weather report", "Buying waterproof boots"],
        ("m1", 15): ["It has a nice view.", "It is located near the university.", "The landlord is helpful.", "The lease terms are flexible."],
        ("m1", 16): ["Swim in the pool", "Tour a university museum", "Meet her neighbors", "See the landlord"],
        ("m1", 17): ["The very low ticket price", "The choice of songs", "The surprise introduction of a new album", "The performance"],
        ("m1", 18): ["She is not sure what time a concert will be.", "She did not have a great overall experience.", "She needs some information from the man.", "She is considering going to see a band again."],
        ("m1", 19): ["Students will get more information.", "Students must give a presentation.", "Students must attend a debate.", "Students will join the International Club."],
        ("m1", 20): ["International Fiction", "Business and Economics", "Speech and Debate", "Environmental Sustainability"],
        ("m1", 21): ["It depends on the day of the week.", "It is not the same for all types of equipment.", "It was decided based on student feedback.", "It will change soon."],
        ("m1", 22): ["A rule about reporting damage", "A rule about cleaning equipment after use", "A rule about wearing suitable clothing", "A rule about not using machines for too long"],
        ("m1", 23): ["A charge will not be applied.", "Bowling shoes will not be required.", "Teams can have six bowlers.", "Scores will not be kept."],
        ("m1", 24): ["Using a score-keeping system", "Selecting bowling shoes", "Joining a team", "Making a payment"],
        ("m1", 25): ["To highlight the importance of music in Ancient Greece", "To point out that Greek amphitheaters hosted a variety of gatherings", "To point out that the type of music played in Ancient Greece depended on the gathering", "To emphasize the skills of aulos players in Ancient Greece"],
        ("m1", 26): ["The size of its mouthpiece", "The thickness of its reeds", "The shape of its pipes", "The color of its body"],
        ("m1", 27): ["Constantly stopping and restarting air movement", "Inhaling and exhaling at the same time", "Keeping cheeks as round as possible", "Copying the method of playing a different instrument"],
        ("m1", 28): ["It began to be played together with other instruments.", "Its popularity decreased.", "The methods of playing it changed.", "The materials for making it changed."],
        ("m1", 29): ["A psychological technique designed to help people increase their attention span", "The tendency to not notice something happening around you when you are focused on something else", "The ability of some people to perform a surprisingly large number of tasks at the same time", "The large number of distractions in modern life"],
        ("m1", 30): ["Count basketball passes made by players", "Spot the person in the gorilla suit", "Predict the result of a game", "Stop the video when a player dropped the ball"],
        ("m1", 31): ["To better understand other people's behavior", "To avoid dangerous situations", "To improve focus on all tasks at once", "To avoid selective attention at work"],
        ("m1", 32): ["To identify a new study on inattentional blindness", "To suggest that inattentional blindness always involves sounds", "To explain that inattentional blindness is derived from a valuable ability", "To illustrate a way of avoiding inattentional blindness"],
        ("m2", 1): ["I'm late for ballet class.", "A friend gave me a novel.", "It was a great concert.", "The skies are cloudy today."],
        ("m2", 2): ["Somewhat frequently, I think.", "It was last week, actually.", "It's one of the largest campuses.", "Yes, I enjoyed the meal very much."],
        ("m2", 3): ["There will be three speakers.", "I don't know.", "At the hotel.", "I'm on my way."],
        ("m2", 4): ["It is free for students.", "It is closed on weekends.", "She previously worked at one.", "She knows the receptionist."],
        ("m2", 5): ["It is difficult to understand.", "It is long.", "He helped develop it.", "He just printed a copy of it."],
        ("m2", 6): ["Why he wants to buy a painting", "Why he has been very busy", "Why he will live close to a museum", "Why he needs the woman's help"],
        ("m2", 7): ["The absence of paintings by local artists", "The lack of variety among exhibited paintings", "The arrangement of paintings", "The schedule of the exhibition"],
        ("m2", 8): ["To measure memory skills of university students", "To study the effect of social pressure on behavior", "To compare visual judgments across cultures", "To determine study habits of university students"],
        ("m2", 9): ["Compare the lengths of different lines", "Draw lines on a card", "Work with a group to solve a problem", "Match words from two different lists"],
        ("m2", 10): ["They could not solve complex problems without help from others.", "They thought for a long time before answering a simple question.", "They used a variety of different strategies to solve a problem.", "They gave incorrect answers to match the answers of others at least once."],
        ("m2", 11): ["The number of participants in each group", "The number of times participants answered questions", "The cultural background of the participants", "The difficulty of the questions being answered"],
        ("m2", 12): ["A method for gathering data to inform decision-making models", "A guideline for making certain kinds of policy decisions", "The unintended consequences of conservation projects", "The importance of research in planning sensitive projects"],
        ("m2", 13): ["Increased tourism traffic and pollution", "Uncertainty surrounding the project's funding", "The possibility of disrupting animal migrations", "Opposition from local communities because of land disputes"],
        ("m2", 14): ["Waiting for scientific consensus before making a decision", "Acting decisively as soon as it has been established that harm has occurred", "Avoiding anything that risks serious harm even when the harm is not certain", "Avoiding unnecessary development projects in protected areas"],
        ("m2", 15): ["To consider a possible objection to the precautionary principle", "To illustrate the consequences of not applying the precautionary principle", "To describe a simpler version of the precautionary principle", "To explain the origin of the term precautionary principle"],
    },
    "LISTENING_STEM_OVERRIDES": {
        ("m1", 13): "What problem does the woman mention?", ("m1", 14): "What does the man recommend?", ("m1", 15): "Why does the woman like an apartment?", ("m1", 16): "What does the woman say she will do tomorrow?", ("m1", 17): "What did the woman like about the concert the most?", ("m1", 18): 'Why does the woman say: "I don\'t know"?', ("m1", 19): "What will happen on Monday?", ("m1", 20): "What class did this announcement likely occur in?", ("m1", 21): "What can be inferred about the gym schedule?", ("m1", 22): "What gym rule does the speaker emphasize?", ("m1", 23): "What one-time exception is being made?", ("m1", 24): "What does the speaker say the listeners should ask for help with?", ("m1", 25): "Why does the speaker mention religious ceremonies and athletic competitions?", ("m1", 26): "According to the speaker, what makes the aulos different from other wind instruments?", ("m1", 27): "What technique of playing the aulos does the speaker describe?", ("m1", 28): "What happened to the aulos over time?", ("m1", 29): "What does the speaker mainly discuss?", ("m1", 30): "In the classic study mentioned, what were participants asked to do?", ("m1", 31): "According to the speaker, why do we need to be aware of inattentional blindness?", ("m1", 32): "Why does the speaker mention a noisy office?", ("m2", 4): "What does the woman say about a campus health center?", ("m2", 5): "What does the man imply about a new checklist?", ("m2", 6): "What is the man explaining when he mentions his new apartment?", ("m2", 7): "What did the woman dislike about an exhibition?", ("m2", 8): "What was the main purpose of Solomon Asch's experiment?", ("m2", 9): "What were the participants in Asch's study asked to do?", ("m2", 10): "What was Asch's main finding about the majority of participants in his study?", ("m2", 11): "What difference between the Asch study and the study conducted in 1980 does the speaker discuss?", ("m2", 12): "What is the talk mainly about?", ("m2", 13): "What does the speaker say was the main concern with the proposed road project in Tanzania?", ("m2", 14): "According to the speaker, what does the precautionary principle emphasize?", ("m2", 15): "Why does the speaker mention asbestos?",
    },
    "LISTENING_PAGE_OVERRIDES": {**{("m1", n): 12 + ((n - 1) // 2) for n in range(1, 13)}, ("m1", 13): 20, ("m1", 14): 20, ("m1", 15): 21, ("m1", 16): 21, ("m1", 17): 22, ("m1", 18): 22, ("m1", 19): 24, ("m1", 20): 24, ("m1", 21): 25, ("m1", 22): 25, ("m1", 23): 27, ("m1", 24): 27, ("m1", 25): 28, ("m1", 26): 28, ("m1", 27): 29, ("m1", 28): 29, ("m1", 29): 30, ("m1", 30): 30, ("m1", 31): 31, ("m1", 32): 31, ("m2", 1): 34, ("m2", 2): 35, ("m2", 3): 36, ("m2", 4): 37, ("m2", 5): 37, ("m2", 6): 38, ("m2", 7): 38, ("m2", 8): 40, ("m2", 9): 40, ("m2", 10): 41, ("m2", 11): 41, ("m2", 12): 42, ("m2", 13): 43, ("m2", 14): 43, ("m2", 15): 44},
    "WRITING_ORDERED": {1: "I can't remember who wrote it .", 2: "Is it being held online or in person ?", 3: "do you have enough time to finish it before your class?", 4: "which brand are you considering ?", 5: "I had some technical issues with my computer .", 6: "I had a family gathering that I couldn't miss.", 7: "do you know if it's open to the public yet ?", 8: "do you know if the position requires experience ?", 9: "I had to finish my economics assignment .", 10: "do you know if any changes were suggested ?"},
    "WRITING_SENTENCE_ITEMS": {1: ("Who is the author of this novel?", ["wrote", "I", "can't", "who", "remember", "it", "."]), 2: ("I signed up for a psychology class this semester.", ["Is", "it", "held", "online", "or", "in", "person", "being", "?"]), 3: ("I need to finish reading this book for my literature class.", ["it", "before", "you", "do", "have", "enough", "time", "to", "finish", "your", "class?"]), 4: ("I'm thinking about getting a new laptop.", ["are", "?", "considering", "brand", "which", "you"]), 5: ("Why didn't you submit the book report on time?", ["technical", "some", "issues", "with", "I", "had", "my", "computer", "."]), 6: ("Why didn't you attend the biology lecture yesterday?", ["had", "I", "gathering", "that", "I", "couldn't", "a", "family", "miss."]), 7: ("I heard that the gallery has an exhibition of student work.", ["know", "if", "the", "do", "you", "public", "yet", "it's", "open", "to", "?"]), 8: ("There is a work study position in the athletic department.", ["you", "?", "requires", "experience", "the", "position", "if", "do", "know"]), 9: ("I saw you in the library yesterday.", ["my", "economics", "to", "finish", "I", "had", "assignment", "."]), 10: ("The club members and the faculty advisor approved the new policy.", ["know", "?", "any", "changes", "you", "were", "suggested", "if", "do"])},
    "WRITING_MANUAL_PROMPTS": {11: "You recently started a job on campus. Your academic advisor, Professor Patel, has been helpful in guiding you through your studies. However, you are finding it difficult to balance your work schedule with your academic commitments. Write an email to Professor Patel. Thank her for the support and guidance she has provided, discuss why you are having difficulty completing your academic commitments, and explain how you plan to balance your academic commitments and work plans. To: Professor Patel. Subject: Request to discuss academic and work balance. Write as much as you can and in complete sentences.", 12: "Your professor is teaching a class on educational psychology. Write a post responding to the professor's question. Dr. Gupta asks: We've been discussing the impact of different teaching methods on student learning. Some educational experts believe that project-based learning, which involves students working on projects over an extended period, is the most effective way to learn. Do you think project-based learning is beneficial for students? Why or why not? Paul believes project-based learning is highly beneficial because it encourages critical thinking, collaboration, and problem-solving skills, and students can apply what they learn in real-world scenarios. Claire believes project-based learning might not work for every student because some students may find it challenging to manage long-term projects and prefer traditional teaching methods. Express and support your opinion, contribute to the discussion in your own words, and write at least 100 words."},
    "WRITING_PAGES": {1: 44, 2: 45, 3: 45, 4: 46, 5: 46, 6: 47, 7: 47, 8: 48, 9: 48, 10: 49, 11: 50, 12: 51},
    "WRITING_FIXED_TEXT": {},
    "SPEAKING_REPEAT_AUDIO_TRANSCRIPT": ["Enter your name and student ID number.", "Browse the course catalog to choose your classes.", "You can use the schedule planner tool to avoid time conflicts.", "If a class is already full, a pop-up message will appear.", "Contact the instructor to see if more seats can be added.", "You can still add or drop classes up until the second week of the new semester.", "For your records, print out a list of your classes or email a copy to yourself."],
    "SPEAKING_INTERVIEW_AUDIO_TRANSCRIPT": ["To begin, do you have a hobby or interest that you regularly spend time doing?", "If you were to select a new hobby, what would you choose and why?", "Now tell me what might prevent you from starting this new pastime.", "Some people believe it is better to have one interest outside of work or school, that you dedicate yourself to, rather than multiple smaller ones. What do you think about that, and why?"],
    "SPEAKING_PAGES": {1: 53, 2: 54, 3: 54, 4: 55, 5: 55, 6: 56, 7: 56, 8: 57, 9: 58, 10: 59, 11: 60},
    "SPEAKING_CONTENT_STATUS": "reviewed_repair",
    "BLOCKED_REASON_BY_ITEM": {},
}


def configure_exam(progress_key: str) -> None:
    global ANSWER_EVIDENCE_OVERRIDES
    ANSWER_EVIDENCE_OVERRIDES = {}
    if progress_key == "2026-01-21-B":
        return
    if progress_key == "2026-01-21-C":
        globals().update(C_EXAM_CONFIG)
        return
    if progress_key == "2026-01-27-A":
        globals().update(A27_EXAM_CONFIG)
        return
    if progress_key == "2026-01-27-B":
        globals().update(A27_B_EXAM_CONFIG)
        return
    if progress_key == "2026-01-28-A":
        globals().update(A28_EXAM_CONFIG)
        return
    if progress_key == "2026-01-28-B":
        globals().update(B28_EXAM_CONFIG)
        return
    raise ValueError(f"Unsupported exam key: {progress_key}")


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duration_seconds(path: Path) -> float:
    output = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True,
    )
    return round(float(output.strip()), 3)


def source_ref(path: str, hashes: dict[str, str], *, page: int | None = None, module: str | None = None, number: int | None = None, confidence: str = "source_exact") -> dict[str, Any]:
    value: dict[str, Any] = {"path": path, "sha256": hashes[path], "confidence": confidence}
    if page:
        value["page"] = page
    if module:
        value["module"] = module
    if number:
        value["question_number"] = number
    return value


def answer_evidence(subject: str, module: str, number: int, page: int, hashes: dict[str, str], confidence: str) -> list[dict[str, Any]]:
    overrides = ANSWER_EVIDENCE_OVERRIDES.get((subject, module, number))
    if not overrides:
        return [
            source_ref(ANSWER_PDF, hashes, module=module, number=number),
            source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence),
        ]
    return [
        source_ref(
            item["path"],
            hashes,
            page=item.get("page"),
            module=module,
            number=number,
            confidence=item.get("confidence", "reviewed_repair"),
        )
        for item in overrides
    ]


def options(values: list[str]) -> list[dict[str, str]]:
    return [{"key": chr(65 + index), "text": text.strip()} for index, text in enumerate(values)]


def question_id(subject: str, module: str, group_index: int, number: int) -> str:
    return f"{EXAM_ID}:{subject}:{module}:g{group_index:02d}:q{number:02d}"


def module_id(subject: str, module: str) -> str:
    return f"{EXAM_ID}:{subject}:{module}"


def group_id(subject: str, module: str, group_index: int) -> str:
    return f"{EXAM_ID}:{subject}:{module}:g{group_index:02d}"


def normalize_text(text: str) -> str:
    text = text.replace("Al-", "AI-").replace("Al ", "AI ")
    text = text.replace("résumés", "resumes").replace("’", "'")
    text = re.sub(r"\s*< Back.*$", "", text)
    text = re.sub(r"\s*Review.*$", "", text)
    text = re.sub(r"\s*Begin >$", "", text)
    text = re.sub(r"\s*Next >.*$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def reading_page(module: str, number: int) -> int:
    if (module, number) in READING_PAGE_OVERRIDES:
        return READING_PAGE_OVERRIDES[(module, number)]
    if module == "m2":
        if number <= 10:
            return 11
        if number <= 11:
            return 11
        if number <= 14:
            return 12
        return 13
    if number <= 20:
        return 2
    if number <= 22:
        return 3
    if number <= 24:
        return 4
    if number <= 26:
        return 5
    if number <= 29:
        return 6
    if number <= 31:
        return 8
    if number <= 34:
        return 9
    return 10


def extracted_reading(source_root: Path) -> dict[tuple[str, int], dict[str, Any]]:
    extracted = json.loads((source_root / READING_CACHE).read_text(encoding="utf-8"))
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    current_module = "m1"
    for item in extracted:
        if item.get("kind") == "complete_words" and item.get("number") == 36:
            current_module = "m2"
            continue
        if READING_M2_START_PAGE is not None and item.get("page", 0) >= READING_M2_START_PAGE:
            current_module = "m2"
        elif READING_M2_START_PAGE is None and item.get("page", 0) >= 11:
            current_module = "m2"
        if item.get("kind") != "question":
            continue
        number = int(item.get("number") or 0)
        stem = item.get("stem", "")
        for (repair_module, source_number, stem_fragment), repaired_number in READING_NUMBER_REPAIRS.items():
            if current_module == repair_module and number == source_number and stem_fragment in stem:
                number = repaired_number
                break
        if current_module == "m1" and number > 1000 and "groundbreaking" in stem:
            number = 31
        if current_module == "m2" and number == 1 and "fossils" in stem:
            number = 15
        by_key[(current_module, number)] = item
    return by_key


def build_reading(source_root: Path, hashes: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_key = extracted_reading(source_root)
    modules: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    sequence = 0

    for module_order, module in enumerate(("m1", "m2"), 1):
        module_groups: list[str] = []
        for group_index, (first, last, task_type, title) in enumerate(READING_GROUPS[module], 1):
            gid = group_id("reading", module, group_index)
            qids = [question_id("reading", module, group_index, number) for number in range(first, last + 1)]
            module_groups.append(gid)
            page = reading_page(module, first)
            if task_type == "complete_words":
                stimulus = {
                    "format": "inline_completion",
                    "display_text": FILL_DISPLAY[f"{module}_{group_index:02d}"],
                    "token_syntax": "{question-local-number:visible-prefix}",
                    "rendering_rule": "Render each token as one inline text input; never detach blanks into a side panel.",
                }
                group_confidence = "reviewed_repair"
            else:
                candidates = [by_key.get((module, number), {}) for number in range(first, last + 1)]
                material = max((normalize_text(item.get("material", "")) for item in candidates), key=len, default="")
                stimulus = {"format": "rich_text", "text": material}
                group_confidence = "source_exact"
            groups.append({
                "id": gid,
                "module_id": module_id("reading", module),
                "subject": "reading",
                "order": group_index,
                "task_type": task_type,
                "title": title,
                "directive": "Fill in the missing letters in the paragraph." if task_type == "complete_words" else "Read the material and answer the questions.",
                "stimulus": stimulus,
                "question_ids": qids,
                "source_refs": [source_ref(PAPER, hashes, page=page, module=module, confidence=group_confidence), source_ref(READING_CACHE, hashes, module=module, confidence=group_confidence)],
            })

            for number in range(first, last + 1):
                sequence += 1
                qid = question_id("reading", module, group_index, number)
                page = reading_page(module, number)
                refs = [source_ref(PAPER, hashes, page=page, module=module, number=number), source_ref(READING_CACHE, hashes, module=module, number=number)]
                if task_type == "complete_words":
                    answer = READING_ANSWERS[module][number - 1]
                    prefix = FILL_PREFIXES[module][number - 1]
                    grading_blocked = (module, number) in GRADING_BLOCKED_READING
                    content_status = "reviewed_repair"
                    question = {
                        "id": qid,
                        "module_id": module_id("reading", module),
                        "group_id": gid,
                        "subject": "reading",
                        "number": number,
                        "sequence": sequence,
                        "response_type": "text",
                        "prompt": "Complete the missing letters in context.",
                        "options": [],
                        "input_config": {"visible_prefix": prefix, "input_kind": "missing_letters"},
                        "content_status": content_status,
                        "grading_status": "blocked" if grading_blocked else "auto",
                        "source_refs": [dict(ref, confidence="reviewed_repair") for ref in refs],
                    }
                    if not grading_blocked:
                        answers.append({
                            "question_id": qid,
                            "response_type": "text",
                            "canonical_text": answer,
                            "accepted_text": [answer],
                            "grading_status": "auto",
                            "evidence": answer_evidence("reading", module, number, page, hashes, "reviewed_repair"),
                        })
                elif (module, number) in BLOCKED_READING:
                    question = {
                        "id": qid,
                        "module_id": module_id("reading", module),
                        "group_id": gid,
                        "subject": "reading",
                        "number": number,
                        "sequence": sequence,
                        "response_type": "mc",
                        "prompt": "",
                        "options": [],
                        "input_config": {"selection": "single"},
                        "content_status": "missing_options",
                        "grading_status": "blocked",
                        "source_refs": [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence="source_missing"), source_ref(READING_CACHE, hashes, module=module, number=number, confidence="source_missing")],
                    }
                else:
                    override = READING_MC_OVERRIDES.get((module, number))
                    item = by_key.get((module, number), {})
                    confidence = "source_exact"
                    extra_sources: list[str] = []
                    if override:
                        stem = override["stem"]
                        raw_options = override["options"]
                        confidence = override.get("confidence", "reviewed_repair")
                        extra_sources = override.get("extra_sources", [])
                    else:
                        stem = normalize_text(item.get("stem", ""))
                        raw_options = [normalize_text(value) for value in item.get("options", [])]
                    source_refs = [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence), source_ref(READING_CACHE, hashes, module=module, number=number, confidence=confidence)]
                    source_refs.extend(source_ref(path, hashes, module=module, number=number, confidence=confidence) for path in extra_sources)
                    if len(raw_options) != 4:
                        raise ValueError(f"reading {module} q{number} has {len(raw_options)} options after recovery")
                    grading_blocked = (module, number) in GRADING_BLOCKED_READING
                    question = {
                        "id": qid,
                        "module_id": module_id("reading", module),
                        "group_id": gid,
                        "subject": "reading",
                        "number": number,
                        "sequence": sequence,
                        "response_type": "mc",
                        "prompt": stem,
                        "options": options(raw_options),
                        "input_config": {"selection": "single"},
                        "content_status": "reviewed_repair" if confidence != "source_exact" else "ready",
                        "grading_status": "blocked" if grading_blocked else "auto",
                        "source_refs": source_refs,
                    }
                    if not grading_blocked:
                        answers.append({
                            "question_id": qid,
                            "response_type": "mc",
                            "correct_option_keys": [READING_ANSWERS[module][number - 1]],
                            "grading_status": "auto",
                            "evidence": answer_evidence("reading", module, number, page, hashes, confidence),
                        })
                questions.append(question)

        modules.append({
            "id": module_id("reading", module),
            "subject": "reading",
            "module": module,
            "order": module_order,
            "label": f"Reading Module {module_order}",
            "duration_seconds": 1200 if module == "m1" else 600,
            "navigation": {"back_policy": "within_module", "review_policy": "within_module"},
            "asset_ids": [f"{EXAM_ID}:paper"],
            "group_ids": module_groups,
        })
    return modules, groups, questions, answers


def extract_exam_section(path: Path, heading: str, *, stop_marker: str | None = None) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index(heading)
    if stop_marker:
        end = text.index(stop_marker, start)
    else:
        match = re.search(r"\n## ", text[start + len(heading):])
        end = len(text) if not match else start + len(heading) + match.start()
    return text[start:end]


def is_listening_noise(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped in {"Talk", "Play", "Next >", "< Back", "Continue >", "Vol Begin >", "Begi", "文", "ai", "\\", "|"}:
        return True
    patterns = [
        r"^\[第 \d+ 页\]", r"^2026", r"^Home", r"^Review", r"^eview", r"^i olume", r"^模块",
        r"^Listening$", r"^Listening Section", r"^In the listening", r"^There are three",
        r"^Listen and Choose", r"^a Response", r"^Conversations", r"^Announcements", r"^and Academic",
        r"^You WILL", r"^Module ?[12]", r"^In an actual", r"^You can use", r"^The first task",
        r"^sentence or question", r"^Conversation, Announcement", r"^You will listen",
        r"^Choose the best response", r"0:00/", r"^O[e—_一-]", r"^Qe", r"^Ce", r"^Coe", r"^Ci\)",
        r"^@", r"^[=\-—_<>\"“”'`\\/\\s]+$", r"^\w*\s*模块",
    ]
    return any(re.search(pattern, stripped) for pattern in patterns)


def strip_option_bullet(text: str) -> str:
    value = re.sub(r"^(©|CO|O)\s*", "", text.strip())
    replacements = {
        "Mytuition": "My tuition",
        "Ilike": "I like",
        "Atleast": "At least",
        "Ihave": "I have",
        "Ialready": "I already",
        "Ishould": "I should",
        "Avery": "A very",
        "Aplace": "A place",
        "Aparking": "A parking",
        "Achange": "A change",
        "Anew": "A new",
        "Afine": "A fine",
        "Asmall": "A small",
        "Aset": "A set",
        "Acooking": "A cooking",
        "Agiftfor": "A gift for",
        "Itis": "It is",
        "Itled": "It led",
        "Atype": "A type",
        "Abuilding": "A building",
        "Adesign": "A design",
        "Aresearch": "A research",
        "Ihaveno": "I have no",
        "Idon't": "I don't",
        "1didn't": "I didn't",
        "I'Ilgive": "I'll give",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = value.replace("A<gift", "A gift").replace("|", "I").replace("’", "'")
    return normalize_text(value)


def is_option_start(text: str) -> bool:
    stripped = text.strip()
    return bool(re.match(r"^(©|CO|O)\s*\S+", stripped)) and not is_listening_noise(stripped)


def parse_listening_block(lines: list[str]) -> tuple[str, list[str]]:
    stem_parts: list[str] = []
    parsed_options: list[str] = []
    current_option: str | None = None
    seen_option = False
    for raw in lines:
        stripped = raw.strip()
        if is_listening_noise(stripped):
            continue
        if is_option_start(stripped):
            if current_option:
                parsed_options.append(current_option)
            current_option = strip_option_bullet(stripped)
            seen_option = True
            continue
        if seen_option and current_option:
            current_option = f"{current_option} {strip_option_bullet(stripped)}".strip()
        elif not stripped.lower().startswith("listen to"):
            stem_parts.append(stripped)
    if current_option:
        parsed_options.append(current_option)
    return normalize_text(" ".join(stem_parts)), [normalize_text(value) for value in parsed_options]


def parse_listening_markdown(source_root: Path) -> dict[tuple[str, int], tuple[str, list[str]]]:
    section = extract_exam_section(
        source_root / LISTENING_MD,
        LISTENING_SECTION_HEADING,
        stop_marker=LISTENING_SECTION_STOP_MARKER,
    )
    question_re = re.compile(r"^Listening Question\s+(\d+)\s*of\s*(\d+)", re.I)
    by_key: dict[tuple[str, int], tuple[str, list[str]]] = {}
    current: tuple[str, int] | None = None
    lines: list[str] = []

    def flush() -> None:
        if not current:
            return
        stem, parsed_options = parse_listening_block(lines)
        if parsed_options:
            by_key[current] = (stem, parsed_options)

    for line in section.splitlines():
        normalized_line = line.strip().replace("1of", "1 of")
        match = question_re.match(normalized_line)
        if match:
            flush()
            total = int(match.group(2))
            current = ("m1" if total == 32 else "m2", int(match.group(1)))
            lines = []
        elif current:
            lines.append(line)
    flush()
    for key, override in LISTENING_OPTION_OVERRIDES.items():
        stem = LISTENING_STEM_OVERRIDES.get(key, by_key.get(key, ("", []))[0])
        by_key[key] = (stem, override)
    for key, stem in LISTENING_STEM_OVERRIDES.items():
        by_key.setdefault(key, (stem, []))
    return by_key


def parse_listening_prompts(source_root: Path) -> dict[tuple[str, int], str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required to parse the TOEFL transcript PDF") from exc

    reader = PdfReader(str(source_root / TRANSCRIPT_PDF))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    prompts: dict[tuple[str, int], str] = {}
    module = "m1"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Module2"):
            module = "m2"
            continue
        match = re.match(r"^(\d+)\.\s*(.+)$", stripped)
        if match:
            number = int(match.group(1))
            upper = LISTENING_PROMPT_UPPER[module]
            if 1 <= number <= upper:
                prompts[(module, number)] = normalize_text(match.group(2))
    return prompts


def listening_page(module: str, number: int) -> int:
    if (module, number) in LISTENING_PAGE_OVERRIDES:
        return LISTENING_PAGE_OVERRIDES[(module, number)]
    if module == "m2":
        if number == 1:
            return 43
        if number == 2:
            return 44
        if number == 3:
            return 45
        if number <= 5:
            return 47
        if number <= 7:
            return 49
        if number == 8:
            return 50
        if number <= 10:
            return 51
        if number == 11:
            return 52
        if number <= 13:
            return 53
        return 54
    if number <= 12:
        return 13 + number
    if number <= 14:
        return 27 if number == 13 else 28
    if number <= 16:
        return 30
    if number <= 18:
        return 32
    if number <= 20:
        return 33 if number == 19 else 34
    if number <= 22:
        return 35
    if number <= 24:
        return 36 if number == 23 else 37
    if number <= 26:
        return 38
    if number <= 28:
        return 39
    if number == 29:
        return 40
    if number <= 31:
        return 41
    return 42


def build_listening(source_root: Path, hashes: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    parsed = parse_listening_markdown(source_root)
    prompts = parse_listening_prompts(source_root)
    modules: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    sequence = 0

    for module_order, module in enumerate(("m1", "m2"), 1):
        module_groups: list[str] = []
        for group_index, (first, last, task_type, title) in enumerate(LISTENING_GROUPS[module], 1):
            gid = group_id("listening", module, group_index)
            qids = [question_id("listening", module, group_index, number) for number in range(first, last + 1)]
            module_groups.append(gid)
            groups.append({
                "id": gid,
                "module_id": module_id("listening", module),
                "subject": "listening",
                "order": group_index,
                "task_type": task_type,
                "title": title,
                "directive": "Listen once, then choose the best answer.",
                "stimulus": {"format": "audio", "asset_id": f"{EXAM_ID}:listening:{module}", "transcript_policy": "review_after_submit"},
                "question_ids": qids,
                "source_refs": [source_ref(PAPER, hashes, page=listening_page(module, first), module=module), source_ref(LISTENING_MD, hashes, module=module), source_ref(TRANSCRIPT_PDF, hashes, module=module)],
            })
            for number in range(first, last + 1):
                sequence += 1
                qid = question_id("listening", module, group_index, number)
                missing_options_blocked = (module, number) in BLOCKED_LISTENING
                grading_blocked = (module, number) in GRADING_BLOCKED_LISTENING
                stem, raw_options = parsed.get((module, number), ("", []))
                if task_type == "listen_and_choose":
                    prompt = prompts.get((module, number), "")
                else:
                    prompt = stem
                if missing_options_blocked:
                    raw_options = []
                elif len(raw_options) != 4:
                    raise ValueError(f"listening {module} q{number} has {len(raw_options)} options after parsing")
                page = listening_page(module, number)
                confidence = "source_missing" if missing_options_blocked else ("reviewed_repair" if (module, number) in LISTENING_OPTION_OVERRIDES or grading_blocked else "source_exact")
                question = {
                    "id": qid,
                    "module_id": module_id("listening", module),
                    "group_id": gid,
                    "subject": "listening",
                    "number": number,
                    "sequence": sequence,
                    "response_type": "mc",
                    "prompt": prompt,
                    "options": options(raw_options),
                    "input_config": {"selection": "single", "audio_replay_policy": "once_in_test_mode", "audio_scrub_policy": "disabled_in_test_mode"},
                    "content_status": "missing_options" if missing_options_blocked else ("reviewed_repair" if confidence == "reviewed_repair" else "ready"),
                    "grading_status": "blocked" if missing_options_blocked or grading_blocked else "auto",
                    "source_refs": [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence), source_ref(LISTENING_MD, hashes, module=module, number=number, confidence=confidence), source_ref(TRANSCRIPT_PDF, hashes, module=module, number=number)],
                }
                questions.append(question)
                if not missing_options_blocked and not grading_blocked:
                    answers.append({
                        "question_id": qid,
                        "response_type": "mc",
                        "correct_option_keys": [LISTENING_ANSWERS[module][number - 1]],
                        "grading_status": "auto",
                        "evidence": answer_evidence("listening", module, number, page, hashes, confidence),
                    })
        modules.append({
            "id": module_id("listening", module),
            "subject": "listening",
            "module": module,
            "order": module_order,
            "label": f"Listening Module {module_order}",
            "duration_seconds": int(round(duration_seconds(source_root / (LISTENING_M1_AUDIO if module == "m1" else LISTENING_M2_AUDIO)))),
            "navigation": {"back_policy": "disabled", "review_policy": "after_submit"},
            "asset_ids": [f"{EXAM_ID}:listening:{module}"],
            "group_ids": module_groups,
        })
    return modules, groups, questions, answers


def tokenize_ordered(sentence: str) -> list[str]:
    return sentence.split()


def clean_scramble(scramble: list[str], ordered: list[str]) -> list[str]:
    remaining = Counter(ordered)
    cleaned: list[str] = []
    for token in scramble:
        token = "I" if token == "|" else token
        if remaining[token] > 0:
            cleaned.append(token)
            remaining[token] -= 1
    for token in ordered:
        if remaining[token] > 0:
            cleaned.append(token)
            remaining[token] -= 1
    return cleaned


def build_writing(hashes: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    module = "m1"
    mid = module_id("writing", module)
    group_specs = [(1, 10, "build_a_sentence", "Build a Sentence"), (11, 11, "write_email", "Write an Email"), (12, 12, "academic_discussion", "Academic Discussion")]
    groups: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    group_lookup: dict[int, tuple[int, str]] = {}
    for group_index, (first, last, task_type, title) in enumerate(group_specs, 1):
        gid = group_id("writing", module, group_index)
        for number in range(first, last + 1):
            group_lookup[number] = (group_index, gid)
        groups.append({
            "id": gid,
            "module_id": mid,
            "subject": "writing",
            "order": group_index,
            "task_type": task_type,
            "title": title,
            "directive": "Arrange the words to make an appropriate sentence." if task_type == "build_a_sentence" else "Write a complete response to the prompt.",
            "stimulus": None,
            "question_ids": [question_id("writing", module, group_index, number) for number in range(first, last + 1)],
            "source_refs": [source_ref(PAPER, hashes, page=WRITING_PAGES[first], module=module), source_ref(WRITING_MD, hashes, module=module)],
        })

    for number in range(1, 13):
        group_index, gid = group_lookup[number]
        qid = question_id("writing", module, group_index, number)
        page = WRITING_PAGES[number]
        if number <= 10:
            context, scramble_source = WRITING_SENTENCE_ITEMS[number]
            ordered = tokenize_ordered(WRITING_ORDERED[number])
            scramble = clean_scramble(scramble_source, ordered)
            status = "reviewed_repair" if Counter(scramble_source) != Counter(scramble) else "ready"
            confidence = "reviewed_repair" if status == "reviewed_repair" else "source_exact"
            input_config = {"scramble_tokens": scramble, "keyboard_reorder": True}
            fixed_text = WRITING_FIXED_TEXT.get(number)
            if fixed_text:
                input_config["fixed_text"] = fixed_text
            questions.append({
                "id": qid,
                "module_id": mid,
                "group_id": gid,
                "subject": "writing",
                "number": number,
                "sequence": number,
                "response_type": "order",
                "prompt": "Make an appropriate sentence for the situation.",
                "context_sentence": context,
                "options": [],
                "input_config": input_config,
                "content_status": status,
                "grading_status": "auto",
                "source_refs": [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence), source_ref(WRITING_MD, hashes, module=module, number=number, confidence=confidence)],
            })
            answers.append({
                "question_id": qid,
                "response_type": "order",
                "ordered_tokens": ordered,
                "grading_status": "auto",
                "evidence": [source_ref(ANSWER_PDF, hashes, module=module, number=number), source_ref(PAPER, hashes, page=page, module=module, number=number, confidence=confidence)],
            })
        else:
            questions.append({
                "id": qid,
                "module_id": mid,
                "group_id": gid,
                "subject": "writing",
                "number": number,
                "sequence": number,
                "response_type": "free_text",
                "prompt": WRITING_MANUAL_PROMPTS[number],
                "options": [],
                "input_config": {"minimum_words": 100 if number == 12 else 0, "autosave": True},
                "content_status": "reviewed_repair",
                "grading_status": "manual",
                "source_refs": [source_ref(PAPER, hashes, page=page, module=module, number=number, confidence="reviewed_repair"), source_ref(WRITING_MD, hashes, module=module, number=number, confidence="reviewed_repair")],
            })
    modules = [{
        "id": mid,
        "subject": "writing",
        "module": module,
        "order": 1,
        "label": "Writing",
        "duration_seconds": 1020,
        "navigation": {"back_policy": "within_module", "review_policy": "within_module"},
        "asset_ids": [f"{EXAM_ID}:paper"],
        "group_ids": [group["id"] for group in groups],
    }]
    return modules, groups, questions, answers


def build_speaking(hashes: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    groups: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    modules: list[dict[str, Any]] = []
    specs = [
        ("m1", 1, 7, "listen_and_repeat", "Listen and Repeat", SPEAKING_REPEAT_AUDIO_TRANSCRIPT),
        ("m2", 8, 11, "take_an_interview", "Take an Interview", SPEAKING_INTERVIEW_AUDIO_TRANSCRIPT),
    ]
    for module_order, (module, first, last, task_type, title, prompts) in enumerate(specs, 1):
        mid = module_id("speaking", module)
        gid = group_id("speaking", module, 1)
        qids = [question_id("speaking", module, 1, number) for number in range(first, last + 1)]
        groups.append({
            "id": gid,
            "module_id": mid,
            "subject": "speaking",
            "order": 1,
            "task_type": task_type,
            "title": title,
            "directive": "Record one response for each prompt.",
            "stimulus": {"format": "audio", "asset_id": f"{EXAM_ID}:speaking", "recording_policy": "one_take_in_test_mode"},
            "question_ids": qids,
            "source_refs": [source_ref(PAPER, hashes, page=SPEAKING_PAGES[first], module=module, confidence="reviewed_repair"), source_ref(SPEAKING_AUDIO, hashes, module=module), source_ref(SPEAKING_TRANSCRIPT_JSON, hashes, module=module, confidence="reviewed_repair")],
        })
        for offset, number in enumerate(range(first, last + 1)):
            prompt = prompts[offset]
            questions.append({
                "id": question_id("speaking", module, 1, number),
                "module_id": mid,
                "group_id": gid,
                "subject": "speaking",
                "number": number,
                "sequence": len(questions) + 1,
                "response_type": "recording",
                "prompt": "Listen and repeat only once." if task_type == "listen_and_repeat" else prompt,
                "context_sentence": prompt if task_type == "listen_and_repeat" else "Answer the interviewer question after listening.",
                "options": [],
                "input_config": {"maximum_takes_test_mode": 1, "local_preview_practice_mode": True},
                "content_status": SPEAKING_CONTENT_STATUS,
                "grading_status": "manual",
                "source_refs": [source_ref(PAPER, hashes, page=SPEAKING_PAGES[number], module=module, number=number, confidence="reviewed_repair"), source_ref(SPEAKING_AUDIO, hashes, module=module, number=number), source_ref(SPEAKING_TRANSCRIPT_JSON, hashes, module=module, number=number, confidence="reviewed_repair")],
            })
        modules.append({
            "id": mid,
            "subject": "speaking",
            "module": module,
            "order": module_order,
            "label": title,
            "duration_seconds": 420 if module == "m1" else 540,
            "navigation": {"back_policy": "disabled", "review_policy": "after_submit"},
            "asset_ids": [f"{EXAM_ID}:speaking"],
            "group_ids": [gid],
        })
    return modules, groups, questions


def build_assets(source_root: Path, hashes: dict[str, str]) -> list[dict[str, Any]]:
    specs = [
        (f"{EXAM_ID}:paper", "paper_pdf", "exam", PAPER, None, None),
        (f"{EXAM_ID}:answers", "answer_pdf", "exam", ANSWER_PDF, None, None),
        (f"{EXAM_ID}:listening-transcript", "transcript_pdf", "listening", TRANSCRIPT_PDF, None, None),
        (f"{EXAM_ID}:listening:m1", "audio", "listening", LISTENING_M1_AUDIO, module_id("listening", "m1"), duration_seconds(source_root / LISTENING_M1_AUDIO)),
        (f"{EXAM_ID}:listening:m2", "audio", "listening", LISTENING_M2_AUDIO, module_id("listening", "m2"), duration_seconds(source_root / LISTENING_M2_AUDIO)),
        (f"{EXAM_ID}:speaking", "audio", "speaking", SPEAKING_AUDIO, None, duration_seconds(source_root / SPEAKING_AUDIO)),
    ]
    assets: list[dict[str, Any]] = []
    for asset_id, kind, subject, path_value, linked_module, duration in specs:
        source: dict[str, Any] = {"path": path_value, "sha256": hashes[path_value], "size_bytes": (source_root / path_value).stat().st_size}
        if duration is not None:
            source["duration_seconds"] = duration
        asset: dict[str, Any] = {
            "id": asset_id,
            "kind": kind,
            "subject": subject,
            "source": source,
            "delivery": {"storage_key": f"toefl/v2/{EXAM_KEY}/{Path(path_value).name}", "status": "local_source"},
        }
        if linked_module:
            asset["module_id"] = linked_module
        assets.append(asset)
    return assets


def load_validator(repo_root: Path):
    path = repo_root / "scripts/validate_toefl_practice_v2.py"
    spec = importlib.util.spec_from_file_location("validate_toefl_practice_v2", path)
    module = importlib.util.module_from_spec(spec)
    if not spec.loader:
        raise RuntimeError("validator module loader unavailable")
    spec.loader.exec_module(module)
    return module


def update_progress(repo_root: Path, output_root: Path, generated_at: str, counts: dict[str, Any], validation_summary: dict[str, Any], validation_errors: list[str]) -> None:
    progress_path = output_root / "rebuild_progress.json"
    if not progress_path.is_file():
        return
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    has_blockers = bool(validation_errors) or counts.get("blocked", 0) > 0
    rebuild_status = "review_required" if has_blockers else "ready_for_reintegration"
    validation_status = "validation_failed" if validation_errors else ("passed_with_blocked_source_items" if counts.get("blocked", 0) else "passed")
    for row in progress.get("exams", []):
        if row.get("exam_key") == PROGRESS_KEY:
            row.update({
                "rebuild_status": rebuild_status,
                "validation_status": validation_status,
                "v2_package": str((output_root / EXAM_KEY).relative_to(repo_root)),
                "counts": counts,
                "notes": PROGRESS_NOTES,
            })
            break
    rows = progress.get("exams", [])
    progress["generated_at"] = generated_at
    progress["summary"] = {
        "exam_sets": len(rows),
        "pilot_built": sum(row.get("rebuild_status") == "pilot_built" for row in rows),
        "review_required": sum(row.get("rebuild_status") == "review_required" for row in rows),
        "ready_for_reintegration": sum(row.get("rebuild_status") == "ready_for_reintegration" for row in rows),
        "queued": sum(row.get("rebuild_status") == "queued" for row in rows),
        "validation_passed_or_blocked": sum(str(row.get("validation_status", "")).startswith("passed") for row in rows),
    }
    json_dump(progress_path, progress)

    ready_path = output_root / "reintegration_readiness_report.md"
    report = "# TOEFL v2 reintegration readiness\n\n"
    report += f"Generated: {generated_at}\n\n"
    report += "## Release gate\n\n"
    report += "A set may enter the StudyTracker catalog only when every expected atomic question exists, source evidence is recorded, auto-graded items have private answer entries, no answer leaks into public content, media is verified, and no item is falsely marked ready.\n\n"
    report += "## Current status\n\n"
    report += f"- Inventory: {len(rows)} real-exam sets.\n"
    report += f"- v2 packages with validation pass/blocker-aware pass: {progress['summary']['validation_passed_or_blocked']}.\n"
    report += f"- Review required: {progress['summary']['review_required']}.\n"
    report += f"- Ready for reintegration: {progress['summary']['ready_for_reintegration']}.\n"
    report += f"- Remaining queue: {progress['summary']['queued']}.\n\n"
    report += "## Latest package\n\n"
    report += f"- {PROGRESS_KEY}: {validation_summary.get('questions', 0)} questions; {validation_summary.get('auto', 0)} auto, {validation_summary.get('manual', 0)} manual, {validation_summary.get('blocked', 0)} blocked.\n"
    report += f"- Blockers: {LATEST_BLOCKER_TEXT}\n"
    ready_path.write_text(report, encoding="utf-8")


def build_package(repo_root: Path, source_root: Path, output_root: Path) -> dict[str, Any]:
    package_dir = output_root / EXAM_KEY
    generated_at = datetime.now(UTC).isoformat()
    source_paths = [
        PAPER, ANSWER_PDF, TRANSCRIPT_PDF, LISTENING_M1_AUDIO, LISTENING_M2_AUDIO, SPEAKING_AUDIO,
        READING_CACHE, *READING_EXTRA_SOURCE_PATHS, LISTENING_MD, WRITING_MD, SPEAKING_MD, SPEAKING_TRANSCRIPT_JSON,
    ]
    source_paths.extend(
        item["path"]
        for evidence in ANSWER_EVIDENCE_OVERRIDES.values()
        for item in evidence
    )
    source_paths = list(dict.fromkeys(source_paths))
    for path_value in source_paths:
        if not (source_root / path_value).is_file():
            raise FileNotFoundError(source_root / path_value)
    hashes = {path_value: file_hash(source_root / path_value) for path_value in source_paths}

    reading_modules, reading_groups, reading_questions, reading_answers = build_reading(source_root, hashes)
    listening_modules, listening_groups, listening_questions, listening_answers = build_listening(source_root, hashes)
    writing_modules, writing_groups, writing_questions, writing_answers = build_writing(hashes)
    speaking_modules, speaking_groups, speaking_questions = build_speaking(hashes)
    questions = reading_questions + listening_questions + writing_questions + speaking_questions
    counts = {
        "questions": len(questions),
        "auto": sum(item["grading_status"] == "auto" for item in questions),
        "manual": sum(item["grading_status"] == "manual" for item in questions),
        "blocked": sum(item["grading_status"] == "blocked" for item in questions),
        "by_subject": {subject: sum(item["subject"] == subject for item in questions) for subject in ("reading", "listening", "writing", "speaking")},
    }
    content = {
        "schema_version": "2.0.0",
        "exam": {
            "id": EXAM_ID,
            "title": EXAM_TITLE,
            "date": EXAM_DATE,
            "variant": EXAM_VARIANT,
            "source_kind": "real_exam",
            "source_folder": SOURCE_FOLDER,
            "expected_question_count": 120,
            "availability_status": "blocked" if counts["blocked"] else "reviewed",
        },
        "assets": build_assets(source_root, hashes),
        "modules": reading_modules + listening_modules + writing_modules + speaking_modules,
        "groups": reading_groups + listening_groups + writing_groups + speaking_groups,
        "questions": questions,
    }
    blocked_items = [item for item in questions if item["grading_status"] == "blocked"]
    answer_key = {
        "schema_version": "2.0.0",
        "exam_id": EXAM_ID,
        "visibility": "private_server_only",
        "answers": reading_answers + listening_answers + writing_answers,
        "manual_grading": [item["id"] for item in questions if item["grading_status"] == "manual"],
        "blocked": [
            {
                "question_id": item["id"],
                "reason": BLOCKED_REASON_BY_ITEM.get((item["subject"], item["module_id"].rsplit(":", 1)[-1], item["number"]), "Required source content is missing or incomplete; exclude from auto-grading denominator."),
            }
            for item in blocked_items
        ],
    }
    manifest = {
        "schema_version": "2.0.0",
        "exam_id": EXAM_ID,
        "generated_at": generated_at,
        "generator": "scripts/build_toefl_practice_v2_exam.py",
        "source_root_portability": "All source paths are relative to the configured source root.",
        "counts": counts,
        "quality": {
            "validation_status": "pending_validator",
            "publish_status": "blocked" if counts["blocked"] else "ready",
            "subject_reviews": {
                "reading": "pending",
                "listening": "pending",
                "writing": "pending",
                "speaking": "pending",
            },
            "blocking_reasons": BLOCKING_REASONS,
            "known_blocked_question_ids": [item["id"] for item in blocked_items],
        },
    }
    qa_report = {
        "schema_version": "1.0.0",
        "exam_id": EXAM_ID,
        "generated_at": generated_at,
        "counts": counts,
        "source_evidence": {
            "questions_with_source_refs": sum(bool(item.get("source_refs")) for item in questions),
            "questions_total": len(questions),
            "answer_entries_with_evidence": sum(bool(item.get("evidence")) for item in reading_answers + listening_answers + writing_answers),
            "answer_entries_total": len(reading_answers + listening_answers + writing_answers),
        },
        "media_coverage": {
            "audio_assets_expected": 3,
            "audio_assets_readable": sum(
                asset.get("kind") == "audio" and asset.get("source", {}).get("duration_seconds", 0) > 0
                for asset in build_assets(source_root, hashes)
            ),
        },
        "blockers": BLOCKING_REASONS,
        "checks": QA_CHECK_SPECS,
    }
    json_dump(package_dir / "content.json", content)
    json_dump(package_dir / "answer_key.json", answer_key)
    json_dump(package_dir / "manifest.json", manifest)
    json_dump(package_dir / "qa_report.json", qa_report)

    validator = load_validator(repo_root)
    errors, validation_summary = validator.validate_package(package_dir, repo_root / "schemas/toefl_practice_v2.schema.json", source_root)
    manifest["quality"]["validation_status"] = "validation_failed" if errors else ("passed_with_blocked_source_items" if blocked_items else "passed")
    if errors:
        manifest["quality"]["publish_status"] = "blocked"
    json_dump(package_dir / "manifest.json", manifest)
    release_blockers = (
        []
        if errors
        else validator.release_blockers(
            content,
            answer_key,
            manifest,
            validation_summary,
        )
    )
    report_base = {
        "schema_version": "1.0.0",
        "validated_at": datetime.now(UTC).isoformat(),
        "package_dir": validator.portable_package_path(package_dir),
        "source_root_checked": True,
        "summary": validation_summary,
        "errors": errors,
    }
    json_dump(
        package_dir / "validation_result.json",
        {
            **report_base,
            "status": "fail" if errors else "pass",
            "release_gate_checked": False,
            "release_ready": not errors and not release_blockers,
            "release_blockers": release_blockers,
        },
    )
    json_dump(
        package_dir / "release_gate_report.json",
        {
            **report_base,
            "status": "fail" if errors else ("blocked" if release_blockers else "pass"),
            "release_gate_checked": True,
            "release_ready": not errors and not release_blockers,
            "release_blockers": release_blockers,
        },
    )
    for check in qa_report["checks"]:
        if check["id"] == "answer-separation":
            check["status"] = "pass" if not errors else "fail"
            check["detail"] = "Validator found no public answer leakage." if not errors else "Validator found package errors; see validation_report.json."
    qa_report["validation_summary"] = validation_summary
    qa_report["validation_errors"] = errors
    json_dump(package_dir / "qa_report.json", qa_report)
    update_progress(repo_root, output_root, generated_at, counts, validation_summary, errors)
    return {"package": str(package_dir), "counts": counts, "validation_errors": errors}


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--exam-key", default=PROGRESS_KEY, choices=["2026-01-21-B", "2026-01-21-C", "2026-01-27-A", "2026-01-27-B", "2026-01-28-A", "2026-01-28-B"])
    parser.add_argument("--source-root", type=Path, default=Path("/Users/zhouxin/Desktop/新托福资料"))
    parser.add_argument("--output-root", type=Path, default=repo_root / "data/toefl_practice_v2")
    args = parser.parse_args()
    configure_exam(args.exam_key)
    result = build_package(repo_root, args.source_root.resolve(), args.output_root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["validation_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
