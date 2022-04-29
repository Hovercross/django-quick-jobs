"""Tracking utils for job runner"""

from threading import Event
from typing import Callable, List, Optional, Union
from datetime import timedelta
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class RunEnvironment:
    """The run environment is passed into all jobs when they"
    "are run and exposes information about the execution"""

    # An event that will get set if a shutdown is requested
    stopping: Event = field(default_factory=Event)


Job = Callable[[RunEnvironment], Optional[bool]]
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
