import pytest
from django.core.management import call_command
import structlog
from structlog.testing import LogCapture

from job_runner.registration import import_default_jobs


@pytest.fixture(name="log_output")
def fixture_log_output():
    return LogCapture()


@pytest.fixture(autouse=True)
def fixture_configure_structlog(log_output):
    structlog.configure(processors=[log_output])


def test_no_jobs(log_output: LogCapture):
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
