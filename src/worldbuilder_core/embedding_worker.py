import argparse
import asyncio
import time

from worldbuilder_core.db import SessionLocal, create_db_and_tables
from worldbuilder_core.services.document_extraction_jobs import (
    claim_document_extraction_job,
    run_document_extraction_batch,
)
from worldbuilder_core.services.embedding_jobs import (
    claim_embedding_job,
    run_embedding_job_batch,
    worker_identity,
)


def run_worker(*, poll_seconds: float = 2.0, once: bool = False) -> None:
    create_db_and_tables()
    worker_id = worker_identity()
    while True:
        with SessionLocal() as session:
            job = claim_embedding_job(session, worker_id)
        if job is not None:
            with SessionLocal() as session:
                asyncio.run(run_embedding_job_batch(session, job.id, worker_id))
            if once:
                return
            continue
        with SessionLocal() as session:
            extraction_job = claim_document_extraction_job(session, worker_id)
        if extraction_job is None:
            if once:
                return
            time.sleep(poll_seconds)
            continue
        with SessionLocal() as session:
            asyncio.run(run_document_extraction_batch(session, extraction_job.id, worker_id))
        if once:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Process queued Worldbuilder AI jobs.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    run_worker(poll_seconds=max(args.poll_seconds, 0.1), once=args.once)


if __name__ == "__main__":
    main()
