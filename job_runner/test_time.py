"""Tests for the time functions"""

from typing import List, Tuple
from datetime import timedelta

import pytest
from .time import AutoTime, auto_time

TIME_EQUIVALENCIES: List[Tuple[AutoTime, timedelta]] = [
    (30, timedelta(seconds=30)),
    (60.0, timedelta(seconds=60)),
    (0, timedelta(seconds=0)),
    (timedelta(minutes=1), timedelta(seconds=60)),
    (120, timedelta(minutes=2)),
]


@pytest.mark.parametrize("input,expected", TIME_EQUIVALENCIES)
def test_time_equivalencies(
    input: AutoTime,
    expected: timedelta,
):
    result = auto_time(input)
    assert result == expected
