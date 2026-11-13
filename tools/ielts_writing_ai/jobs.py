"""In-process background jobs with a bounded worker pool.

The trial server runs as a single process, so a small thread pool is enough.
Work interrupted by a restart is marked failed at startup (see
``Storage.fail_interrupted``) and can be regenerated from the page.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("iwa.jobs")


class JobRunner:
    def __init__(self, generator, *, mode: str = "thread", max_workers: int = 2):
        self.generator = generator
        self.mode = mode
        self._pool = (
            ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="iwa-job")
            if mode == "thread"
            else None
        )

    def _submit(self, fn, *args) -> None:
        if self._pool is None:
            fn(*args)
            return

        def safe():
            try:
                fn(*args)
            except Exception:  # pragma: no cover - logged, generation already guarded
                log.exception("background job failed")

        self._pool.submit(safe)

    def start_submission(self, submission_id: int, generation_ids: list[int], needs_image: bool):
        """Read the task image first (if any), then fan out the three generations. A
        well-formed reading waits for the person to check it (web: image-check), which
        then starts the generations."""

        def pipeline():
            if needs_image:
                self.generator.describe_image(submission_id)
                if self.generator.awaiting_image_check(submission_id):
                    return
            for generation_id in generation_ids:
                self._submit(self.generator.run, generation_id)

        self._submit(pipeline)

    def start_generation(self, generation_id: int) -> None:
        self._submit(self.generator.run, generation_id)

    def shutdown(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
