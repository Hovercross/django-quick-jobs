"""Environments for the job runner"""

from threading import Event
from typing import Tuple

from job_runner.time import AutoTime, read_auto_time
from datetime import timedelta


class _Env:
    def __init__(self, stop_event: Event):
        self.stop_event = stop_event
        self.request_immediate_rerun = False


class TrackerEnv:
    """Manages the environment from the job tracker side"""

    def __init__(self, env: _Env):
        self._env = env

    @property
    def requested_rerun(self):
        return self._env.request_immediate_rerun


class RunEnv:
    """The run environment is passed into all jobs when they"
    "are run and exposes information about the execution"""

    def __init__(self, env: _Env):
        self._env = env

    def wait_for_stop_request(self, timeout: AutoTime):
        """Wait for stop should be used instead of any sleeps"""

        wait_time = read_auto_time(timeout, default=timedelta(seconds=0))

        self._env.stop_event.wait(wait_time.total_seconds())

    def request_rerun(self):
        self._env.request_immediate_rerun = True

    @property
    def is_stopping(self) -> bool:
        return self._env.stop_event.is_set()


def get_environments(stop_event: Event) -> Tuple[RunEnv, TrackerEnv]:
    env = _Env(stop_event)
    return RunEnv(env), TrackerEnv(env)
