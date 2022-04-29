"""Job tracking library"""

import job_runner.singlton
from job_runner.tracker import RunEnvironment

# Expose the singleton scheduler into the top job_runner API
schedule = job_runner.singlton.schedule
