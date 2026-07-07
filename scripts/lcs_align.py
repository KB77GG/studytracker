"""Global monotonic (LCS-based) forced alignment for complete reference text.

The greedy anchor-window aligner in batch_align_ielts.py works well when the
ASR transcription is dense, but drifts badly when whisper under-transcribes a
region (it loses the anchor and either grabs a far-future word or dumps the
rest into a tail distribution). For jfdr6 we have the *complete, ordered* book
transcript, so a global longest-common-subsequence match between book words
and whisper words is far more robust: well-transcribed spans anchor exactly,
and sentences whose words whisper missed get interpolated between their
neighbours' anchors instead of drifting across the whole file.

Public entry point: align_sentences(sentences, whisper_words, audio_duration).
"""

from __future__ import annotations

import re


def _norm(text: str) -> list[str]:
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return text.split()


def _lcs_match(book: list[str], asr: list[str]) -> dict[int, int]:
    """Return {book_word_index: asr_word_index} for a longest common subsequence.

    Hirschberg would be O(n) memory but n,m ~ 900 here so the plain O(nm) DP
    table (~800k ints) is fine and much simpler.
    """
    n, m = len(book), len(asr)
    # dp[i][j] = LCS length of book[i:] and asr[j:]
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row, nxt = dp[i], dp[i + 1]
        bi = book[i]
        for j in range(m - 1, -1, -1):
            if bi == asr[j]:
                row[j] = nxt[j + 1] + 1
            else:
                row[j] = nxt[j] if nxt[j] >= row[j + 1] else row[j + 1]
    match: dict[int, int] = {}
    i = j = 0
    while i < n and j < m:
        if book[i] == asr[j]:
            match[i] = j
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return match


def align_sentences(
    sentences: list[str],
    whisper_words: list[dict],
    audio_duration: float,
) -> list[dict]:
    """Align each sentence to a [start, end] window via global LCS.

    sentences: display/plain sentence strings, in audio order (1:1 output).
    whisper_words: [{"word","start","end"}] flattened, in time order.
    Returns [{"id","start","end","text"}] with one entry per sentence.
    """
    asr_words = [_norm(w["word"])[0] if _norm(w["word"]) else "" for w in whisper_words]
    asr_times = [(float(w["start"]), float(w["end"])) for w in whisper_words]

    # Flatten book into words with their owning sentence index.
    book_words: list[str] = []
    owner: list[int] = []
    for si, sent in enumerate(sentences):
        for w in _norm(sent):
            book_words.append(w)
            owner.append(si)

    match = _lcs_match(book_words, asr_words) if book_words and asr_words else {}

    # Per-sentence: collect matched asr times.
    sent_starts: list[float | None] = [None] * len(sentences)
    sent_ends: list[float | None] = [None] * len(sentences)
    for bi, ai in match.items():
        si = owner[bi]
        s, e = asr_times[ai]
        if sent_starts[si] is None or s < sent_starts[si]:
            sent_starts[si] = s
        if sent_ends[si] is None or e > sent_ends[si]:
            sent_ends[si] = e

    # Enforce monotonic anchors: a matched sentence start must not precede the
    # previous matched sentence start (LCS is monotonic so this rarely fires,
    # but guards against a stray early match).
    last = -1.0
    for si in range(len(sentences)):
        if sent_starts[si] is not None:
            if sent_starts[si] < last:
                sent_starts[si] = last
            last = sent_starts[si]

    # Interpolate sentences with no matched words between neighbouring anchors.
    anchors = [si for si in range(len(sentences)) if sent_starts[si] is not None]
    segments: list[dict] = []
    if not anchors:
        # Degenerate: spread evenly.
        slot = audio_duration / max(1, len(sentences))
        for si, sent in enumerate(sentences):
            segments.append({"id": si + 1, "start": round(si * slot, 2),
                             "end": round((si + 1) * slot, 2), "text": sent})
        return segments

    first_anchor, last_anchor = anchors[0], anchors[-1]
    for si, sent in enumerate(sentences):
        if sent_starts[si] is not None:
            start = sent_starts[si]
            end = sent_ends[si] if sent_ends[si] and sent_ends[si] > start else start + 0.5
        else:
            # Find bracketing anchors.
            prev = max((a for a in anchors if a < si), default=None)
            nxt = min((a for a in anchors if a > si), default=None)
            if prev is None:
                # Before first anchor: back off from it.
                span = sent_starts[first_anchor]
                slot = span / max(1, first_anchor + 1)
                start = si * slot
                end = start + slot
            elif nxt is None:
                # After last anchor: spread to audio end.
                base = sent_ends[last_anchor] or sent_starts[last_anchor]
                remaining = len(sentences) - last_anchor - 1
                slot = max(1.0, (audio_duration - base) / max(1, remaining))
                start = base + (si - last_anchor) * slot
                end = start + slot
            else:
                # Between two anchors: even split of the gap.
                gap_start = sent_ends[prev] or sent_starts[prev]
                gap_end = sent_starts[nxt]
                between = nxt - prev
                slot = (gap_end - gap_start) / max(1, between)
                start = gap_start + (si - prev) * slot
                end = start + slot
        if audio_duration:
            cap = audio_duration - 0.05
            start = min(start, cap)
            end = min(max(end, start), cap)
        segments.append({"id": si + 1, "start": round(start, 2),
                         "end": round(end, 2), "text": sentences[si]})
    return segments
