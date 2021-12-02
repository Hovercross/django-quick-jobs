"""Job tracking library"""

import job_runner.singlton

# Expose the singleton scheduler into the top job_runner API
schedule = job_runner.singlton.schedule
