"""Tests for the job scheduler"""

from datetime import timedelta

from example_app.jobs import sample_job_1

from .registration import import_default_jobs


def test_global_scheduler():
    jobs = import_default_jobs()
    assert sample_job_1 in jobs
    assert sample_job_1.interval == timedelta(seconds=5)
    assert sample_job_1.variance == timedelta()
