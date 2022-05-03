from typing import Optional, Union
from datetime import timedelta

AutoTime = Union[None, timedelta, int, float]


def read_auto_time(
    val: AutoTime, default: Optional[timedelta] = None
) -> Optional[timedelta]:
    if val is None:
        return default

    if isinstance(val, timedelta):
        return val

    return timedelta(seconds=val)
