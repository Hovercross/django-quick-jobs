from datetime import datetime

from job_runner.registration import register_job
from job_runner.environment import RunEnv

from django.db.models import F

from . import models

# Run this job periodically - at most every 30 seconds and at least every 60 seconds
@register_job(5, 0)
def sample_job_1(env: RunEnv):
    print(f"sample_job_1 is getting called at {datetime.now()}")


# Run this job periodically - at most every 60 seconds and at least every 180 seconds
@register_job(60, 120)
def sample_job_2(env: RunEnv):
    print(f"sample_job_2 is getting called at {datetime.now()}")


@register_job(1, 0)
def sample_job_3(env: RunEnv):
    print(f"sample_job_3 is getting called at {datetime.now()}")

    env.wait_for_stop_request(5)


@register_job(60, 0)
def sample_job_4(env: RunEnv):
    print(f"sample_job_4 is getting called at {datetime.now()}")

    env.wait_for_stop_request(5.8)
    if env.is_stopping:
        print("Test job 4 got immediate stop request")
        return

    print("Test job 4 finished without stop request")
    env.request_rerun()


@register_job(0.1, 0)
def increment_sample_value(env: RunEnv):
    try:
        item = models.Item.objects.get(key="sample test")
        item.value = F("value") + 1
        item.save()
        item.refresh_from_db()
    except models.Item.DoesNotExist:
        item = models.Item(key="sample test", value=1)
        item.save()

    print(f"Item value: {item.value}")
