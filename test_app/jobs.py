from job_runner.registration import register_job
from job_runner.environment import RunEnv


@register_job(5, 10)
def sample_job_1(env: RunEnv):
    print("sample_job_1 from test_app is being called")
