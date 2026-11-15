"""Bounded public-media reads, integrity checks and immutable cache behavior."""

import copy
import hashlib
import json
import struct
import tempfile
import unittest
import urllib.error
import zlib
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.cache_exam_sprint_media import cache_unit_media, verified_media_manifest
from services.ninefen_assets import (
    NinefenAssetError,
    _fetch_bytes,
    _NoRedirect,
    cache_exam_assets,
    collect_exam_media,
    validate_media_bytes,
    validate_media_url,
)

IMAGE_URL = "https://static.9fnnn.com/practice/group/123/image/456.png"
AUDIO_URL = "https://static.9fnnn.com/practice/part/123/audio/456.mp3"


def png_bytes():
    def chunk(kind, body):
        return (
            struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


def mp3_bytes():
    # Two structurally complete MPEG1/Layer3 frames at 128 kbps, 44.1 kHz.
    return (b"\xff\xfb\x90\x00" + b"\x00" * 413) * 2


def exam(*urls):
    return {
        "data": {
            "parts": [
                {
                    "assets": [
                        {"assetType": "audio" if url.endswith("mp3") else "image", "url": url}
                        for url in urls
                    ]
                }
            ]
        }
    }


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "assets"

    def test_media_map_hash_and_original_payload_are_stable(self):
        payload = exam(IMAGE_URL, AUDIO_URL)
        before = json.dumps(payload)

        def fake(url, **_):
            return (mp3_bytes(), "audio/mpeg") if url == AUDIO_URL else (png_bytes(), "image/png")

        result = cache_exam_assets(payload, self.root, fetcher=fake)
        self.assertEqual(json.dumps(payload), before)
        self.assertEqual(len(result["assets"]), 2)
        for row in result["assets"]:
            raw = (self.root / row["filename"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"])
            self.assertEqual(len(raw), row["byte_count"])
            self.assertEqual(result["media_map"][row["source_url"]], row["public_url"])
            self.assertTrue(row["public_url"].startswith("/practice/sprint/assets/"))

    def test_duplicate_fields_download_once(self):
        payload = exam(IMAGE_URL)
        payload["data"]["parts"][0].update(
            image=IMAGE_URL, imageUrl=IMAGE_URL, article=f'<img src="{IMAGE_URL}">'
        )
        fetcher = Mock(return_value=(png_bytes(), "image/png"))
        cache_exam_assets(payload, self.root, fetcher=fetcher)
        self.assertEqual(fetcher.call_count, 1)

    def test_all_urls_validate_before_any_download(self):
        fetcher = Mock()
        with self.assertRaises(NinefenAssetError):
            cache_exam_assets(
                exam(IMAGE_URL, "https://evil.invalid/steal.png"), self.root, fetcher=fetcher
            )
        fetcher.assert_not_called()
        self.assertFalse(self.root.exists())

    def test_url_scope_blocks_credential_redirect_and_traversal_inputs(self):
        for url in [
            "http://static.9fnnn.com/practice/a.png",
            "https://user:password@static.9fnnn.com/practice/a.png",
            "https://static.9fnnn.com:444/practice/a.png",
            "https://static.9fnnn.com.evil.invalid/practice/a.png",
            "https://static.9fnnn.com/practice/../secret.png",
            "https://static.9fnnn.com/practice/%2e%2e/secret.png",
            "https://static.9fnnn.com/practice/a.png?token=x",
            "https://static.9fnnn.com/practice/a.png#fragment",
            "//static.9fnnn.com/practice/a.png",
            "https://static.9fnnn.com/practice/a.svg",
        ]:
            with self.subTest(url=url), self.assertRaises(NinefenAssetError):
                validate_media_url(url)

    def test_html_cannot_smuggle_external_media_or_active_content(self):
        for markup in [
            '<img src="https://evil.invalid/a.png">',
            '<img srcset="https://evil.invalid/a.png 2x">',
            '<iframe src="https://evil.invalid/"></iframe>',
            '<img onerror="alert(1)">',
            "<script>alert(1)</script>",
            '<a href="javascript:alert(1)">x</a>',
            '<div style="background:url(https://evil.invalid/a.png)">x</div>',
            '<table background="https://evil.invalid/a.png"></table>',
            "<div style=\"background:image-set('https://evil.invalid/a.png' 1x)\">x</div>",
            '<div style="background:u\\72l(https://evil.invalid/a.png)">x</div>',
        ]:
            with self.subTest(markup=markup), self.assertRaises(NinefenAssetError):
                collect_exam_media({"data": {"parts": [{"article": markup}]}})

    def test_public_inline_images_and_audio_are_collected(self):
        payload = {
            "data": {
                "parts": [
                    {
                        "contentHtml": f'<p style="background:url({IMAGE_URL})">a</p><audio src="{AUDIO_URL}"></audio>'
                    }
                ]
            }
        }
        self.assertEqual(collect_exam_media(payload), [IMAGE_URL, AUDIO_URL])

    def test_second_asset_failure_never_returns_partial_manifest(self):
        payload = exam(IMAGE_URL, AUDIO_URL)
        original = copy.deepcopy(payload)
        fetcher = Mock(side_effect=[(png_bytes(), "image/png"), TimeoutError("offline")])
        with self.assertRaises(TimeoutError):
            cache_exam_assets(payload, self.root, fetcher=fetcher)
        self.assertEqual(payload, original)
        self.assertEqual(len(list(self.root.glob("*.png"))), 1)
        self.assertEqual(list(self.root.glob(".asset-*")), [])
        self.assertFalse((self.root / "current.json").exists())

    def test_hash_cache_is_reused_but_never_overwrites_corruption(self):
        fetcher = Mock(return_value=(png_bytes(), "image/png"))
        first = cache_exam_assets(exam(IMAGE_URL), self.root, fetcher=fetcher)
        path = self.root / first["assets"][0]["filename"]
        stat = path.stat()
        cache_exam_assets(exam(IMAGE_URL), self.root, fetcher=fetcher)
        self.assertEqual(path.stat().st_mtime_ns, stat.st_mtime_ns)
        path.write_bytes(b"corrupt")
        with self.assertRaisesRegex(NinefenAssetError, "corrupt"):
            cache_exam_assets(exam(IMAGE_URL), self.root, fetcher=fetcher)
        self.assertEqual(path.read_bytes(), b"corrupt")

    def test_existing_asset_symlink_is_rejected(self):
        raw = png_bytes()
        self.root.mkdir()
        outside = self.root.parent / "outside"
        outside.write_bytes(raw)
        (self.root / (hashlib.sha256(raw).hexdigest() + ".png")).symlink_to(outside)
        with self.assertRaises(NinefenAssetError):
            cache_exam_assets(
                exam(IMAGE_URL), self.root, fetcher=lambda *_, **__: (raw, "image/png")
            )

    def test_bounded_injected_download_and_aggregate_budget(self):
        def fake(*_, **__):
            return png_bytes(), "image/png"

        with (
            patch("services.ninefen_assets.MAX_IMAGE_BYTES", 8),
            self.assertRaises(NinefenAssetError),
        ):
            cache_exam_assets(exam(IMAGE_URL), self.root, fetcher=fake)
        with (
            patch("services.ninefen_assets.MAX_EXAM_BYTES", len(png_bytes()) + 1),
            self.assertRaises(NinefenAssetError),
        ):
            cache_exam_assets(
                exam(IMAGE_URL, IMAGE_URL.replace("456", "789")), self.root, fetcher=fake
            )

    def test_empty_html_mime_and_truncated_files_are_rejected(self):
        for raw, expected, declared in [
            (b"", "image/png", "image/png"),
            (b"<html>not audio</html>", "audio/mpeg", "audio/mpeg"),
            (png_bytes(), "image/png", "text/html"),
            (png_bytes()[:-5], "image/png", "image/png"),
            (mp3_bytes()[:300], "audio/mpeg", "audio/mpeg"),
            (png_bytes(), "audio/mpeg", "audio/mpeg"),
        ]:
            with (
                self.subTest(expected=expected, declared=declared, size=len(raw)),
                self.assertRaises(NinefenAssetError),
            ):
                validate_media_bytes(raw, expected, declared)

    def test_png_crc_corruption_is_rejected(self):
        raw = bytearray(png_bytes())
        raw[40] ^= 1
        with self.assertRaises(NinefenAssetError):
            validate_media_bytes(bytes(raw), "image/png")

    def test_invalid_prefix_and_timeout_do_not_fetch(self):
        for options in [
            {"public_prefix": "//evil.invalid"},
            {"public_prefix": "/../data"},
            {"timeout": float("nan")},
            {"timeout": "20"},
            {"timeout": True},
        ]:
            with self.subTest(options=options), self.assertRaises(NinefenAssetError):
                cache_exam_assets(exam(IMAGE_URL), self.root, **options)

    def test_missing_assets_are_valid_without_creating_cache(self):
        self.assertEqual(cache_exam_assets(exam(), self.root), {"media_map": {}, "assets": []})
        self.assertFalse(self.root.exists())

    def test_redirect_handler_does_not_follow_a_new_origin(self):
        with self.assertRaises(NinefenAssetError):
            _NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid/x")

    def test_http_download_retries_transient_failures_with_bound(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.geturl.return_value = IMAGE_URL
        response.headers = {"Content-Length": str(len(png_bytes())), "Content-Type": "image/png"}
        response.read.return_value = png_bytes()
        opener = Mock()
        opener.open.side_effect = [
            urllib.error.URLError("temporary"),
            urllib.error.URLError("temporary"),
            response,
        ]
        with (
            patch("services.ninefen_assets.urllib.request.build_opener", return_value=opener),
            patch("services.ninefen_assets.time.sleep"),
        ):
            raw, mime = _fetch_bytes(IMAGE_URL, max_bytes=1024, timeout=20)
        self.assertEqual((raw, mime), (png_bytes(), "image/png"))
        self.assertEqual(opener.open.call_count, 3)
        response.read.assert_called_once_with(1025)

    def test_response_length_mismatch_is_not_cached(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.geturl.return_value = IMAGE_URL
        response.headers = {"Content-Length": "100", "Content-Type": "image/png"}
        response.read.return_value = b"partial"
        opener = Mock()
        opener.open.return_value = response
        with (
            patch("services.ninefen_assets.urllib.request.build_opener", return_value=opener),
            self.assertRaisesRegex(NinefenAssetError, "incomplete"),
        ):
            _fetch_bytes(IMAGE_URL, max_bytes=1024, timeout=20)

    def test_unit_manifest_resume_requires_source_and_blob_hashes(self):
        payload = exam(IMAGE_URL)
        payload["data"]["id"] = "1234567890123456789"
        directory = self.root.parent / "manifests"
        fetcher = Mock(return_value=(png_bytes(), "image/png"))
        original, reused = cache_unit_media(payload, self.root, directory, fetcher=fetcher)
        self.assertFalse(reused)
        second, reused = cache_unit_media(payload, self.root, directory, fetcher=fetcher)
        self.assertTrue(reused)
        self.assertEqual(original, second)
        self.assertEqual(fetcher.call_count, 1)
        payload["data"]["title"] = "A new source version"
        third, reused = cache_unit_media(payload, self.root, directory, fetcher=fetcher)
        self.assertFalse(reused)
        self.assertNotEqual(original["source_content_sha256"], third["source_content_sha256"])
        self.assertEqual(fetcher.call_count, 2)

    def test_failed_unit_refresh_retains_previous_manifest(self):
        payload = exam(IMAGE_URL)
        payload["data"]["id"] = "1234567890123456789"
        directory = self.root.parent / "manifests"
        cache_unit_media(
            payload, self.root, directory, fetcher=lambda *_, **__: (png_bytes(), "image/png")
        )
        path = directory / "1234567890123456789.json"
        before = path.read_bytes()
        with self.assertRaises(NinefenAssetError):
            cache_unit_media(
                payload,
                self.root,
                directory,
                refresh=True,
                fetcher=Mock(side_effect=NinefenAssetError("offline")),
            )
        self.assertEqual(path.read_bytes(), before)

    def test_corrupt_unit_map_or_blob_cannot_be_resumed(self):
        payload = exam(IMAGE_URL)
        payload["data"]["id"] = "1234567890123456789"
        directory = self.root.parent / "manifests"
        manifest, _ = cache_unit_media(
            payload, self.root, directory, fetcher=lambda *_, **__: (png_bytes(), "image/png")
        )
        path = directory / "1234567890123456789.json"
        corrupt = copy.deepcopy(manifest)
        corrupt["media_map"][IMAGE_URL] = "https://evil.invalid/image.png"
        path.write_text(json.dumps(corrupt))
        self.assertIsNone(verified_media_manifest(payload, path, self.root))
        path.write_text(json.dumps(manifest))
        (self.root / manifest["assets"][0]["filename"]).write_bytes(b"damaged")
        self.assertIsNone(verified_media_manifest(payload, path, self.root))


if __name__ == "__main__":
    unittest.main()
