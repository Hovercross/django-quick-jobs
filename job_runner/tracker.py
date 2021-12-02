"""Tracking utils for job runner"""

from typing import Callable, List, Optional, Union
from datetime import timedelta
from dataclasses import dataclass
from threading import Lock

Job = Callable[[], Optional[bool]]

AutoTime = Union[None, timedelta, int, float]


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


class JobTracker:
    """Track the registered jobs"""

    def __init__(self):
        self._lock = Lock()
        self._jobs: List[RegisteredJob] = []

    def add_job(self, job: RegisteredJob):
        """Add a tracked job"""
        with self._lock:
            self._jobs.append(job)

    def schedule_job(self, func: Job, interval: AutoTime = None, variance: AutoTime = None):
        """Schedule a job to run every {interval} < run time < {variance}"""

        interval = _read_auto_time(interval, timedelta(seconds=0))
        variance = _read_auto_time(variance, timedelta(seconds=0))

        job = RegisteredJob(func=func, interval=interval, variance=variance)

        self.add_job(job)


    def get_jobs(self) -> List[RegisteredJob]:
        """Get all the jobs that have been registered"""
        return self._jobs[:]


def _read_auto_time(val: AutoTime, default: timedelta) -> timedelta:
    if val is None:
        return default

    if isinstance(val, timedelta):
        return val

    return timedelta(seconds=val)
