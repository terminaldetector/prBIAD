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

from exo_core.inference.engine import Chunk, EchoBuilder, GenerationTask
from exo_core.inference.shards import Sharding
from exo_core.inference.sharder import get_shard_assignments
from exo_core.networking.mesh import InMemoryMeshNetwork
from exo_core.node import ExoNode
from exo_core.shared.topology import Cycle
from exo_core.shared.types import Memory, MemoryUsage, ModelCard, NodeId
from exo_core.topology.partition import allocate_layers_proportionally
from exo_core.worker.runner import Runner


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
    print("ALL PASSED")


if __name__ == "__main__":
    main()
