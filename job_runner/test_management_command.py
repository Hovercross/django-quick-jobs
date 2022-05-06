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


@register_job(1)
def invalid():
    print("Invalid job is being called")


@register_job()
def fatal(env: RunEnv):
    """A sample job that requests a fatal exit"""

    env.request_fatal_errors()
    raise Exception("I'm in danger!")


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


@pytest.mark.timeout(15)
def test_run_forever_bail():
    run_forever_event.clear()  # reset

    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--stop-after",
            "1",
            "--stop-timeout",
            "5",
            "--include-job",
            "job_runner.test_management_command.run_forever",
        )

    # clean up the thread by setting the event
    run_forever_event.set()


def test_invalid_job():
    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--include-job",
            "job_runner.test_management_command.invalid",
        )


def test_fatal_job():
    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--include-job",
            "job_runner.test_management_command.fatal",
        )
