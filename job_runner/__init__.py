"""Job tracking library"""

import job_runner.singlton

# Expose the singleton scheduler into the global API
schedule = job_runner.singlton.schedule