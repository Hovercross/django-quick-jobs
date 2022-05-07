from typing import Optional, Union
from datetime import timedelta

AutoTime = Union[timedelta, int, float]


def auto_time(val: AutoTime) -> timedelta:
    if isinstance(val, timedelta):
        return val

    return timedelta(seconds=val)


def auto_time_default(
    val: Optional[AutoTime], default: timedelta = timedelta(0)
) -> timedelta:
    if val is None:
        return timedelta(0)

    return auto_time(val)
