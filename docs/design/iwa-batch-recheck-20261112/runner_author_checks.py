"""Run the author's probes/tests with transport-independent network denial.

Only the audit hook is added; product code and scenario assertions stay unchanged.
"""

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = """
import sys
def _runner_deny_network(event, args):
    if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo'}:
        raise RuntimeError('runner audit: network is forbidden')
sys.addaudithook(_runner_deny_network)
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=("batch", "process"), required=True)
    args = parser.parse_args()
    for key in list(os.environ):
        if key.startswith(("IWA_", "PROBE_")):
            del os.environ[key]
    exec(GUARD, {})
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    os.chdir(repo)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "batch":
        probe = (
            repo
            / "docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/batch_probe.py"
        )
        spec = importlib.util.spec_from_file_location("runner_authored_batch_probe", probe)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.SITE = GUARD + module.SITE
        sys.argv = [str(probe), "--repo", str(repo), "--out", str(args.out)]
        module.main()
    else:
        from tools.ielts_writing_ai.tests import test_batch_resume_20261112 as module

        module.HOLD = GUARD + module.HOLD
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.ParentKilledTest)
        with tempfile.TemporaryDirectory(prefix="iwa-runner-audit-site-") as site:
            (Path(site) / "sitecustomize.py").write_text(GUARD)
            os.environ["PYTHONPATH"] = site + os.pathsep + str(repo)
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        summary = {
            "tests": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "passed": result.wasSuccessful(),
            "network_blocked": True,
        }
        args.out.write_text(json.dumps(summary, indent=2) + "\n")
        raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
