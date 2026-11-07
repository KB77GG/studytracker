"""Local-only template preview with synthetic empty answers; no app/DB imports."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from flask import Flask, abort, render_template, request, send_from_directory  # noqa: E402

from services.ielts_practice_scoring import grade_listening_test_answers  # noqa: E402
from services.question_type_review import derive_listening_payload  # noqa: E402

app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
app.config["TEMPLATES_AUTO_RELOAD"] = True
AUDIO_ROOT = None


@app.get("/practice", endpoint="practice_library")
@app.get("/reading/tests", endpoint="reading_test_index")
@app.get("/reading/jijing", endpoint="reading_jijing_index")
@app.get("/listening/tests", endpoint="listening_test_index")
def index():
    return "Local audit preview only. No accounts, persistence or submissions."


@app.get("/static/listening/<path:filename>")
def audio(filename):
    if AUDIO_ROOT is None:
        abort(404)
    return send_from_directory(AUDIO_ROOT, filename)


@app.get("/preview/<subject>/<test_id>")
def preview(subject, test_id):
    if subject not in {"reading", "listening"}:
        abort(404)
    path = ROOT / "static" / (subject + "_tests") / (test_id + ".json")
    if not path.is_file() or not test_id.startswith("ielts"):
        abort(404)
    payload = json.loads(path.read_text())
    context = None
    if subject == "listening":
        result = grade_listening_test_answers(payload, {})
        payload = derive_listening_payload(
            payload, static_root=ROOT / "static", audio_root=AUDIO_ROOT
        )
        if request.args.get("review", "1") != "0":
            context = {"read_only": True, "initial_review": {"answers": {}, "result": result}}
    return render_template(subject + "/test_practice.html", test=payload, practice_context=context)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5098)
    parser.add_argument("--audio-root", type=Path)
    args = parser.parse_args()
    AUDIO_ROOT = args.audio_root
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
