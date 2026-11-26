"""Python 3.10 runner for baseline tests importing the Python 3.11 UTC alias.

Only the test process receives the standard timezone.utc alias. Product modules
remain unchanged; production compatibility also requires compile/static checks.
"""

import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
if not hasattr(datetime, "UTC"):
    datetime.UTC = datetime.timezone.utc  # noqa: UP017 -- baseline test compatibility.
suite = unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:])
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
