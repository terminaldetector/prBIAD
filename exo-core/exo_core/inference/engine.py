"""Inference engine abstractions + a reference echo engine.

Distilled from ``exo.worker.engines.base`` (``Engine``/``Builder`` ABCs). The
signatures are simplified for the Android core: no ``serve_prefill`` (KV-cache
disaggregation over TCP is desktop-only) and streaming uses simple string chunks
rather than the upstream tagged ``Chunk`` union.

A concrete backend (TensorFlow Lite / LiteRT / ONNX Runtime / a native runtime
via JNI) implements ``Engine`` + ``Builder``. ``EchoEngine`` is a dependency-free
reference implementation used by the self-test and for wiring/bring-up before a
real backend is available.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from exo_core.inference.shards import ShardMetadata
from exo_core.shared.types import new_runner_id

TaskId = str
CANCEL_ALL_TASKS = "__cancel_all__"


@dataclass
class GenerationTask:
    """A text-generation request (distilled from ``types.tasks.GenerationTask``)."""

    prompt: str
    max_tokens: int = 64
    task_id: TaskId = field(default_factory=new_runner_id)


@dataclass
class Chunk:
    """A streamed output chunk."""

    task_id: TaskId
    text: str
    finished: bool = False


class Engine(ABC):
    """Runs a model shard and produces output tokens/chunks."""

    def __init__(self) -> None:
        self._cancelled_tasks: set = set()

    def should_cancel(self, task_id: TaskId) -> bool:
        return task_id in self._cancelled_tasks or CANCEL_ALL_TASKS in self._cancelled_tasks

    def cancel(self, task_id: TaskId) -> None:
        self._cancelled_tasks.add(task_id)

    @abstractmethod
    def warmup(self) -> None: ...

    @abstractmethod
    def submit(self, task: GenerationTask) -> None: ...

    @abstractmethod
    def step(self) -> Iterable[Tuple[TaskId, Chunk]]:
        """Advance generation one step, yielding any produced chunks."""

    @abstractmethod
    def close(self) -> None: ...


class Builder(ABC):
    """Loads a shard and builds the ``Engine`` that runs it."""

    @abstractmethod
    def connect(self, shard: ShardMetadata) -> None: ...

    @abstractmethod
    def load(self, shard: ShardMetadata) -> Iterable[float]:
        """Load model weights, yielding progress in ``[0.0, 1.0]``."""

    @abstractmethod
    def build(self) -> Engine: ...

    @abstractmethod
    def close(self) -> None: ...


class EchoEngine(Engine):
    """Reference engine that echoes the prompt token-by-token.

    Only the last pipeline stage emits text; earlier stages are pass-through.
    This makes a multi-node ring demonstrable end-to-end without a model.
    """

    def __init__(self, shard: ShardMetadata) -> None:
        super().__init__()
        self.shard = shard
        self._queues: Dict[TaskId, List[str]] = {}

    def warmup(self) -> None:
        pass

    def submit(self, task: GenerationTask) -> None:
        tokens = task.prompt.split()[: task.max_tokens]
        # Only the shard holding the last layers "speaks"; upstream stages
        # forward hidden state (simulated here as a no-op passthrough).
        self._queues[task.task_id] = tokens if self.shard.is_last_layer else []

    def step(self) -> Iterable[Tuple[TaskId, Chunk]]:
        out: List[Tuple[TaskId, Chunk]] = []
        for task_id, tokens in list(self._queues.items()):
            if self.should_cancel(task_id):
                self._queues.pop(task_id, None)
                continue
            if tokens:
                token = tokens.pop(0)
                out.append((task_id, Chunk(task_id, token + " ", finished=False)))
            else:
                out.append((task_id, Chunk(task_id, "", finished=True)))
                self._queues.pop(task_id, None)
        return out

    def close(self) -> None:
        self._queues.clear()


class EchoBuilder(Builder):
    """Builds :class:`EchoEngine` instances (reference/bring-up backend)."""

    def __init__(self) -> None:
        self._shard: Optional[ShardMetadata] = None

    def connect(self, shard: ShardMetadata) -> None:
        self._shard = shard

    def load(self, shard: ShardMetadata) -> Iterable[float]:
        self._shard = shard
        return [0.5, 1.0]

    def build(self) -> Engine:
        assert self._shard is not None, "connect()/load() must be called first"
        return EchoEngine(self._shard)

    def close(self) -> None:
        self._shard = None
