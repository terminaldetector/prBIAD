"""Memory-weighted partition strategy.

Distilled from ``exo.master.placement_utils`` and ``exo.master.placement``.
``allocate_layers_proportionally`` is ported *verbatim* (it is already pure
Python); the cycle-filtering / selection helpers are simplified to drop the
MLX ring/JACCL host-matrix machinery that is Apple-specific.
"""

from __future__ import annotations

from typing import List, Mapping, Optional

from exo_core.log import get_logger
from exo_core.shared.topology import Cycle
from exo_core.shared.types import Memory, MemoryUsage, ModelCard, NodeId

logger = get_logger("topology.partition")


def allocate_layers_proportionally(
    total_layers: int,
    memory_fractions: List[float],
) -> List[int]:
    """Split ``total_layers`` across nodes proportionally to memory fractions.

    Ported verbatim from ``exo.master.placement_utils.allocate_layers_proportionally``:
    uses the *largest remainder* method and guarantees at least one layer per node.
    """
    n = len(memory_fractions)
    if n == 0:
        raise ValueError("Cannot allocate layers to an empty node list")
    if total_layers < n:
        raise ValueError(
            "Cannot distribute {} layers across {} nodes "
            "(need at least 1 layer per node)".format(total_layers, n)
        )

    # Largest remainder: floor each, then distribute remainder by fractional part
    raw = [f * total_layers for f in memory_fractions]
    result = [int(r) for r in raw]
    by_remainder = sorted(range(n), key=lambda i: raw[i] - result[i], reverse=True)
    for i in range(total_layers - sum(result)):
        result[by_remainder[i]] += 1

    # Ensure minimum 1 per node by taking from the largest
    for i in range(n):
        if result[i] == 0:
            max_idx = max(range(n), key=lambda j: result[j])
            assert result[max_idx] > 1
            result[max_idx] -= 1
            result[i] = 1

    return result


def filter_cycles_by_memory(
    cycles: List[Cycle],
    node_memory: Mapping[NodeId, MemoryUsage],
    required_memory: Memory,
) -> List[Cycle]:
    """Keep only cycles whose combined available RAM fits the model.

    Ported from ``exo.master.placement_utils.filter_cycles_by_memory``.
    """
    filtered: List[Cycle] = []
    for cycle in cycles:
        if not all(node in node_memory for node in cycle):
            continue
        total_mem = Memory()
        for node_id in cycle.node_ids:
            total_mem = total_mem + node_memory[node_id].ram_available
        if total_mem >= required_memory:
            filtered.append(cycle)
    return filtered


def get_smallest_cycles(cycles: List[Cycle]) -> List[Cycle]:
    """Return the cycles that use the fewest nodes (ported verbatim)."""
    if not cycles:
        return []
    min_nodes = min(len(cycle) for cycle in cycles)
    return [cycle for cycle in cycles if len(cycle) == min_nodes]


def select_cycle_for_model(
    cycles: List[Cycle],
    node_memory: Mapping[NodeId, MemoryUsage],
    model_card: ModelCard,
) -> Optional[Cycle]:
    """Pick the ring a model instance should be placed on.

    Distilled from ``exo.master.placement.place_instance`` (which additionally
    scores by download progress and RDMA/thunderbolt topology). Here we:

    1. keep only cycles with enough combined memory for the model, then
    2. prefer the smallest such cycle (fewest hops), then
    3. break ties by maximum total available memory.
    """
    viable = filter_cycles_by_memory(cycles, node_memory, model_card.storage_size)
    if not viable:
        logger.warning(
            "No cycle has enough memory for %s (needs %.2f GB)",
            model_card.model_id,
            model_card.storage_size.in_gb,
        )
        return None

    smallest = get_smallest_cycles(viable)

    def total_available(cycle: Cycle) -> int:
        total = 0
        for node_id in cycle.node_ids:
            total += node_memory[node_id].ram_available.in_bytes
        return total

    chosen = max(smallest, key=total_available)
    logger.info(
        "Placed %s on ring of %d node(s): %s",
        model_card.model_id,
        len(chosen),
        list(chosen.node_ids),
    )
    return chosen
