"""Tests for the job scheduler"""

from datetime import timedelta
from typing import Iterable, List, Tuple

import pytest

from example_app.jobs import sample_job_1
from job_runner.environment import RunEnv
from .singlton import auto_import_jobs
from .tracker import AutoTime, RegisteredJob, JobTracker

TIME_EQUIVALENCIES: List[Tuple[AutoTime, timedelta]] = [
    (30, timedelta(seconds=30)),
    (60.0, timedelta(seconds=60)),
    (0, timedelta(seconds=0)),
    (timedelta(minutes=1), timedelta(seconds=60)),
]


def test_global_scheduler():
    expected_job = RegisteredJob(
        interval=timedelta(seconds=5),
        variance=timedelta(seconds=0),
        func=sample_job_1,
    )

    assert expected_job in auto_import_jobs()


def test_schedule_job():
    def hello(env: RunEnv):
        pass

    tracker = JobTracker()
    tracker.schedule_job(hello)

    expected_job = RegisteredJob(
        interval=timedelta(seconds=0),
        variance=timedelta(seconds=0),
        func=hello,
    )

    assert expected_job in tracker.get_jobs()


def _get_test_time_data() -> Iterable[Tuple[AutoTime, AutoTime, timedelta, timedelta]]:
    for interval, expected_interval in TIME_EQUIVALENCIES:
        for variance, expected_variance in TIME_EQUIVALENCIES:
            yield (interval, variance, expected_interval, expected_variance)


@pytest.mark.parametrize(
    "interval,variance,expected_interval,expected_variance", _get_test_time_data()
)
def test_schedule_job_params(
    interval: AutoTime,
    variance: AutoTime,
    expected_interval: timedelta,
    expected_variance: timedelta,
):
    def hello(env: RunEnv):
        pass

    tracker = JobTracker()
    tracker.schedule_job(hello, interval, variance)

    expected = RegisteredJob(expected_interval, expected_variance, hello)
    assert tracker.get_jobs() == [expected]
