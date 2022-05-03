from datetime import datetime
import time

from job_runner.registration import register_job
from job_runner.environment import RunEnv


@register_job()
def run_forever(env: RunEnv):
    """A sample job that is badly behaved and will run forever.
    Not in jobs.py since we don't want it to run by default"""

    print(f"run_forever is getting called at {datetime.now()}")

    while True:
        time.sleep(1)
