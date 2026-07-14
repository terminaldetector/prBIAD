"""Common value types.

Distilled from ``exo.shared.types.*`` (``common.py``, ``memory.py``,
``backends.py``, ``profiling.py``) and ``exo.shared.models.model_cards``.

Upstream uses pydantic ``FrozenModel``/``TaggedModel``; here we use plain
``dataclasses`` so the core has zero third-party dependencies and runs under
Chaquopy. The semantics (memory arithmetic, model-card fields) are preserved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import NewType

# In upstream ``NodeId``/``RunnerId``/``InstanceId`` are UUID-backed newtypes.
NodeId = NewType("NodeId", str)
RunnerId = NewType("RunnerId", str)
InstanceId = NewType("InstanceId", str)


def new_node_id() -> NodeId:
    return NodeId(str(uuid.uuid4()))


def new_runner_id() -> RunnerId:
    return RunnerId(str(uuid.uuid4()))


def new_instance_id() -> InstanceId:
    return InstanceId(str(uuid.uuid4()))


class Backend(str, Enum):
    """Compute backend of a node (distilled from ``exo.shared.types.backends``).

    The Apple-only backends are retained as enum values for compatibility with
    upstream placement logic, and Android-relevant backends are added.
    """

    MlxMetal = "MlxMetal"
    MlxCuda = "MlxCuda"
    # Android-relevant backends (not present upstream):
    TfLite = "TfLite"          # TensorFlow Lite (already a Saturn Mask dep)
    LiteRt = "LiteRt"          # Google AI Edge LiteRT
    Cpu = "Cpu"


@dataclass(frozen=True)
class Memory:
    """A quantity of memory, stored in bytes (distilled from ``types.memory``)."""

    in_bytes: int = 0

    @staticmethod
    def from_gb(gb: float) -> "Memory":
        return Memory(int(gb * 1024 * 1024 * 1024))

    @staticmethod
    def from_mb(mb: float) -> "Memory":
        return Memory(int(mb * 1024 * 1024))

    @property
    def in_gb(self) -> float:
        return self.in_bytes / (1024 * 1024 * 1024)

    def __add__(self, other: "Memory") -> "Memory":
        return Memory(self.in_bytes + other.in_bytes)

    def __radd__(self, other: object) -> "Memory":
        # Enables ``sum(memories, start=Memory())``.
        if other == 0 or other is None:
            return self
        if isinstance(other, Memory):
            return Memory(self.in_bytes + other.in_bytes)
        return NotImplemented

    def __mul__(self, factor: int) -> "Memory":
        return Memory(self.in_bytes * factor)

    def __floordiv__(self, divisor: int) -> "Memory":
        return Memory(self.in_bytes // divisor)

    def __truediv__(self, other: "Memory") -> float:
        # Fraction of two memory quantities (used for memory-weighted split).
        return self.in_bytes / other.in_bytes

    def __ge__(self, other: "Memory") -> bool:
        return self.in_bytes >= other.in_bytes

    def __gt__(self, other: "Memory") -> bool:
        return self.in_bytes > other.in_bytes


@dataclass(frozen=True)
class MemoryUsage:
    """Per-node memory snapshot (distilled from ``types.profiling.MemoryUsage``)."""

    ram_total: Memory = field(default_factory=Memory)
    ram_available: Memory = field(default_factory=Memory)


@dataclass(frozen=True)
class Host:
    """A network host (distilled from ``types.common.Host``)."""

    ip: str
    port: int


@dataclass(frozen=True)
class ModelCard:
    """Minimal model descriptor (distilled from ``models.model_cards.ModelCard``).

    Only the fields required by the partition/sharding logic are kept.
    """

    model_id: str
    n_layers: int
    storage_size: Memory
    uses_cfg: bool = False
