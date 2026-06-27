"""共享文本归一化工具（纯函数，只依赖标准库）。

从 api/miniprogram.py 下沉至此，便于在零依赖单测中复用。
注意：只收敛**逐字节相同**的辅助函数；entrance.py / materials.py 里
那两个**逻辑分叉**的 _normalize_question_options 不在此处合并。
"""

import re


def _normalize_objective_answer(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[‘’`]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^[\W_]+|[\W_]+$", "", text)
    return text


def _objective_answer_alternatives(answer: str) -> set[str]:
    raw = str(answer or "").strip()
    if not raw:
        return set()
    parts = re.split(r"\s*(?:/|\||\bor\b)\s*", raw, flags=re.IGNORECASE)
    return {_normalize_objective_answer(part) for part in parts if _normalize_objective_answer(part)}
