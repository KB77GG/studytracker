"""Task-image upload validation and storage (the tool's own upload directory)."""

from __future__ import annotations

import secrets
from pathlib import Path

SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
)


class UploadError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def sniff_image(head: bytes) -> tuple[str, str] | None:
    for signature, mime, ext in SIGNATURES:
        if head.startswith(signature):
            return mime, ext
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def save_image(file_storage, upload_dir: Path, user_id: int, max_bytes: int) -> tuple[str, str]:
    """Validate by content (not by filename) and save; returns (relative_path, mime)."""
    data = file_storage.read(max_bytes + 1)
    if not data:
        raise UploadError("image_empty", "题图文件为空")
    if len(data) > max_bytes:
        raise UploadError("image_too_large", f"题图不能超过 {max_bytes // (1024 * 1024)} MB")
    sniffed = sniff_image(data[:16])
    if not sniffed:
        raise UploadError("image_type", "题图只支持 PNG、JPG 或 WEBP")
    mime, ext = sniffed
    relative = Path(str(int(user_id))) / f"{secrets.token_hex(16)}.{ext}"
    target = Path(upload_dir) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return relative.as_posix(), mime


def resolve(upload_dir: Path, relative: str) -> Path | None:
    """Resolve a stored relative path, refusing anything outside the upload dir."""
    base = Path(upload_dir).resolve()
    candidate = (base / relative).resolve()
    if base not in candidate.parents or not candidate.is_file():
        return None
    return candidate


def remove(upload_dir: Path, relative: str | None) -> None:
    if not relative:
        return
    path = resolve(upload_dir, relative)
    if path is not None:
        path.unlink(missing_ok=True)
