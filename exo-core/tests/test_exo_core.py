"""Pytest wrapper around the exo-core self-test.

Run with either:
    python -m exo_core.selftest
    pytest
"""

from __future__ import annotations

from exo_core import selftest


def test_partition():
    selftest.test_partition()


def test_shard_assignment():
    selftest.test_shard_assignment()


def test_runner():
    selftest.test_runner()


def test_distributed():
    selftest.test_distributed()
