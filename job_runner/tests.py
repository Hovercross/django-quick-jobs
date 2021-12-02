"""Tests for the job scheduler"""

from datetime import timedelta

from django.test import TestCase

from . import schedule, find_jobs
from .tracker import RegisteredJob


class ScheduleTest(TestCase):
    """Tests for the scheduler"""

    def test_global_registration(self):
        """Test basic registration"""
        @schedule(timedelta(seconds=30))
        def hello():
            pass

        self.assertIn(
            RegisteredJob(
                interval=timedelta(seconds=30),
                variance=timedelta(seconds=0),
                func=hello),
            find_jobs())

    def test_registration_int(self):
        """Test registration with ints"""
        @schedule(5, 10)
        def hello():
            pass

        self.assertIn(
            RegisteredJob(
                interval=timedelta(seconds=5),
                variance=timedelta(seconds=10),
                func=hello),
            find_jobs())
