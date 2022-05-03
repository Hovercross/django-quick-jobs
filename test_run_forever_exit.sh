#!/bin/bash

python manage.py run_jobs --stop-after=1 --include-job "example_app.run_forever_job.run_forever"

# We expect a return code 1 on timeout. If we don't get it, exit 1
if [[ $? -eq 0 ]]; then
    exit 1;
fi

# Successful exit
exit 0