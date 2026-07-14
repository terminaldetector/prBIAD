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


def test_backend_registry():
    selftest.test_backend_registry()


def test_bridge_backend():
    selftest.test_bridge_backend()


def test_distributed_bridge():
    selftest.test_distributed_bridge()


def test_sharded_split():
    selftest.test_sharded_split()
