"""Cache public Ninefen media under content hashes without changing exam data.

The importer owns HTML sanitization and publication. This module rejects active
or externally loaded HTML resources, downloads only the observed public media
origin, and returns a map only after *every* referenced asset validates. Failure
may leave harmless immutable files, never a partially published exam/manifest.
"""

from __future__ import annotations

import hashlib
import html
import http.client
import json
import math
import os
import re
import struct
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser
from pathlib import Path

from services.ninefen_source import verified_https_handler

UNIT_ID = re.compile(r"[0-9]{1,24}\Z")
ASSET_NAME = re.compile(r"[a-f0-9]{64}\.(?:mp3|png|jpg|gif|webp)\Z")
PUBLIC_PREFIX = "/practice/sprint/assets"

MEDIA_ORIGIN = "static.9fnnn.com"
MAX_AUDIO_BYTES = 40 * 1024 * 1024
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_EXAM_BYTES = 80 * 1024 * 1024
MAX_ASSETS = 64
MAX_ATTEMPTS = 3
SUFFIX_TYPES = {
    ".mp3": "audio/mpeg",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
MEDIA_FIELDS = {"audioUrl", "exAudioUrl", "image", "imageUrl", "imgUrl", "img_url", "poster"}


class NinefenAssetError(ValueError):
    """An exam's media cannot safely be used as a complete local asset set."""


def validate_media_url(url: str) -> str:
    if not isinstance(url, str) or not url or any(ord(char) <= 32 for char in url):
        raise NinefenAssetError("Invalid media URL")
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise NinefenAssetError("Invalid media URL") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != MEDIA_ORIGIN
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/practice/[A-Za-z0-9_./-]+", parsed.path)
        or any(piece in (".", "..") for piece in parsed.path.split("/"))
    ):
        raise NinefenAssetError("Media URL is outside the public media scope")
    expected = SUFFIX_TYPES.get(Path(parsed.path).suffix.lower())
    if expected is None:
        raise NinefenAssetError("Unsupported public media format")
    return expected


class _HTMLMedia(HTMLParser):
    """Inspect resource-bearing HTML without executing or rendering any markup."""

    def __init__(self, add):
        super().__init__(convert_charrefs=True)
        self.add = add

    def handle_starttag(self, tag, attributes):
        if tag in {
            "script",
            "iframe",
            "embed",
            "object",
            "svg",
            "math",
            "link",
            "base",
            "style",
            "video",
        }:
            raise NinefenAssetError("Active or unsupported HTML media")
        for key, value in attributes:
            value = value or ""
            if key.startswith("on") or key in {"srcdoc", "srcset"}:
                raise NinefenAssetError("Unsupported HTML resource attribute")
            if re.match(r"\s*(javascript|vbscript|data):", html.unescape(value), re.I):
                raise NinefenAssetError("Unsafe HTML resource URL")
            if key in {"src", "poster"}:
                if tag not in {"img", "audio", "source"}:
                    raise NinefenAssetError("Unsupported HTML media element")
                self.add(value)
            if key == "background":
                self.add(value)
            if key == "style":
                if "\\" in value or re.search(
                    r"@import|expression\s*\(|behavior\s*:|-moz-binding|image-set\s*\(", value, re.I
                ):
                    raise NinefenAssetError("Unsafe CSS resource")
                for match in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", value, re.I):
                    self.add(match.group(2))
                if re.search(r"url\s*\(", value, re.I) and not re.search(r"url\(.*\)", value, re.I):
                    raise NinefenAssetError("Malformed CSS media URL")

    handle_startendtag = handle_starttag


def collect_exam_media(payload: dict) -> list[str]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get("parts"), list):
        raise NinefenAssetError("Expected a complete public exam response")
    urls = {}

    def add(url):
        validate_media_url(url)
        urls[url] = None
        if len(urls) > MAX_ASSETS:
            raise NinefenAssetError("Too many assets in one exam")

    def walk(value):
        if isinstance(value, dict):
            if "url" in value and value.get("assetType") in {"audio", "image"}:
                add(value["url"])
            for key, child in value.items():
                if key in MEDIA_FIELDS and child not in (None, ""):
                    add(child)
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str) and "<" in value:
            parser = _HTMLMedia(add)
            parser.feed(value)
            parser.close()

    walk(data)
    return list(urls)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NinefenAssetError("Media redirects are not permitted")


