from datetime import datetime

from job_runner import schedule

# Run this job periodically - at most every 10 seconds and at least every 60 seconds
@schedule(10, 50)
def my_great_job():
    print(f"My great job is getting called at {datetime.now()}")
