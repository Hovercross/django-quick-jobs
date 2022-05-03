"""Tests for management command"""

from django.core.management import call_command

from job_runner.environment import RunEnv
from job_runner.registration import register_job

test_val = None


@register_job(1)
def set_test_val(env: RunEnv):
    global test_val
    test_val = True


def test_management_command_smoke():
    call_command("run_jobs", stop_after=1)


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
