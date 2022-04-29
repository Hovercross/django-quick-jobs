from datetime import datetime

from structlog import get_logger

from job_runner import schedule

logging = get_logger()

# Run this job periodically - at most every 30 seconds and at least every 60 seconds
@schedule(30, 60)
def test_job_1():
    logging.debug("Executing test job 1")


# Run this job periodically - at most every 60 seconds and at least every 180 seconds
@schedule(60, 120)
def test_job_2():
    logging.debug("Executing test job 2")
