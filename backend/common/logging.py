"""Logging helpers: attach the current request ID to every record."""

import logging

from common.request_context import request_id_var


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True
