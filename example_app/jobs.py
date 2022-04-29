from datetime import datetime

from job_runner import schedule, RunEnvironment

# Run this job periodically - at most every 30 seconds and at least every 60 seconds
@schedule(5, 0)
def test_job_1(env: RunEnvironment):
    print(f"test_job_1 is getting called at {datetime.now()}")


# Run this job periodically - at most every 60 seconds and at least every 180 seconds
@schedule(60, 120)
def test_job_2(env: RunEnvironment):
    print(f"test_job_2 is getting called at {datetime.now()}")


@schedule(0, 0)
def test_job_3(env: RunEnvironment):
    print(f"test_job_3 is getting called at {datetime.now()}")

    env.stopping.wait(5)