def _fetch_bytes(url: str, *, max_bytes: int, timeout: float) -> tuple[bytes, str]:
    opener = urllib.request.build_opener(_NoRedirect(), verified_https_handler())
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "StudyTracker-PublicHotlist/1.0", "Accept": "image/*,audio/mpeg"},
    )
    for attempt in range(MAX_ATTEMPTS):
        try:
            with opener.open(request, timeout=timeout) as response:
                if response.geturl() != url:
                    raise NinefenAssetError("Unexpected media response origin")
                content_length = response.headers.get("Content-Length")
                try:
                    length = int(content_length) if content_length is not None else None
                except ValueError as exc:
                    raise NinefenAssetError("Invalid media response length") from exc
                if length is not None and not 0 < length <= max_bytes:
                    raise NinefenAssetError("Media response exceeds the size limit")
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes or (length is not None and len(raw) != length):
                    raise NinefenAssetError("Media response is oversized or incomplete")
                return raw, response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        except urllib.error.HTTPError as exc:
            exc.close()
            if exc.code not in {429, 500, 502, 503, 504} or attempt == MAX_ATTEMPTS - 1:
                raise NinefenAssetError(f"Public media HTTP failure ({exc.code})") from exc
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
            if attempt == MAX_ATTEMPTS - 1:
                raise NinefenAssetError("Public media is unavailable") from exc
        time.sleep(attempt + 1)
    raise NinefenAssetError("Public media is unavailable")


def _valid_png(raw: bytes) -> bool:
    offset, saw_data = 8, False
    while offset + 12 <= len(raw):
        size = int.from_bytes(raw[offset : offset + 4], "big")
        end = offset + 12 + size
        if end > len(raw):
            return False
        kind = raw[offset + 4 : offset + 8]
        body = raw[offset + 8 : end - 4]
        if zlib.crc32(kind + body) & 0xFFFFFFFF != int.from_bytes(raw[end - 4 : end], "big"):
            return False
        if offset == 8:
            if kind != b"IHDR" or size != 13:
                return False
            width, height = struct.unpack(">II", body[:8])
            if not 0 < width <= 20000 or not 0 < height <= 20000:
                return False
        if kind == b"IDAT":
            saw_data = True
        if kind == b"IEND":
            return size == 0 and saw_data and end == len(raw)
        offset = end
    return False


