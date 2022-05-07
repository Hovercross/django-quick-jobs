from datetime import timedelta
from test_app.jobs import sample_job_1

from job_runner.registration import import_default_jobs


def test_default_job_registration():
    jobs = import_default_jobs()

    expected_name = "test_app.jobs.sample_job_1"

    jobs_by_name = {job.name: job for job in jobs}
    assert expected_name in jobs_by_name
    job = jobs_by_name[expected_name]
    assert job.name == expected_name
    assert job.interval == timedelta(seconds=5)
    assert job.variance == timedelta(seconds=10)

    return
