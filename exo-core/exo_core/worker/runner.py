"""In-process runner.

Upstream ``exo.worker.runner`` isolates each engine in a spawned
``multiprocessing`` subprocess (via ``AsyncProcess`` + ``mp_channel``). Android
processes cannot fork/spawn Python subprocesses under Chaquopy, so this runner
drives the engine on a background *thread* instead, exposing the same
submit/collect lifecycle. It is deliberately simple and single-model.
"""

from __future__ import annotations

import threading
from queue import Empty, Queue
from typing import Callable, Optional

from exo_core.inference.engine import Builder, Chunk, Engine, GenerationTask
from exo_core.inference.shards import ShardMetadata
from exo_core.log import get_logger
from exo_core.worker.planner import RunnerPhase, plan_next_phase

logger = get_logger("worker.runner")

ChunkCallback = Callable[[Chunk], None]


class Runner:
    """Owns a :class:`Builder`/:class:`Engine` and runs its step loop on a thread."""

    def __init__(self, shard: ShardMetadata, builder: Builder) -> None:
        self.shard = shard
        self._builder = builder
        self._engine: Optional[Engine] = None
        self._phase = RunnerPhase.IDLE
        self._tasks: "Queue[GenerationTask]" = Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._on_chunk: Optional[ChunkCallback] = None

    @property
    def phase(self) -> RunnerPhase:
        return self._phase

    def start(self, on_chunk: ChunkCallback, *, weights_present: bool = False) -> None:
        self._on_chunk = on_chunk
        # Drive the lifecycle planner to READY before running.
        while self._phase != RunnerPhase.READY:
            self._phase = plan_next_phase(
                self._phase, RunnerPhase.READY, weights_present=weights_present
            )
            self._apply_phase()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="exo-runner", daemon=True)
        self._thread.start()
        self._phase = RunnerPhase.RUNNING
        logger.info("Runner started for shard %s", self.shard.model_card.model_id)

    def _apply_phase(self) -> None:
        if self._phase == RunnerPhase.CONNECTING:
            self._builder.connect(self.shard)
        elif self._phase == RunnerPhase.LOADING:
            for _ in self._builder.load(self.shard):
                pass
        elif self._phase == RunnerPhase.READY:
            self._engine = self._builder.build()
            self._engine.warmup()

    def submit(self, task: GenerationTask) -> None:
        self._tasks.put(task)

    def _loop(self) -> None:
        assert self._engine is not None
        while not self._stop.is_set():
            try:
                task = self._tasks.get(timeout=0.05)
                self._engine.submit(task)
            except Empty:
                pass
            for _task_id, chunk in self._engine.step():
                if self._on_chunk is not None:
                    self._on_chunk(chunk)

    def stop(self) -> None:
        self._phase = RunnerPhase.STOPPING
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._engine is not None:
            self._engine.close()
        self._builder.close()
        self._phase = RunnerPhase.STOPPED
        logger.info("Runner stopped for shard %s", self.shard.model_card.model_id)
