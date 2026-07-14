"""Bridge backend: run inference on a host-provided runtime (LiteRT/TFLite/ONNX).

exo-core is pure Python and cannot host a native LLM runtime itself. Instead, the
Android app implements the model runtime in Kotlin (Google AI Edge **LiteRT** LLM
Inference API, **TFLite**, or **ONNX Runtime**) and passes a *runner object* into
Python through Chaquopy. ``BridgeEngine``/``BridgeBuilder`` adapt that runner to
exo-core's ``Engine``/``Builder`` contract.

The Python↔host boundary is intentionally string-based (prompt in, JSON chunks
out) so it works uniformly across Chaquopy and plain CPython (tests use a
pure-Python fake runner).

Host runner contract (Kotlin ``InferenceBackend``; see ``BACKENDS.md``)::

    interface InferenceBackend {
        // Load weights for this shard. `shardJson` describes the layer band so a
        // sharding-capable runtime can load a sub-model; full-model runtimes ignore it.
        fun loadModel(modelPath: String, shardJson: String)
        fun submit(taskId: String, prompt: String, maxTokens: Int)
        // Return a JSON array of pending chunks, then clear them:
        //   [{"task_id": "...", "text": "tok", "finished": false}, ...]
        fun poll(): String
        fun cancel(taskId: String)
        fun close()
    }
"""

from __future__ import annotations

import json
from typing import Iterable, List, Optional, Tuple

try:  # ``Protocol`` is 3.8+, but guard for very old runtimes.
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    Protocol = object  # type: ignore

    def runtime_checkable(cls):  # type: ignore
        return cls

from exo_core.inference.engine import Builder, Chunk, Engine, GenerationTask, TaskId
from exo_core.inference.shards import ShardMetadata
from exo_core.log import get_logger

logger = get_logger("inference.bridge")


@runtime_checkable
class HostLlmRunner(Protocol):
    """The host (Kotlin) object that actually runs the model.

    Any object exposing these methods works — a Chaquopy-wrapped Kotlin
    ``InferenceBackend`` in production, or a plain Python fake in tests.
    """

    def loadModel(self, model_path: str, shard_json: str) -> None: ...  # noqa: N802
    def submit(self, task_id: str, prompt: str, max_tokens: int) -> None: ...
    def poll(self) -> str: ...
    def cancel(self, task_id: str) -> None: ...
    def close(self) -> None: ...


def _shard_to_json(shard: ShardMetadata) -> str:
    return json.dumps(
        {
            "model_id": shard.model_card.model_id,
            "device_rank": shard.device_rank,
            "world_size": shard.world_size,
            "start_layer": shard.start_layer,
            "end_layer": shard.end_layer,
            "n_layers": shard.n_layers,
            "is_first_layer": shard.is_first_layer,
            "is_last_layer": shard.is_last_layer,
        }
    )


class BridgeEngine(Engine):
    """Adapts a :class:`HostLlmRunner` to the exo-core ``Engine`` contract."""

    def __init__(self, runner: "HostLlmRunner", shard: ShardMetadata) -> None:
        super().__init__()
        self._runner = runner
        self.shard = shard

    def warmup(self) -> None:
        # Optional: a real runner may warm caches during loadModel(); nothing to do.
        pass

    def submit(self, task: GenerationTask) -> None:
        self._runner.submit(task.task_id, task.prompt, task.max_tokens)

    def step(self) -> Iterable[Tuple[TaskId, Chunk]]:
        raw = self._runner.poll()
        if not raw:
            return []
        out: List[Tuple[TaskId, Chunk]] = []
        try:
            items = json.loads(raw)
        except (ValueError, TypeError) as exc:
            logger.warning("bridge poll() returned invalid JSON: %s", exc)
            return []
        for item in items:
            task_id = str(item.get("task_id", ""))
            if self.should_cancel(task_id):
                continue
            out.append(
                (
                    task_id,
                    Chunk(
                        task_id=task_id,
                        text=str(item.get("text", "")),
                        finished=bool(item.get("finished", False)),
                    ),
                )
            )
        return out

    def cancel(self, task_id: TaskId) -> None:
        super().cancel(task_id)
        try:
            self._runner.cancel(task_id)
        except Exception as exc:  # pragma: no cover - host-dependent
            logger.warning("host cancel() failed: %s", exc)

    def close(self) -> None:
        try:
            self._runner.close()
        except Exception as exc:  # pragma: no cover
            logger.warning("host close() failed: %s", exc)


class BridgeBuilder(Builder):
    """Builds :class:`BridgeEngine` instances backed by a host runtime.

    ``model_path`` overrides ``shard.model_card.model_path`` when provided (useful
    when the app resolves the on-device path at runtime).
    """

    def __init__(self, runner: "HostLlmRunner", model_path: Optional[str] = None) -> None:
        self._runner = runner
        self._model_path = model_path
        self._shard: Optional[ShardMetadata] = None

    def connect(self, shard: ShardMetadata) -> None:
        self._shard = shard

    def load(self, shard: ShardMetadata) -> Iterable[float]:
        self._shard = shard
        path = self._model_path or shard.model_card.model_path or ""
        if not path:
            logger.warning(
                "No model_path for %s; host runtime must resolve it itself",
                shard.model_card.model_id,
            )
        self._runner.loadModel(path, _shard_to_json(shard))
        return [1.0]

    def build(self) -> Engine:
        assert self._shard is not None, "connect()/load() must be called first"
        return BridgeEngine(self._runner, self._shard)

    def close(self) -> None:
        try:
            self._runner.close()
        except Exception:  # pragma: no cover
            pass
