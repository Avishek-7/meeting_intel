#!/usr/bin/env python3
import argparse

from rq import Queue
from rq.job import Job
from rq.registry import FailedJobRegistry

from core.queue import redis_client

DEFAULT_ERROR_SUBSTRING = "Invalid attribute name: jobs.meeting_analysis.run_meeting_analysis_job_sync"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Requeue only failed RQ jobs that match a specific error substring.",
    )
    parser.add_argument(
        "--queue",
        default="default",
        help="RQ queue name (default: default)",
    )
    parser.add_argument(
        "--error-substring",
        default=DEFAULT_ERROR_SUBSTRING,
        help="Substring to match within job.exc_info",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually requeue matched jobs. Without this flag, it runs in dry-run mode.",
    )
    args = parser.parse_args()

    if redis_client is None:
        raise SystemExit("Redis queue is unavailable (check redis_url).")

    queue = Queue(args.queue, connection=redis_client)
    failed_registry = FailedJobRegistry(queue=queue)
    failed_ids = failed_registry.get_job_ids()

    matched_ids: list[str] = []
    for job_id in failed_ids:
        try:
            job = Job.fetch(job_id, connection=redis_client)
        except Exception:
            continue
        if args.error_substring in (job.exc_info or ""):
            matched_ids.append(job_id)

    print(f"failed_total={len(failed_ids)}")
    print(f"matched={len(matched_ids)}")

    if not matched_ids:
        print("No matching failed jobs found.")
        return

    for job_id in matched_ids:
        print(f"match={job_id}")

    if not args.apply:
        print("Dry run only. Add --apply to requeue matched jobs.")
        return

    requeued = 0
    for job_id in matched_ids:
        try:
            failed_registry.requeue(job_id)
            requeued += 1
        except Exception as exc:
            print(f"requeue_failed={job_id} error={type(exc).__name__}: {exc}")

    print(f"requeued={requeued}")


if __name__ == "__main__":
    main()
