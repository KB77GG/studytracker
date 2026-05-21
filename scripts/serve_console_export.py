#!/usr/bin/env python3
"""Serve repo files with CORS for temporary Chrome Console imports."""

from __future__ import annotations

import argparse
import http.server
import os
import threading
from pathlib import Path


class CorsHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def guess_type(self, path: str) -> str:
        if path.endswith(".js"):
            return "text/javascript; charset=utf-8"
        return super().guess_type(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ttl", type=int, default=3600)
    args = parser.parse_args()

    os.chdir(Path(args.root).resolve())
    server = http.server.ThreadingHTTPServer((args.host, args.port), CorsHandler)
    if args.ttl > 0:
        threading.Timer(args.ttl, server.shutdown).start()
    print(f"serving {Path.cwd()} on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
