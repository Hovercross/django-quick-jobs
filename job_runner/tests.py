"""Tests for the job scheduler"""

from datetime import timedelta
from typing import Iterable, Tuple

import pytest

from . import schedule
from .singlton import import_jobs
from .tracker import AutoTime, RegisteredJob, JobTracker

TIME_EQUIVS = [
    (30, timedelta(seconds=30)),
    (60.0, timedelta(seconds=60)),
    (0, timedelta(seconds=0)),
    (timedelta(minutes=1), timedelta(seconds=60)),
]


@schedule(30, 0)
def example_job():
    return 42


def test_global_scheduler():
    expected_job = RegisteredJob(
        interval=timedelta(seconds=30),
        variance=timedelta(seconds=0),
        func=example_job,
    )

    assert expected_job in import_jobs()


def test_schedule_job():
    def hello():
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
    for interval, expected_interval in TIME_EQUIVS:
        for variance, expected_variance in TIME_EQUIVS:
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
    def hello():
        pass

    tracker = JobTracker()
    tracker.schedule_job(hello, interval, variance)

    expected = RegisteredJob(expected_interval, expected_variance, hello)
    assert tracker.get_jobs() == [expected]
