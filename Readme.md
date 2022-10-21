# Django Quick Jobs

A way of running simple periodic tasks without the use of Cron, Celery, RabbitMQ, Redis, or any external services.

## Why was this created

I have a need to run some periodic jobs on the DigitalOcean App Platform, which doesn't have any scheduled job runners and my use cases were too simple to bother with Celery and such. This package gives a simple way to have a *jobs.py* file in your Django app(s) with functions that should be run periodically.

This library is best used for smaller-scale sites where Celery and the like is overkill. Once you are worrying about large numbers of jobs or the performance of querying the database for any ready work it is probably time to move to a more robust tool.

## Basic usage

In each of your Django app(s) that need to have jobs, create a *jobs.py* file. Inside of *jobs.py*, create a function that accepts a `job_runner.environment.RunEnv` parameter and decorate it with `@job_runner.register_job(interval, variance, timeout)`. These jobs will then all be run via `python manage.py run_jobs`. Each job will be repeated every `interval` with an additional random delay between 0 and `variance`. The variance option is to reduce the impact of any "thundering herds". If `timeout` is specified then the job runner will be stopped whenever the job runs for longer than `timeout`. The only required parameter to `register_job` is `interval`. All times (`interval`, `variance`, and `timeout`) can be integers, floats, or timedelta objects. Integer and float parameters are interpreted as seconds.

Jobs are not coordinated across multiple instances of `run_jobs` - the individual jobs need to be designed to handle concurrency on their own. Strategies for this would be to use `select_for_update`, a serializable isolation level, or some external locking mechanics.

Individual runners will not start new executions of a job if the previous job is still running. If you only have one instance of `python manage.py run_jobs` running you can be reasonably certain that each of your individual jobs will only have one execution of a given job at any given time.

## Sample use cases

### Recalculating data

We might have some model that sets a `needs_recalculation` field. We could have a periodic job that queries everything that has `needs_recalculation` set to true and perform some calculation that takes a long time - such as updating other related data models. The models we are updating should use `select_for_update` so that multiple instances of the job runner don't try to recalculate the same objects at the same time.

### Sending emails

We might have a process that inserts outgoing email records into a database table. We could have a job that queries for all unsent email (again with `select_for_update`) and sends them, then marking them as sent in the database.



## Installation

Install the package: `pip install django-quick-jobs`

Add `job_runner` to `INSTALLED_APPS` in *settings.py*:

```python
INSTALLED_APPS = [
    ...
    'job_runner',
]
```

### Minimum requirements

- Python: 3.7
- Django: 2.2

Automated tests are currently run against all valid permutations of Python 3.7, 3.8, 3.9, 3.10, and 3.11 with Django 2.2, 3.0, 3.1, 3.2, 4.0, and 4.1. The latest point releases are always used for testing.

## Example usage

### Create a job

In *your_great_app/jobs.py*:

```python
from datetime import datetime

from job_runner.registration import register_job
from job_runner.environment import RunEnv

# Run this job periodically - at most every 10 seconds and at least every 60 seconds
@register_job(10, 50)
def my_great_job(env: RunEnv):
    print(f"My great job is getting called at {datetime.now()}")
```

Note that `your_great_app` must be in `INSTALLED_APPS` for the job runner to automatically detect it.

### Start the job runner

Run `python manage.py run_jobs` from your terminal

Resulting output:
```text
> python manage.py run_jobs

My great job is getting called at 2021-12-02 19:24:11.139457
My great job is getting called at 2021-12-02 19:24:27.777766
My great job is getting called at 2021-12-02 19:25:21.121113
```

## Command line options

For most use cases no additional command line flags need to be set.

- `--include-job`: The full path to a registered job that should be run in this instance of the job runner. This flag can be repeated to run multiple jobs and only the listed jobs will be executed. Included jobs do not have to be in a *jobs.py* file - they can be anywhere that can be imported from Python. Jobs must use the `@registered_job` decorator even if they are not in *jobs.py*.
- `--exclude-job`: The full path of a registered job that should be excluded from being executed. All jobs not excluded will be run and this option is mutually exclusive with `--include-jobs`
- `--stop-after`: Stop the job runner after some amount of time, listed in seconds. Useful to temporarily fix a resource leak by stopping the job runner periodically and then letting your execution environment start it again. By default the job runner does not shut itself down.
- `--stop-variance`: A random delay to add to the `--stop-after` parameter in order to prevent thundering herds if you have multiple job runner instances.
- `--stop-timeout`: When stopping, how long before the job runner forces an exit if the individual jobs are not shutting down cleanly. Defaults to 5 seconds.
- `--trial-run`: Just make sure all the included or excluded jobs can be found. The logger will emit a job list at the info level that can be used to verify what would be run. If there are no jobs to run, the job runner with exit with an error even if the `--trial-run` flag is set.

## The job run environment

Every job that is being run will be passed an instance of `job_runner.environment.RunEnv`. This environment gives the job instance the ability to interact with the job runner in limited ways.

The following functions and properties are exposed for use in the run environment:

- `is_stopping`: This allows the script to check if it has been requested to stop. It is recommended to check this as often as possible and exit cleanly if a stop is requested.
- `request_rerun()`: This allows the job being executed to request that it gets executed immediately again. A sample use case might be a work queue where the queue tries to get a job from the database. You may want to request that it be rerun until there are no jobs left and then let the scheduler delay execution until the next time when the queue is empty.
- `request_stop()`: Request that the entire job runner shut down. Useful if running in Kubernetes or another system that will restart the job runner and the job has gotten into a situation that requires a restart to fix. Note that the entire runner and thus all jobs will exit.
- `request_fatal_errors()`: A shortcut to indicate that any raised errors should be propagated and the job runner shut down if an error occurs. Effectively triggers `request_stop()` on an exception.
- `sleep(timeout)`: Delay execution of the job for some amount of time. Will raise an exception if the runtime environment has requested that the system shut down. Use this instead of `time.sleep` to be a well behaved job that exits when it is asked to.
- `raise_if_stopping()`: Raise a `job_runner.environment.RunInterrupted` if the thread has requested to stop. This can be used instead of checks to `is_stopping` to reduce boilerplate.
