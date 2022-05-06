from datetime import datetime
import time

from job_runner.registration import register_job
from job_runner.environment import RunEnv


@register_job(5, 0)
def sample_job_1(env: RunEnv):
    print(f"sample_job_1 is getting called at {datetime.now()}")


@register_job()
def run_forever(env: RunEnv):
    """A sample job that is badly behaved and will run forever"""

    print(f"run_forever is getting called at {datetime.now()}")

    while True:
        time.sleep(1)


@register_job()
def fatal(env: RunEnv):
    """A sample job that requests a fatal exit"""

    env.request_fatal_errors()
    raise Exception("I'm in danger!")


@register_job(5)
def exception(env: RunEnv):
    """A sample job that throws an exception"""

    raise Exception("I'm not in that much danger")
