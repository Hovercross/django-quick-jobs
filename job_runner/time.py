from typing import TypeVar, Optional, Union
from datetime import timedelta

T = TypeVar("T")

AutoTime = Union[timedelta, int, float]


def auto_time(val: AutoTime) -> timedelta:
    if isinstance(val, timedelta):
        return val

    return timedelta(seconds=val)


def auto_time_default(val: Optional[AutoTime], default: T) -> Union[timedelta, T]:
    if val is None:
        return default

    return auto_time(val)
