"""Sharding metadata, shard assignment and inference engine abstractions."""

from __future__ import annotations

from exo_core.inference.shards import (
    PipelineShardMetadata,
    ShardAssignments,
    Sharding,
    ShardMetadata,
    TensorShardMetadata,
)
from exo_core.inference.sharder import get_shard_assignments
from exo_core.inference.engine import Builder, Engine, GenerationTask, EchoEngine
from exo_core.inference.backends import (
    BridgeBuilder,
    BridgeEngine,
    HostLlmRunner,
    available_backends,
    get_builder,
    register_backend,
)
from exo_core.inference.sharded import (
    NumericShardRunner,
    ShardedPipeline,
    ShardRunner,
)

__all__ = [
    "Sharding",
    "ShardMetadata",
    "PipelineShardMetadata",
    "TensorShardMetadata",
    "ShardAssignments",
    "get_shard_assignments",
    "Engine",
    "Builder",
    "GenerationTask",
    "EchoEngine",
    "BridgeBuilder",
    "BridgeEngine",
    "HostLlmRunner",
    "get_builder",
    "register_backend",
    "available_backends",
    "ShardRunner",
    "NumericShardRunner",
    "ShardedPipeline",
]
