"""Job from an external app for test purposes"""

from job_runner import schedule


@schedule(30, 0)
def say_hello():
    print("Hello from example app")
