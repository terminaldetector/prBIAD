"""Logging shim that routes to ``android.util.Log`` when running under Chaquopy.

Upstream exo uses loguru + hypercorn logging, which are undesirable on Android.
This module exposes a tiny ``get_logger`` that returns a standard ``logging``
logger, but when running inside an Android process (Chaquopy) it attaches a
handler that forwards records to ``android.util.Log`` under the ``EXO_BRIDGE``
tag, matching the logging convention from the integration plan.
"""

from __future__ import annotations

import logging
from typing import Optional

_ANDROID_TAG = "EXO_BRIDGE"
_configured = False


def _android_log_module():
    """Return the ``android.util.Log`` class if available, else ``None``."""
    try:  # Chaquopy exposes Java classes via the ``jnius``/``java`` bridge.
        from java import jclass  # type: ignore

        return jclass("android.util.Log")
    except Exception:
        return None


class _AndroidLogHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self._log = _android_log_module()

    def emit(self, record: logging.LogRecord) -> None:
        if self._log is None:
            return
        msg = self.format(record)
        try:
            if record.levelno >= logging.ERROR:
                self._log.e(_ANDROID_TAG, msg)
            elif record.levelno >= logging.WARNING:
                self._log.w(_ANDROID_TAG, msg)
            elif record.levelno >= logging.INFO:
                self._log.i(_ANDROID_TAG, msg)
            else:
                self._log.d(_ANDROID_TAG, msg)
        except Exception:
            pass


def _configure() -> None:
    global _configured
    if _configured:
        return
    root = logging.getLogger("exo_core")
    root.setLevel(logging.INFO)
    if _android_log_module() is not None:
        handler: logging.Handler = _AndroidLogHandler()
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root.addHandler(handler)
    root.propagate = False
    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    _configure()
    if name:
        return logging.getLogger("exo_core." + name)
    return logging.getLogger("exo_core")
