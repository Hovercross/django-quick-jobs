import pytest
from django.core.management import call_command

from job_runner.registration import import_default_jobs


def test_no_jobs():
    jobs = import_default_jobs()

    args = [
        "run_jobs",
    ]

    # Exclude every job
    for job in jobs:
        args.append("--exclude-job")
        args.append(job.name)

    with pytest.raises(SystemExit):
        call_command(*args)


def test_default_jobs():
    # Just make sure this runs
    call_command("run_jobs", "--stop-after", "1")
