"""Job tracking library"""

import job_runner.singlton

# These get exposed into job_runner directly, and are, in 99% of cases, the only
# public API
find_jobs = job_runner.singlton.find_jobs
schedule = job_runner.singlton.schedule