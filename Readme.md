# Django Quick Jobs

I have a need to run some periodic jobs on the DigitalOcean App Platform, which doesn't have any scheduled job runners, and my use cases were too simple to bother with Celery and such. This package gives a simple way to have a `jobs.py` file in your Django app(s), and then decorating each job with `@job_runner.register_job(interval, variance)`. These jobs will then all be run via `python manage.py run_jobs`. Each job will be repeated every interval with an additional random delay between 0 and the variance. The variance option is to reduce the impact of any thundering herds when you have multiple jobs at the same interval or multiple job runners that might all start at once.

Jobs are not coordinated across multiple instances of run_jobs. The individual jobs need to be designed to handle concurrency, for instance by locking using `select_for_update=True` in a queryset.

## Example usage

`settings.py`:
```python
INSTALLED_APPS = [
    ...
    'your_great_app',
    'job_runner',
]
```

`your_great_app/jobs.py`:
```python
from datetime import datetime

from job_runner.registration import register_job
from job_runner.environment import RunEnvironment

# Run this job periodically - at most every 10 seconds and at least every 60 seconds
@register_job(10, 50)
def my_great_job(env: RunEnvironment):
    print(f"My great job is getting called at {datetime.now()}")
```

Start the job runner: `python manage.py run_jobs`

```text
> python manage.py run_jobs

My great job is getting called at 2021-12-02 19:24:11.139457
My great job is getting called at 2021-12-02 19:24:27.777766
My great job is getting called at 2021-12-02 19:25:21.121113
```

## Command line options

For most use cases no additional command line flags need to be set.

- `--include-job`: The full path to a registered job that should be run in this instance of the job runner. This flag can be repeated to run multiple jobs, and if it is included no jobs excepted the listed jobs will be executed. Included jobs do not have to be in a `jobs.py` file and can be anywhere that can be imported from Python. Jobs must use the `@registered_job` decorator even if they are not in `jobs.py`
- `--exclude-job`: The full path of a registered job that should be excluded from being executed. All jobs not excluded will be run and this option is mutually exclusive with `--include-jobs`
- `--stop-after`: Stop the job runner after some amount of time, listed in seconds. Useful to temporarily fix a resource leak by stopping the job runner periodically and then letting your execution environment start it again. By default the job runner does not shut itself down.
- `--stop-variance`: A random delay to add to the `--stop-after` parameter in order to prevent thundering herds if you have multiple job runner instances.
- `--stop-timeout`: When stopping, how long before the job runner forces an exit if the individual jobs are not shutting down cleanly. Defaults to 5 seconds.
- `--trial-run`: Just make sure all the included or excluded jobs can be found. The logger will emit a job list at the info level that can be used to verify what would be run. If there are no jobs to run, the job runner with exit with an error even if the `--trial-run` flag is set.

## The job run environment

Every job that is being run will be passed an instance of `job_runner.environments.RunEnvironment`. This environment gives the job instance the ability to interact with the job runner in limited ways.

The following functions and properties are exposed for use in the run environment:

- `is_stopping`: This allows the script to check if it has been requested to stop. It is recommended to check this as often as possible and exit cleanly if a stop is requested.
- `request_rerun()`: This allows the job being executed to request that it gets executed immediately again. A sample use case might be a work queue where the queue tries to get a job from the database. You may want to request that it be rerun until there are no jobs left and then let the scheduler delay execution until the next time when the queue is empty.
- `request_stop()`: Request that the entire job runner shut down. Useful if running in Kubernetes or another system that will restart the job runner and the job has gotten into a situation that requires a restart to fix. Note that the entire runner and thus all jobs will exit.
- `request_fatal_errors()`: A shortcut to indicate that any thrown errors should be propagated and the job runner shut down if an error occurs. Effectively triggers `request_stop()` on an exception.
- `sleep(timeout)`: Delay execution of the job for some amount of time. Will throw an exception if the runtime environment has requested that the system shut down. Use this instead of `time.sleep` to be a well behaved job that exits when it is asked to.