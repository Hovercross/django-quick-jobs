"""Environments for the job runner"""

from threading import Event

from job_runner.time import AutoTime, read_auto_time
from datetime import timedelta


class TrackerEnv:
    """Manages the environment from the job tracker side"""

    def __init__(self, stop_event: Event):
        self._run_env = RunEnvironment(stop_event, self)
        self._did_request_rerun = False

    @property
    def run_environment(self):
        return self._run_env

    @property
    def did_request_rerun(self):
        return self._did_request_rerun


class RunEnvironment:
    """The run environment is passed into all jobs when they"
    "are run and exposes information about the execution"""

    def __init__(self, stop_evt: Event, tracker_env: TrackerEnv):
        self._stop_evt = stop_evt
        self._tracker_env = tracker_env

    def wait_for_stop_request(self, timeout: AutoTime):
        """Wait for stop should be used instead of any sleeps"""

        wait_time = read_auto_time(timeout, default=timedelta(seconds=0))

        self._stop_evt.wait(wait_time.total_seconds())

    def request_rerun(self):
        self._tracker_env._did_request_rerun = True

    @property
    def is_stopping(self) -> bool:
        return self._stop_evt.is_set()
