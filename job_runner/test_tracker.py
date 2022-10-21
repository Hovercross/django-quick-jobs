"""Tests for the job scheduler"""

from datetime import timedelta

from .sample_jobs import sample_job_1, sample_job_disabled
from .registration import import_jobs_from_module


def test_explicit_jobs():
    jobs = import_jobs_from_module("job_runner.sample_jobs")
    assert sample_job_1 in jobs
    assert sample_job_1.interval == timedelta(seconds=5)


def test_disabled_jobs():
    jobs = import_jobs_from_module("job_runner.sample_jobs")
    assert sample_job_disabled not in jobs
