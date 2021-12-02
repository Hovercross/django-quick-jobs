"""Job tracking library"""

from . import singleton

# These get exposed into job_runner directly, and are, in 99% of cases, the only
# public API
find_jobs = singleton.find_jobs
schedule = singleton.schedule