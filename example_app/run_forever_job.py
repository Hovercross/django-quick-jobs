from datetime import datetime
import time

from job_runner import schedule, RunEnv


@schedule(0, 0)
def run_forever(env: RunEnv):
    """A sample job that is badly behaved and will run forever.
    Not in jobs.py since we don't want it to run by default"""

    print(f"run_forever is getting called at {datetime.now()}")

    while True:
        time.sleep(1)
