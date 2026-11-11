"""Offline integration probes against the real CLI/realcheck implementation."""

import argparse
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))

    def no_network(event, _args):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo"}:
            raise RuntimeError("Offline probe forbids network")

    sys.addaudithook(no_network)
    from tools.ielts_writing_ai import realcheck
    from tools.ielts_writing_ai.__main__ import build_parser, cmd_realcheck
    from tools.ielts_writing_ai.llm import FakeClient, LLMResult
    from tools.ielts_writing_ai.tests.helpers import PNG_BYTES, settings_for

    with tempfile.TemporaryDirectory(prefix="iwa-runner-realcheck-") as td:
        root = Path(td)
        report_dir = root / "failed-report"
        observations = []

        class InvalidClient(FakeClient):
            def complete(self, *a, **kw):
                observations.append(
                    {
                        "directory_exists_during_request": report_dir.exists(),
                        "files": sorted(p.name for p in report_dir.glob("*")),
                    }
                )
                return LLMResult("invalid synthetic JSON", self.model, 0)

        settings = settings_for(str(root / "d"), evaluate_thinking="high")
        ns = build_parser().parse_args(
            [
                "realcheck",
                "--samples",
                "builtin",
                "--limit",
                "1",
                "--kinds",
                "evaluate",
                "--max-calls",
                "2",
                "--out",
                str(report_dir),
            ]
        )
        with (
            patch.object(
                realcheck,
                "build_client",
                side_effect=lambda s, vision=False: None if vision else InvalidClient(),
            ),
            redirect_stdout(io.StringIO()),
        ):
            rc = cmd_realcheck(settings, ns)
        report = json.loads((report_dir / "report.json").read_text())
        run = json.loads((report_dir / "run_data.json").read_text())
        cli = {
            "exit": rc,
            "calls": report["calls"],
            "aborted": report["aborted"],
            "all_failed": all(
                s["generations"]["evaluate"]["status"] == "failed" for s in run["samples"]
            ),
            "persistence_at_dispatch": observations,
        }

        chart = root / "chart.png"
        chart.write_bytes(PNG_BYTES)
        base = next(i for i in realcheck.load_samples("builtin") if i["task_type"] == "task1")
        items = realcheck.expand_repeats(
            [{**base, "id": f"chart-{i}", "image": str(chart)} for i in range(2)], 2
        )

        class UnreadableClient(FakeClient):
            def complete(self, *a, **kw):
                return LLMResult("The image is unreadable.", self.model, 0)

        data = realcheck.run(
            settings,
            items,
            client=FakeClient(),
            vision_client=UnreadableClient(),
            kinds=("evaluate",),
            max_calls=10,
        )
        vision = {
            "stage_flash_call_cap": 10,
            "expected_image_limit": 2,
            "actual_vision_calls": sum(c["kind"] == "describe_image" for c in data["calls"]),
            "actual_text_calls": sum(c["kind"] == "evaluate" for c in data["calls"]),
            "total_calls": len(data["calls"]),
            "saved_readings": len(data["image_descriptions"]),
            "image_statuses": [s["image_status"] for s in data["samples"]],
        }
        result = {
            "network_calls": 0,
            "private_files_read": False,
            "cli_validation_failure": cli,
            "vision_failure_repeats": vision,
        }
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
