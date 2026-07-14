"""Runnable self-test / demo for exo-core.

Runs with plain CPython (no Android, no third-party deps):

    python -m exo_core.selftest

Exercises the four distilled subsystems:
  1. memory-weighted layer partitioning
  2. pipeline shard assignment across heterogeneous nodes
  3. the threading-based in-process Runner + EchoEngine
  4. a 2-node pipeline ring over the in-memory mesh (Scenario 2/3 from the plan)
"""

from __future__ import annotations

import asyncio
import json

from exo_core.inference.backends import available_backends, get_builder
from exo_core.inference.engine import Chunk, EchoBuilder, GenerationTask
from exo_core.inference.shards import Sharding
from exo_core.inference.sharder import get_shard_assignments
from exo_core.networking.mesh import InMemoryMeshNetwork
from exo_core.node import ExoNode
from exo_core.shared.topology import Cycle
from exo_core.shared.types import Memory, MemoryUsage, ModelCard, NodeId
from exo_core.topology.partition import allocate_layers_proportionally
from exo_core.worker.runner import Runner


class FakeHostRunner:
    """Pure-Python stand-in for a Kotlin ``InferenceBackend`` (LiteRT/TFLite/ONNX).

    Echoes the prompt token-by-token via the same JSON ``poll()`` contract the real
    host runtime uses, so the bridge backend is exercised without a native runtime.
    """

    def __init__(self) -> None:
        self.loaded = None
        self._pending = {}

    def loadModel(self, model_path, shard_json):  # noqa: N802 (host naming)
        self.loaded = (model_path, json.loads(shard_json))

    def submit(self, task_id, prompt, max_tokens):
        self._pending[task_id] = prompt.split()[:max_tokens]

    def poll(self):
        out = []
        for tid, toks in list(self._pending.items()):
            if toks:
                out.append({"task_id": tid, "text": toks.pop(0) + " ", "finished": False})
            else:
                out.append({"task_id": tid, "text": "", "finished": True})
                del self._pending[tid]
        return json.dumps(out)

    def cancel(self, task_id):
        self._pending.pop(task_id, None)

    def close(self):
        self._pending.clear()


def test_partition() -> None:
    # 6 layers across 3 nodes with 50% / 25% / 25% memory -> [3, 2, 1] (largest remainder)
    alloc = allocate_layers_proportionally(6, [0.5, 0.25, 0.25])
    assert sum(alloc) == 6, alloc
    assert all(x >= 1 for x in alloc), alloc
    assert alloc == [3, 2, 1], alloc
    print("  partition: 6 layers @ [0.5,0.25,0.25] -> {}".format(alloc))


def test_shard_assignment() -> None:
    card = ModelCard(model_id="demo-llm", n_layers=6, storage_size=Memory.from_gb(2))
    a, b = NodeId("A"), NodeId("B")
    cycle = Cycle([a, b])
    node_memory = {
        a: MemoryUsage(ram_available=Memory.from_gb(8)),
        b: MemoryUsage(ram_available=Memory.from_gb(4)),
    }
    assigns = get_shard_assignments(card, cycle, Sharding.Pipeline, node_memory)
    sa = assigns.shard_for_node(a)
    sb = assigns.shard_for_node(b)
    assert sa.start_layer == 0 and sa.is_first_layer, sa
    assert sb.is_last_layer and sb.end_layer == 6, sb
    assert sa.end_layer == sb.start_layer, (sa, sb)
    # 8:4 memory -> 4:2 layers
    assert (sa.end_layer - sa.start_layer, sb.end_layer - sb.start_layer) == (4, 2)
    print("  shards: A=[{},{}) B=[{},{})".format(sa.start_layer, sa.end_layer, sb.start_layer, sb.end_layer))


def test_runner() -> None:
    card = ModelCard(model_id="demo-llm", n_layers=2, storage_size=Memory())
    cycle = Cycle([NodeId("solo")])
    node_memory = {NodeId("solo"): MemoryUsage(ram_available=Memory.from_gb(8))}
    assigns = get_shard_assignments(card, cycle, Sharding.Pipeline, node_memory)
    shard = assigns.shard_for_node(NodeId("solo"))

    collected = []
    runner = Runner(shard, EchoBuilder())
    runner.start(lambda chunk: collected.append(chunk.text) if chunk.text else None)
    runner.submit(GenerationTask(prompt="quick brown fox"))
    import time
    for _ in range(50):
        if "".join(collected).strip() == "quick brown fox":
            break
        time.sleep(0.02)
    runner.stop()
    out = "".join(collected).strip()
    assert out == "quick brown fox", repr(out)
    print("  runner (threaded, single node): {!r}".format(out))


async def _distributed() -> str:
    bus = {}
    coordinator = ExoNode("nodeA", InMemoryMeshNetwork("nodeA", bus), Memory.from_gb(8))
    satellite = ExoNode("nodeB", InMemoryMeshNetwork("nodeB", bus), Memory.from_gb(4))
    await coordinator.announce()
    await satellite.announce()

    sat_task = asyncio.ensure_future(satellite.run_forever())
    try:
        card = ModelCard(model_id="demo-llm", n_layers=6, storage_size=Memory.from_gb(2))
        out = await coordinator.generate(card, "hello world foo bar", Sharding.Pipeline)
    finally:
        satellite.stop()
        sat_task.cancel()
    return out


def test_distributed() -> None:
    out = asyncio.run(_distributed())
    assert out == "hello world foo bar", repr(out)
    print("  ring (2 nodes, pipeline over mesh): {!r}".format(out))


