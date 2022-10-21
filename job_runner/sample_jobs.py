from datetime import datetime
import time

from job_runner.registration import register_job
from job_runner.environment import RunEnv


@register_job(5, 0)
def sample_job_1(env: RunEnv):
    print(f"sample_job_1 is getting called at {datetime.now()}")


@register_job(5, 0, enabled=False)
def sample_job_disabled(env: RunEnv):
    print(f"sample_job_disabled is getting called at {datetime.now()}")