def _mp3_frame_length(raw: bytes, offset: int) -> int:
    if offset + 4 > len(raw):
        return 0
    a, b, c, _ = raw[offset : offset + 4]
    version, layer = (b >> 3) & 3, (b >> 1) & 3
    bitrate, frequency = (c >> 4) & 15, (c >> 2) & 3
    if (
        a != 255
        or b & 224 != 224
        or version == 1
        or layer != 1
        or bitrate in (0, 15)
        or frequency == 3
    ):
        return 0
    rates = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
    if version != 3:
        rates = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
    sample_rate = (44100, 48000, 32000)[frequency] // {3: 1, 2: 2, 0: 4}[version]
    return ((144 if version == 3 else 72) * rates[bitrate] * 1000 // sample_rate) + ((c >> 1) & 1)


def _valid_mp3(raw: bytes) -> bool:
    offset = 0
    if raw.startswith(b"ID3"):
        if len(raw) < 10 or any(value & 128 for value in raw[6:10]):
            return False
        offset = 10 + sum(
            value << shift for value, shift in zip(raw[6:10], (21, 14, 7, 0), strict=True)
        )
    for start in range(offset, min(offset + 4096, len(raw) - 4)):
        length = _mp3_frame_length(raw, start)
        if length and _mp3_frame_length(raw, start + length) and start + length * 2 <= len(raw):
            return True
    return False


def validate_media_bytes(raw: bytes, expected_type: str, content_type: str = "") -> str:
    """Validate bounded file structure, returning a safe canonical extension."""
    if not isinstance(raw, bytes) or not raw:
        raise NinefenAssetError("Empty or invalid media data")
    detected = None
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and _valid_png(raw):
        detected = ("image/png", ".png")
    elif raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9") and len(raw) >= 32:
        detected = ("image/jpeg", ".jpg")
    elif raw[:6] in (b"GIF87a", b"GIF89a") and raw.endswith(b";") and len(raw) >= 14:
        width, height = struct.unpack("<HH", raw[6:10])
        if 0 < width <= 20000 and 0 < height <= 20000:
            detected = ("image/gif", ".gif")
    elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP" and len(raw) >= 20:
        if int.from_bytes(raw[4:8], "little") + 8 == len(raw) and raw[12:16] in {
            b"VP8 ",
            b"VP8L",
            b"VP8X",
        }:
            detected = ("image/webp", ".webp")
    elif expected_type == "audio/mpeg" and _valid_mp3(raw):
        detected = ("audio/mpeg", ".mp3")
    if detected is None or detected[0] != expected_type:
        raise NinefenAssetError("Media bytes do not match the expected format")
    if not isinstance(content_type, str):
        raise NinefenAssetError("Invalid media content type")
    declared = content_type.lower().split(";", 1)[0]
    declared = {"audio/mp3": "audio/mpeg", "image/jpg": "image/jpeg"}.get(declared, declared)
    if declared not in {"", "application/octet-stream", "binary/octet-stream", expected_type}:
        raise NinefenAssetError("Media response content type does not match its bytes")
    return detected[1]


def _store_immutable(directory: Path, filename: str, raw: bytes, digest: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename

    def verify_existing():
        if (
            destination.is_symlink()
            or hashlib.sha256(destination.read_bytes()).hexdigest() != digest
        ):
            raise NinefenAssetError("Existing content-addressed asset is corrupt")

    if destination.exists() or destination.is_symlink():
        verify_existing()
        return
    fd, temporary = tempfile.mkstemp(prefix=".asset-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            verify_existing()
    finally:
        os.unlink(temporary)


def cache_exam_assets(
    payload: dict,
    cache_root: str | Path,
    *,
    public_prefix: str = "/practice/sprint/assets",
    timeout: float = 20,
    fetcher=None,
) -> dict:
    """Return ``{media_map, assets}``; keep the original payload byte-for-byte.

    An injectable fetcher has the same keyword contract as ``_fetch_bytes`` and
    returns ``(bytes, content_type)``. The final byte checks also apply to it.
    ``cache_root`` is a trusted caller-owned directory, never derived from a URL.
    """
    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or not math.isfinite(timeout)
        or not 0 < timeout <= 60
    ):
        raise NinefenAssetError("Invalid media timeout")
    if not re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+", public_prefix):
        raise NinefenAssetError("Invalid local media prefix")
    urls = collect_exam_media(payload)
    download = fetcher or _fetch_bytes
    assets, media_map, total_bytes = [], {}, 0
    for url in urls:
        expected = validate_media_url(url)
        limit = MAX_AUDIO_BYTES if expected.startswith("audio/") else MAX_IMAGE_BYTES
        raw, mime = download(url, max_bytes=limit, timeout=timeout)
        if not isinstance(raw, bytes) or len(raw) > limit:
            raise NinefenAssetError("Media asset exceeds the size limit")
        total_bytes += len(raw)
        if total_bytes > MAX_EXAM_BYTES:
            raise NinefenAssetError("Exam media exceeds the aggregate size limit")
        suffix = validate_media_bytes(raw, expected, mime)
        digest = hashlib.sha256(raw).hexdigest()
        filename = digest + suffix
        _store_immutable(Path(cache_root), filename, raw, digest)
        public_url = public_prefix + "/" + filename
        media_map[url] = public_url
        assets.append(
            {
                "source_url": url,
                "filename": filename,
                "sha256": digest,
                "mime_type": expected,
                "byte_count": len(raw),
                "public_url": public_url,
            }
        )
    return {"media_map": media_map, "assets": assets}


def _atomic_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".media-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verified_media_manifest(payload: dict, path: Path, cache_root: Path) -> dict | None:
    """Return a complete hash-bound manifest only if all immutable files still verify."""
    from services.exam_sprint import content_digest

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        urls = collect_exam_media(payload)
        if (
            manifest.get("schema_version") != 1
            or manifest.get("unit_id") != payload["data"]["id"]
            or manifest.get("source_content_sha256") != content_digest(payload)
            or set(manifest.get("media_map", {})) != set(urls)
            or len(manifest.get("assets", [])) != len(urls)
        ):
            return None
        seen = set()
        for asset in manifest["assets"]:
            url, filename = asset["source_url"], asset["filename"]
            if url not in urls or url in seen or not ASSET_NAME.fullmatch(filename):
                return None
            seen.add(url)
            expected = validate_media_url(url)
            file = cache_root / filename
            limit = MAX_AUDIO_BYTES if expected.startswith("audio/") else MAX_IMAGE_BYTES
            if file.is_symlink() or not file.is_file() or file.stat().st_size > limit:
                return None
            raw = file.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if (
                asset.get("sha256") != digest
                or filename
                != digest + validate_media_bytes(raw, expected, asset.get("mime_type", ""))
                or asset.get("byte_count") != len(raw)
                or asset.get("public_url") != PUBLIC_PREFIX + "/" + filename
                or manifest["media_map"][url] != asset["public_url"]
            ):
                return None
        return manifest
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def cache_unit_media(
    payload: dict, cache_root: Path, manifest_root: Path, *, refresh: bool = False, fetcher=None
) -> tuple[dict, bool]:
    """Prepare media for an already validated public exam; return manifest and reused flag."""
    from services.exam_sprint import content_digest

    unit_id = payload["data"]["id"]
    if not isinstance(unit_id, str) or not UNIT_ID.fullmatch(unit_id):
        raise NinefenAssetError("Invalid public unit identity")
    path = manifest_root / f"{unit_id}.json"
    existing = None if refresh else verified_media_manifest(payload, path, cache_root)
    if existing is not None:
        return existing, True
    media = cache_exam_assets(payload, cache_root, public_prefix=PUBLIC_PREFIX, fetcher=fetcher)
    manifest = {
        "schema_version": 1,
        "unit_id": unit_id,
        "source_content_sha256": content_digest(payload),
        **media,
    }
    _atomic_manifest(path, manifest)
    return manifest, False
