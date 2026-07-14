"""Shard assignment.

Distilled from ``exo.master.placement_utils.get_shard_assignments*``. The
memory-weighted pipeline split and the tensor-parallel fan-out are preserved;
the MLX/CFG/RDMA specifics are removed.
"""

from __future__ import annotations

from typing import Dict, List, Mapping

from exo_core.inference.shards import (
    PipelineShardMetadata,
    ShardAssignments,
    Sharding,
    ShardMetadata,
    TensorShardMetadata,
)
from exo_core.shared.topology import Cycle
from exo_core.shared.types import (
    Memory,
    MemoryUsage,
    ModelCard,
    NodeId,
    RunnerId,
    new_runner_id,
)
from exo_core.topology.partition import allocate_layers_proportionally


def _total_available(node_ids: List[NodeId], node_memory: Mapping[NodeId, MemoryUsage]) -> Memory:
    total = Memory()
    for node_id in node_ids:
        total = total + node_memory[node_id].ram_available
    if total.in_bytes == 0:
        raise ValueError("Cannot create shard assignments: total available memory is 0")
    return total


def _pipeline_assignments(
    model_card: ModelCard,
    cycle: Cycle,
    node_memory: Mapping[NodeId, MemoryUsage],
) -> ShardAssignments:
    if not cycle.node_ids:
        raise ValueError("Cannot create shard assignments for empty node cycle")

    total_memory = _total_available(cycle.node_ids, node_memory)
    fractions = [
        node_memory[node_id].ram_available / total_memory for node_id in cycle.node_ids
    ]
    layer_allocations = allocate_layers_proportionally(model_card.n_layers, fractions)

    runner_to_shard: Dict[RunnerId, ShardMetadata] = {}
    node_to_runner: Dict[NodeId, RunnerId] = {}

    for pipeline_rank, node_id in enumerate(cycle.node_ids):
        layers_before = sum(layer_allocations[:pipeline_rank])
        node_layers = layer_allocations[pipeline_rank]
        shard = PipelineShardMetadata(
            model_card=model_card,
            device_rank=pipeline_rank,
            world_size=len(cycle),
            start_layer=layers_before,
            end_layer=layers_before + node_layers,
            n_layers=model_card.n_layers,
        )
        runner_id = new_runner_id()
        runner_to_shard[runner_id] = shard
        node_to_runner[node_id] = runner_id

    return ShardAssignments(
        model_id=model_card.model_id,
        runner_to_shard=runner_to_shard,
        node_to_runner=node_to_runner,
    )


def _tensor_assignments(model_card: ModelCard, cycle: Cycle) -> ShardAssignments:
    total_layers = model_card.n_layers
    world_size = len(cycle)
    runner_to_shard: Dict[RunnerId, ShardMetadata] = {}
    node_to_runner: Dict[NodeId, RunnerId] = {}

    for i, node_id in enumerate(cycle.node_ids):
        shard = TensorShardMetadata(
            model_card=model_card,
            device_rank=i,
            world_size=world_size,
            start_layer=0,
            end_layer=total_layers,
            n_layers=total_layers,
        )
        runner_id = new_runner_id()
        runner_to_shard[runner_id] = shard
        node_to_runner[node_id] = runner_id

    return ShardAssignments(
        model_id=model_card.model_id,
        runner_to_shard=runner_to_shard,
        node_to_runner=node_to_runner,
    )


def get_shard_assignments(
    model_card: ModelCard,
    cycle: Cycle,
    sharding: Sharding,
    node_memory: Mapping[NodeId, MemoryUsage],
) -> ShardAssignments:
    """Assign shards across a ring (distilled from ``get_shard_assignments``)."""
    if sharding == Sharding.Pipeline:
        return _pipeline_assignments(model_card, cycle, node_memory)
    if sharding == Sharding.Tensor:
        return _tensor_assignments(model_card, cycle)
    raise ValueError("Unknown sharding: {}".format(sharding))
