"""In-process background execution for ingestion jobs (IR-08, ADR-0005)."""

import logging
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import TERMINAL_JOB_STATES, IngestionJob, JobState

logger = logging.getLogger(__name__)

INTERRUPTED_MESSAGE = "Interrupted by a server restart; request the import again."


class JobRunner:
    def __init__(self, workers: int, handler: Callable[[uuid.UUID], None]) -> None:
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ingest")
        self._handler = handler

    def submit(self, job_id: uuid.UUID) -> Future[None]:
        return self._executor.submit(self._handler, job_id)

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)


def fail_interrupted_jobs(session_factory: sessionmaker[Session]) -> int:
    """Jobs are not persisted in a queue; any non-terminal job at startup was interrupted. Mark
    it failed.
    """
    terminal = [state.value for state in TERMINAL_JOB_STATES]
    with session_factory() as session:
        result = session.execute(
            update(IngestionJob)
            .where(IngestionJob.state.not_in(terminal))
            .values(
                state=JobState.FAILED.value,
                error=INTERRUPTED_MESSAGE,
                finished_at=datetime.now(UTC),
            )
        )
        session.commit()
    count = int(getattr(result, "rowcount", 0) or 0)
    if count:
        logger.warning("ingestion_jobs_interrupted", extra={"count": count})
    return count
