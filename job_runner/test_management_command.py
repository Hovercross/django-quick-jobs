"""Tests for management command"""

from threading import Event

import pytest

from django.core.management import call_command, CommandError

from job_runner.environment import RunEnv
from job_runner.registration import register_job

test_val = None
run_forever_event = Event()


@register_job(1)
def set_test_val(env: RunEnv):
    global test_val
    test_val = True


@register_job(1)
def run_forever(env: RunEnv):
    run_forever_event.wait()


def test_management_command_smoke():
    call_command(
        "run_jobs",
        "--include-job",
        "job_runner.sample_jobs.sample_job_1",
        "--stop-after",
        "1",
    )


def test_management_command_simple_execution():
    global test_val
    test_val = False  # Reset
    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.set_test_val",
    )

    assert test_val


def test_run_forever_bail():
    run_forever_event.clear()  # reset

    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--stop-after",
            "1",
            "--include-job",
            "job_runner.test_management_command.run_forever",
        )

    # clean up the thread by setting the event
    run_forever_event.set()
