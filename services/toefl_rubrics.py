"""Concise, auditable labels for the 2026 TOEFL task-level rubrics.

The official guides are copyrighted.  This module keeps short Chinese working
anchors and focus items for the teacher UI rather than reproducing the guides.
Scores remain task-level integers from 0 through 5; this module deliberately
does not contain any 1-6 conversion.
"""

from __future__ import annotations

from typing import Any

RUBRIC_VERSION = "2026-01"
TASK_SCORE_MIN = 0
TASK_SCORE_MAX = 5

_RUBRICS: dict[str, dict[str, Any]] = {
    "listen_and_repeat": {
        "code": "toefl_2026_speaking_listen_and_repeat",
        "version": RUBRIC_VERSION,
        "title": "Listen and Repeat · 2026 口语任务级量表",
        "summary": "重点看复述保真、完整度和可懂度，不按访谈题的论证标准评分。",
        "focus": ["保留原句意义与词形", "是否完整成句", "清晰度、词序和功能词"],
        "anchors": {
            0: "无有效英文作答、完全听不懂或与原句无关",
            1: "只说出少量词语，大部分内容缺失或整体难懂",
            2: "缺少重要部分，意义断裂，整体可懂度低",
            3: "大体完成且是完整句，但意义或词项多处失真",
            4: "基本保留意义，有少量词汇、语法、词形或发音偏差",
            5: "完整、准确复述原句，表达清晰可懂",
        },
    },
    "take_an_interview": {
        "code": "toefl_2026_speaking_take_an_interview",
        "version": RUBRIC_VERSION,
        "title": "Take an Interview · 2026 口语任务级量表",
        "summary": "重点看切题回应、有效展开、语言准确度和口语交付，不机械平均维度。",
        "focus": ["直接回应问题并保持切题", "理由、例子或细节是否有效展开", "流畅度、可懂度、语法和词汇准确性"],
        "anchors": {
            0: "无有效英文作答、完全听不懂或与问题无关",
            1: "只与问题模糊相关，主要是孤立词语或短语且多半难懂",
            2: "尝试回应但缺少有意义展开，意思常难辨且语言很有限",
            3: "基本切题但展开或清晰度有限，停顿、填充或语言限制影响表达",
            4: "切题且有展开，整体清楚流畅，偶发问题不妨碍理解",
            5: "完整切题、展开充分、表达流畅清楚，语言准确且可懂度高",
        },
    },
    "write_email": {
        "code": "toefl_2026_writing_write_an_email",
        "version": RUBRIC_VERSION,
        "title": "Write an Email · 2026 写作任务级量表",
        "summary": "重点看沟通目的、要求覆盖、信息展开、语域礼貌和语言控制。",
        "focus": ["覆盖情境与每项要求", "信息是否有效支持沟通目的", "收件人语域、礼貌、组织与语言准确性"],
        "anchors": {
            0: "空白、拒答、非英语、全抄题面、无关或乱码",
            1: "信息极少或电报式，错误严重频繁，原创表达很少",
            2: "尝试完成但效果有限，展开有限或无关，错误累积影响理解",
            3: "大体完成任务，但部分信息不清或不充分，语言或社交规范有明显问题",
            4: "基本有效且易懂，展开和语域大多合适，仅有少量错误",
            5: "有效完成沟通目的，展开充分，语域礼貌合适，语言准确自然",
        },
    },
    "academic_discussion": {
        "code": "toefl_2026_writing_academic_discussion",
        "version": RUBRIC_VERSION,
        "title": "Write for an Academic Discussion · 2026 写作任务级量表",
        "summary": "重点看独立且切题的贡献、解释例证细节的有效展开和语言控制。",
        "focus": ["提出独立、相关的观点", "解释、例证或细节是否真正展开观点", "句法多样、措辞准确，避免只改写题面或他人观点"],
        "anchors": {
            0: "空白、拒答、非英语、全抄题面、无关或乱码",
            1: "只有词语或短语，几乎没有连贯观点，错误严重频繁",
            2: "尝试参与但观点展开差或仅部分相关，语言限制使思路难跟",
            3: "大体相关易懂，但部分解释、例子或细节缺失、不清或无关",
            4: "相关且易懂，有充分但不总是充分的展开，语言总体合适",
            5: "相关且贡献清晰，解释例证细节展开充分，语言准确自然",
        },
    },
}


def rubric_for_task_type(task_type: str | None) -> dict[str, Any] | None:
    """Return a copy-safe rubric descriptor for a manual task type."""

    rubric = _RUBRICS.get(str(task_type or "").strip().lower())
    if rubric is None:
        return None
    return {
        **rubric,
        "focus": list(rubric["focus"]),
        "anchors": dict(rubric["anchors"]),
        "max_score": TASK_SCORE_MAX,
    }


def rubric_code_for_task_type(task_type: str | None) -> str | None:
    rubric = _RUBRICS.get(str(task_type or "").strip().lower())
    return rubric["code"] if rubric else None
