"""Tracking utils for job runner"""

from threading import Event
from typing import Callable, List, Optional, Union
from datetime import timedelta
from dataclasses import dataclass
from threading import Lock

AutoTime = Union[None, timedelta, int, float]


class RunEnvironment:
    """The run environment is passed into all jobs when they"
    "are run and exposes information about the execution"""

    def __init__(self, stop_evt: Event):
        self._stop_evt = stop_evt
        self._did_request_rerun = False

    def wait_for_stop_request(self, timeout: AutoTime):
        """Wait for stop should be used instead of any sleeps"""

        wait_time = _read_auto_time(timeout, default=timedelta(seconds=0))

        self._stop_evt.wait(wait_time.total_seconds())

    def request_rerun(self):
        self._did_request_rerun = True

    @property
    def is_stop_requested(self) -> bool:
        return self._stop_evt.is_set()

    @property
    def did_request_rerun(self):
        return self._did_request_rerun


Job = Callable[[RunEnvironment], Optional[bool]]


@dataclass(frozen=True)
class RegisteredJob:
    """A job that has been registered to be run periodically"""

    interval: timedelta
    variance: timedelta
    func: Job

    @property
    def name(self):
        """The full name of the function to be called"""
        return f"{self.func.__module__}.{self.func.__name__}"

    @property
    def maximum_interval(self) -> timedelta:
        return self.interval + self.variance

    @property
    def minimum_interval(self) -> timedelta:
        return self.interval


class JobTracker:
    """Track the registered jobs"""

    def __init__(self):
        self._lock = Lock()
        self._jobs: List[RegisteredJob] = []

    def _add_job(self, job: RegisteredJob):
        """Add a tracked job"""

        with self._lock:
            self._jobs.append(job)

    def schedule_job(
        self, func: Job, interval: AutoTime = None, variance: AutoTime = None
    ):
        """Schedule a job to run every {interval} < run time < {variance}"""

        interval = _read_auto_time(interval, timedelta(seconds=0))
        variance = _read_auto_time(variance, timedelta(seconds=0))

        job = RegisteredJob(func=func, interval=interval, variance=variance)

        self._add_job(job)

    def get_jobs(self) -> List[RegisteredJob]:
        """Get all the jobs that have been registered"""
        return self._jobs[:]


def _read_auto_time(val: AutoTime, default: timedelta) -> timedelta:
    if val is None:
        return default

    if isinstance(val, timedelta):
        return val

    return timedelta(seconds=val)
