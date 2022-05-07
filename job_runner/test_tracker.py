"""Tests for the job scheduler"""

from datetime import timedelta

from .sample_jobs import sample_job_1
from .registration import import_jobs_from_modules


def test_explicit_jobs():
    jobs = import_jobs_from_modules(["job_runner.sample_jobs"])
    assert sample_job_1 in jobs
    assert sample_job_1.interval == timedelta(seconds=5)
