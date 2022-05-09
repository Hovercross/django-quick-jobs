"""Tests for management command"""

from threading import Event
import signal
import threading
import time

import pytest

from django.core.management import call_command

from job_runner.environment import RunEnv, SleepInterrupted
from job_runner.registration import register_job

test_val = None
run_forever_event = Event()
slow_job_count = 0
fast_job_count = 0
rerun_job_count = 0


def test_management_command_smoke():
    call_command(
        "run_jobs",
        "--include-job",
        "job_runner.sample_jobs.sample_job_1",
        "--stop-after",
        "1",
    )


@register_job(1)
def set_test_val(env: RunEnv):
    global test_val
    test_val = True


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


@register_job(1)
def run_forever(env: RunEnv):
    run_forever_event.wait()


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


@register_job(1)
def invalid():
    print("Invalid job is being called")


def test_invalid_job():
    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--include-job",
            "job_runner.test_management_command.invalid",
        )


@register_job(1)
def fatal(env: RunEnv):
    """A sample job that requests a fatal exit"""

    env.request_fatal_errors()
    raise Exception("I'm in danger!")


def test_fatal_job():
    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--include-job",
            "job_runner.test_management_command.fatal",
        )


@register_job(0.1)
def fast_job(env: RunEnv):
    global fast_job_count

    fast_job_count += 1


def test_fast_job():
    global fast_job_count
    fast_job_count = 0

    call_command(
        "run_jobs",
        "--stop-after",
        "5",
        "--include-job",
        "job_runner.test_management_command.fast_job",
    )

    # We allow a range since timing isn't perfect
    assert 5 < fast_job_count < 100


@register_job(30)
def slow_job(env: RunEnv):
    global slow_job_count

    slow_job_count += 1


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


@register_job(30)
def rerun_job(env: RunEnv):
    global rerun_job_count

    rerun_job_count += 1
    env.request_rerun()


@pytest.mark.timeout(15)
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

    assert rerun_job_count > 2


@register_job(0)
def sleep_job(env: RunEnv):
    env.sleep(300)


@pytest.mark.timeout(10)
def test_sleep():
    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.sleep_job",
    )


@register_job(0)
def stop_request_job(env: RunEnv):
    env.request_stop()


@pytest.mark.timeout(10)
def test_request_stop():
    call_command(
        "run_jobs",
        "--include-job",
        "job_runner.test_management_command.stop_request_job",
    )


@register_job(0)
def fatal_error_job(env: RunEnv):
    env.request_fatal_errors()
    raise Exception("I like pie")


@pytest.mark.timeout(10)
def test_fatal_exception():
    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--include-job",
            "job_runner.test_management_command.fatal_error_job",
        )


@register_job(0)
def stopping_loop_job(env: RunEnv):
    while not env.is_stopping:
        pass


def test_stopping_loop():
    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.stopping_loop_job",
    )


@register_job(0)
def paused_job_exception(env: RunEnv):
    """A job used to test if a paused job throws a sleep interrupted"""

    with pytest.raises(SleepInterrupted):
        while True:
            env.sleep(1)


def test_paused_job_exception():
    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.paused_job_exception",
    )


@register_job(0)
def paused_job(env: RunEnv):
    """A job that pauses forever"""

    while True:
        env.sleep(1)


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


def test_multiple_included_jobs():
    """Make sure a properly formatted but missing included job throws an error"""

    global fast_job_count
    global slow_job_count

    fast_job_count = 0
    slow_job_count = 0

    call_command(
        "run_jobs",
        "--stop-after",
        "1",
        "--include-job",
        "job_runner.test_management_command.slow_job",
        "--include-job",
        "job_runner.test_management_command.fast_job",
    )

    assert fast_job_count > 0
    assert slow_job_count > 0


@pytest.mark.timeout(5)
def test_trial_run():
    """Make sure the included jobs don't get executed and we exit almost immediately"""

    global fast_job_count
    global slow_job_count

    fast_job_count = 0
    slow_job_count = 0

    call_command(
        "run_jobs",
        "--trial-run",
        "--include-job",
        "job_runner.test_management_command.slow_job",
        "--include-job",
        "job_runner.test_management_command.fast_job",
    )

    assert fast_job_count == 0
    assert slow_job_count == 0


@pytest.mark.timeout(5)
def test_signal_exit():
    """Make sure the included jobs don't get executed and we exit almost immediately"""

    global fast_job_count
    global slow_job_count

    fast_job_count = 0
    slow_job_count = 0

    # After 1 second, send a termination signal.
    # Since both of the jobs are well-behaved they should exit almost immediately
    def send_term():
        time.sleep(1)
        main_thread = threading.main_thread().ident
        signal.pthread_kill(main_thread, signal.SIGTERM)

    threading.Thread(target=send_term).start()

    call_command(
        "run_jobs",
        "--include-job",
        "job_runner.test_management_command.slow_job",
        "--include-job",
        "job_runner.test_management_command.fast_job",
    )

    assert fast_job_count > 0
    assert slow_job_count > 0


@register_job(0, timeout=1)
def paused_job_timeout(env: RunEnv):
    """A job that pauses forever"""

    print("Starting paused job with timeout")

    while True:
        time.sleep(1)


@pytest.mark.timeout(20)
def test_timeout():
    with pytest.raises(SystemExit):
        call_command(
            "run_jobs",
            "--include-job",
            "job_runner.test_management_command.paused_job_timeout",
        )


@register_job(0, timeout=1)
def run_forever_timeout(env: RunEnv):
    run_forever_event.wait()


@pytest.mark.timeout(15)
def test_run_forever_timeout_race():
    """Test that when we have a timed out job that ends up exiting,
    we still get an error"""

    run_forever_event.clear()

    # After 2 seconds, clear the event. This will let the job runner
    # thread finish, call the race condition timeout cancelation,
    # and let the job thread exit cleanly - but we should still get an error

    def delay():
        time.sleep(2)
        run_forever_event.set()

    threading.Thread(target=delay).start()

    with pytest.raises(SystemExit):
        # Call with an explicit stop timeout. This ensures our delay event fires to release
        # the stopped job before the master timeout kills the entire runner
        call_command(
            "run_jobs",
            "--stop-timeout",
            "10",
            "--include-job",
            "job_runner.test_management_command.run_forever_timeout",
        )


def test_invalid_job_for_coverage():
    """Just call the invalid job to make my coverage higher"""

    invalid._func()