def test_backend_registry() -> None:
    backends = available_backends()
    for expected in ("echo", "bridge", "litert", "tflite", "onnx"):
        assert expected in backends, backends
    try:
        get_builder("bridge")  # missing runner must fail loudly
        raise AssertionError("expected ValueError for bridge without runner")
    except ValueError:
        pass
    print("  registry: {}".format(backends))


def test_bridge_backend() -> None:
    card = ModelCard(model_id="demo-llm", n_layers=2, storage_size=Memory(), model_path="/data/model.task")
    cycle = Cycle([NodeId("solo")])
    node_memory = {NodeId("solo"): MemoryUsage(ram_available=Memory.from_gb(8))}
    shard = get_shard_assignments(card, cycle, Sharding.Pipeline, node_memory).shard_for_node(NodeId("solo"))

    runner = FakeHostRunner()
    builder = get_builder("litert", runner=runner, model_path=card.model_path)
    builder.connect(shard)
    list(builder.load(shard))
    engine = builder.build()
    engine.warmup()
    engine.submit(GenerationTask(prompt="alpha beta gamma", task_id="t1"))

    collected = []
    for _ in range(30):
        finished = False
        for _tid, chunk in engine.step():
            if chunk.finished:
                finished = True
            elif chunk.text:
                collected.append(chunk.text)
        if finished:
            break
    engine.close()

    out = "".join(collected).strip()
    assert out == "alpha beta gamma", repr(out)
    assert runner.loaded is not None and runner.loaded[0] == "/data/model.task", runner.loaded
    assert runner.loaded[1]["is_last_layer"] is True, runner.loaded[1]
    print("  bridge backend (host runtime via LiteRT alias): {!r}".format(out))


async def _distributed_bridge() -> str:
    bus = {}
    coordinator = ExoNode(
        "nodeA", InMemoryMeshNetwork("nodeA", bus), Memory.from_gb(8),
        builder=get_builder("litert", runner=FakeHostRunner()),
    )
    satellite = ExoNode(
        "nodeB", InMemoryMeshNetwork("nodeB", bus), Memory.from_gb(4),
        builder=get_builder("litert", runner=FakeHostRunner()),
    )
    await coordinator.announce()
    await satellite.announce()
    sat_task = asyncio.ensure_future(satellite.run_forever())
    try:
        card = ModelCard(
            model_id="demo-llm", n_layers=6, storage_size=Memory.from_gb(2),
            model_path="/data/demo.task",
        )
        return await coordinator.generate(card, "one two three", Sharding.Pipeline)
    finally:
        satellite.stop()
        sat_task.cancel()


def test_distributed_bridge() -> None:
    out = asyncio.run(_distributed_bridge())
    assert out == "one two three", repr(out)
    print("  ring (2 nodes, bridge backend on last stage): {!r}".format(out))


def _shard_json(shard) -> str:
    return json.dumps({
        "model_id": shard.model_card.model_id,
        "device_rank": shard.device_rank,
        "world_size": shard.world_size,
        "start_layer": shard.start_layer,
        "end_layer": shard.end_layer,
        "n_layers": shard.n_layers,
        "is_first_layer": shard.is_first_layer,
        "is_last_layer": shard.is_last_layer,
    })


async def _sharded_split():
    from exo_core.inference.sharded import NumericShardRunner, ShardedPipeline

    ring = ["A", "B"]
    card = ModelCard(model_id="demo-llm", n_layers=6, storage_size=Memory.from_gb(2))
    node_memory = {
        NodeId("A"): MemoryUsage(ram_available=Memory.from_gb(8)),
        NodeId("B"): MemoryUsage(ram_available=Memory.from_gb(4)),
    }
    assigns = get_shard_assignments(card, Cycle([NodeId("A"), NodeId("B")]), Sharding.Pipeline, node_memory)

    bus = {}
    pipes = {}
    bands = {}
    for nid in ring:
        shard = assigns.shard_for_node(NodeId(nid))
        bands[nid] = (shard.start_layer, shard.end_layer)
        runner = NumericShardRunner()
        runner.load(_shard_json(shard))
        pipe = ShardedPipeline(nid, InMemoryMeshNetwork(nid, bus), ring, runner, coordinator="A", max_new_tokens=3)
        pipes[nid] = pipe

    b_task = asyncio.ensure_future(pipes["B"].run_forever())
    try:
        tokens = await pipes["A"].generate(prompt_token_ids=[1])
    finally:
        pipes["B"].stop()
        b_task.cancel()
    return tokens, bands


def test_sharded_split() -> None:
    tokens, bands = asyncio.run(_sharded_split())
    # A owns layers [0,4), B owns [4,6): 6 layers total. Each generated token is the
    # previous seed advanced by ALL 6 layers -> +6 per step. Seed = 1 -> 7, 13, 19.
    # This only holds if BOTH devices ran their band (A:+4, B:+2).
    assert bands["A"] == (0, 4) and bands["B"] == (4, 6), bands
    assert tokens == [7, 13, 19], tokens
    print("  layer split A{}+B{} -> tokens {} (each +6 = both shards ran)".format(
        bands["A"], bands["B"], tokens))


def main() -> None:
    print("exo-core self-test")
    print("[1] partitioning")
    test_partition()
    print("[2] shard assignment")
    test_shard_assignment()
    print("[3] threaded runner")
    test_runner()
    print("[4] distributed ring generation")
    test_distributed()
    print("[5] backend registry")
    test_backend_registry()
    print("[6] bridge backend (LiteRT/TFLite/ONNX host runtime)")
    test_bridge_backend()
    print("[7] distributed ring over bridge backend")
    test_distributed_bridge()
    print("[8] TRUE layer-sharded split (activation-passing ring)")
    test_sharded_split()
    print("ALL PASSED")


if __name__ == "__main__":
    main()
