# Django Quick Jobs

I have a need to run some periodic jobs on the DigitalOcean App Platform, which doesn't have any scheduled job runners, and my use cases were too simple to bother with Celery and such. This package gives a simple way to have a `jobs.py` file in your Django app(s), and then decorating each job with `@job_runner.schedule(interval, variance)`. These jobs will then all be run via `python manage.py run_jobs`. Each job will be repeated every interval with an additional random delay between 0 and the variance.

Jobs are not coordinated across multiple instances of run_jobs. In my case, the individual jobs were designed to handle concurrency themselves via `select_for_update=True` in the queryset.

## Example usage

`settings.py`:
```python
INSTALLED_APPS = [
    ...
    'my_app',
    'job_runner',
]
```

`my_app/jobs.py`:
```python
from job_runner import schedule

# Run this job periodically - at most every 45 seconds and at least every 30 seconds
@schedule(30, 15)
def my_great_job():
    print("My great job is getting called")
```

Start the job runner: `python manage.py run_jobs`
