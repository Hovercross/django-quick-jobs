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


@schedule(1, 0)
def test_job_3(env: RunEnvironment):
    print(f"test_job_3 is getting called at {datetime.now()}")

    env.wait_for_stop_request(5)


@schedule(60, 0)
def test_job_4(env: RunEnvironment):
    print(f"test_job_4 is getting called at {datetime.now()}")

    env.wait_for_stop_request(5.8)
    if env.is_stop_requested:
        print("Test job 4 got immediate stop request")
        return

    print("Test job 4 finished without stop request")
    env.request_rerun()
