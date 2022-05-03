"""Tracking utils for job runner"""

from typing import List, Callable
from datetime import timedelta
from dataclasses import dataclass
from threading import Lock

from .environment import RunEnv
from .time import AutoTime, read_auto_time

Job = Callable[[RunEnv], None]


class RegisteredJob:
    """A job that has been registered to be run periodically"""

    def __init__(
        self,
        interval: timedelta,
        variance: timedelta,
        func: Job,
    ):
        self._interval = interval
        self._variance = variance
        self._func = func

    @property
    def name(self):
        """The full name of the function to be called"""
        return f"{self._func.__module__}.{self._func.__name__}"

    @property
    def maximum_interval(self) -> timedelta:
        return self._interval + self._variance

    @property
    def minimum_interval(self) -> timedelta:
        return self._interval

    @property
    def interval(self) -> timedelta:
        return self._interval

    @property
    def variance(self) -> timedelta:
        return self._variance

    @property
    def func(self) -> Job:
        return self._func

    def __eq__(self, other):
        if not isinstance(other, RegisteredJob):
            return False

        if self._func != other._func:
            return False

        if self._interval != other._interval:
            return False

        if self._variance != other._variance:
            return False

        return True

    def __hash__(self):
        return hash(hash(self._func) + hash(self._interval) + hash(self._variance))


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

        interval = read_auto_time(interval, timedelta(seconds=0))
        variance = read_auto_time(variance, timedelta(seconds=0))

        job = RegisteredJob(func=func, interval=interval, variance=variance)

        self._add_job(job)

    def get_jobs(self) -> List[RegisteredJob]:
        """Get all the jobs that have been registered"""
        return self._jobs[:]
