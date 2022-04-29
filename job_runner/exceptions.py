"""Exceptions for the job runners"""


class RequestRestart(Exception):
    """An exception that indicates that a thread
    wants the whole coordinator to shut down"""
