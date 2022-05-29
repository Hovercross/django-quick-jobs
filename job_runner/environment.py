"""Environments for the job runner"""

from threading import Event
from typing import Tuple

from job_runner.time import AutoTime, auto_time


class SleepInterrupted(Exception):
    """An exception indicating that a thread sleep was interrupted"""


class _Env:
    def __init__(self, stop_event: Event):
        self.stop_event = stop_event
        self.request_immediate_rerun = False
        self.requested_stop = False
        self.requested_fatal_errors = False


class TrackerEnv:
    """Manages the environment from the job tracker side"""

    def __init__(self, env: _Env):
        self._env = env

    @property
    def requested_rerun(self):
        return self._env.request_immediate_rerun

    @property
    def requested_stop(self):
        return self._env.requested_stop

    @property
    def requested_fatal_errors(self):
        return self._env.requested_fatal_errors


class RunEnv:
    """The run environment is passed into all jobs when they"
    "are run and exposes information about the execution"""

    def __init__(self, env: _Env):
        self._env = env

    def sleep(self, timeout: AutoTime):
        """Wait for stop should be used instead of any sleeps"""

        wait_time = auto_time(timeout)

        if self._env.stop_event.wait(wait_time.total_seconds()):
            raise SleepInterrupted()

    def request_rerun(self):
        self._env.request_immediate_rerun = True

    def request_stop(self):
        self._env.requested_stop = True

    def request_fatal_errors(self):
        """Request that errors get thrown up and become fatal"""
        self._env.requested_fatal_errors = True

    @property
    def is_stopping(self) -> bool:
        return self._env.stop_event.is_set()


def get_environments(stop_event: Event) -> Tuple[RunEnv, TrackerEnv]:
    env = _Env(stop_event)
    return RunEnv(env), TrackerEnv(env)
