"""Tests for management command"""

from threading import Event

import pytest

from django.core.management import call_command

from job_runner.environment import RunEnv, SleepInterrupted
from job_runner.registration import register_job

test_val = None
run_forever_event = Event()
slow_job_count = 0
fast_job_count = 0
rerun_job_count = 0


@register_job(0)
def paused_job(env: RunEnv):
    """A job that pauses forever"""

    while True:
        env.sleep(1)


@register_job(0)
def paused_job_exception(env: RunEnv):
    """A job used to test if a paused job throws a sleep interrupted"""

    with pytest.raises(SleepInterrupted):
        while True:
            env.sleep(1)


@register_job(0)
def stopping_loop_job(env: RunEnv):
    while not env.is_stopping:
        pass


@register_job(0)
def fatal_error_job(env: RunEnv):
    env.request_fatal_errors()
    raise Exception("I like pie")


@register_job(0)
def stop_request_job(env: RunEnv):
    env.request_stop()


@register_job(0)
def sleep_job(env: RunEnv):
    env.sleep(300)


@register_job(30)
def rerun_job(env: RunEnv):
    global rerun_job_count

    rerun_job_count += 1
    env.request_rerun()


@register_job(30)
def slow_job(env: RunEnv):
    global slow_job_count

    slow_job_count += 1


@register_job(0.1)
def fast_job(env: RunEnv):
    global fast_job_count

    fast_job_count += 1


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


@register_job(1)
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


@pytest.mark.timeout(5)
def test_run_forever_bail():
    run_forever_event.clear()  # reset

    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--stop-after",
            "1",
            "--stop-timeout",
            "1",
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


def test_fast_job():
    global fast_job_count
    fast_job_count = 0

    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.fast_job",
    )

    # We allow a range since timing isn't perfect
    assert 8 < fast_job_count < 12


def test_slow_job():
    global slow_job_count
    slow_job_count = 0

    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.slow_job",
    )

    assert slow_job_count == 1


def test_rerun_job():
    global rerun_job_count
    rerun_job_count = 0

    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.rerun_job",
    )

    # This is a very inexact measurement, but 10 is an extremely low bound.
    # On my M1 Mac I got 1154 in one second.
    assert rerun_job_count > 10


@pytest.mark.timeout(10)
def test_sleep():
    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.sleep_job",
    )


@pytest.mark.timeout(10)
def test_request_stop():
    call_command(
        "run_jobs",
        "--include-job",
        "job_runner.test_management_command.stop_request_job",
    )


@pytest.mark.timeout(10)
def test_fatal_exception():
    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--include-job",
            "job_runner.test_management_command.fatal_error_job",
        )

    expected_events = {
        "Error thrown in job thread",
        "Job requested fatal errors, propagating error",
    }


def test_stopping_loop():
    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.stopping_loop_job",
    )


def test_paused_job_exception():
    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.paused_job_exception",
    )


def test_paused_job():
    """Make sure that a paused job through up through the job runner properly"""

    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.paused_job",
    )


def test_bad_module_name():
    """Make sure that a paused job through up through the job runner properly"""

    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--stop-after",
            "1",
            "--include-job",
            "pie",
        )


def test_missing_included_job():
    """Make sure a properly formatted but missing included job throws an error"""

    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--stop-after",
            "1",
            "--include-job",
            "pie.jobs.asdf",
        )


    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--stop-after",
            "1",
            "--include-job",
            "pie.jobs.asdf",
            "--include-job",
            "job_runner.test_management_command.sleep_job",
        )
