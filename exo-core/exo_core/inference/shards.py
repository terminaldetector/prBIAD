"""Shard metadata + assignment records.

Distilled from ``exo.shared.types.worker.shards`` and
``exo.shared.types.worker.runners.ShardAssignments``. Pydantic ``TaggedModel``
is replaced with dataclasses; the ``CfgShardMetadata`` (image/CFG-parallel)
variant is dropped since the Android core targets text generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Union

from exo_core.shared.types import ModelCard, NodeId, RunnerId


class Sharding(str, Enum):
    Tensor = "Tensor"
    Pipeline = "Pipeline"


@dataclass(frozen=True)
class BaseShardMetadata:
    """A specific shard of a model, ready to run on one device.

    Layers form a half-open interval ``[start_layer, end_layer)``.
    """

    model_card: ModelCard
    device_rank: int
    world_size: int
    start_layer: int
    end_layer: int
    n_layers: int

    @property
    def is_first_layer(self) -> bool:
        return self.start_layer == 0

    @property
    def is_last_layer(self) -> bool:
        return self.end_layer == self.n_layers


@dataclass(frozen=True)
class PipelineShardMetadata(BaseShardMetadata):
    """Pipeline-parallel shard (a contiguous band of layers)."""


@dataclass(frozen=True)
class TensorShardMetadata(BaseShardMetadata):
    """Tensor-parallel shard (all layers, split within each layer)."""


ShardMetadata = Union[PipelineShardMetadata, TensorShardMetadata]


@dataclass(frozen=True)
class ShardAssignments:
    """Mapping of a placed model instance to per-node shards.

    Distilled from ``exo.shared.types.worker.runners.ShardAssignments``.
    """

    model_id: str
    runner_to_shard: Dict[RunnerId, ShardMetadata] = field(default_factory=dict)
    node_to_runner: Dict[NodeId, RunnerId] = field(default_factory=dict)

    def shard_for_node(self, node_id: NodeId) -> ShardMetadata:
        return self.runner_to_shard[self.node_to_runner[node_id]]
