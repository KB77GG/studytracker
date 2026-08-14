"""Public playback URLs for dictionary audio exposed to clients."""

from __future__ import annotations

import hashlib


def word_tts_playback_url(word) -> str | None:
    """Return a stable API URL when a dictionary word has bound audio."""
    word_id = getattr(word, "id", None)
    audio_path = getattr(word, "audio_us", None) or getattr(word, "audio_uk", None)
    if not word_id or not audio_path:
        return None
    version = hashlib.sha256(str(audio_path).encode("utf-8")).hexdigest()[:12]
    return f"/dictation/words/{word_id}/tts?v={version}"
