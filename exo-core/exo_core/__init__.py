"""exo-core: a distilled, Android-portable core extracted from exo-explore/exo.

This package keeps only the *orchestration* logic of exo that is portable to
Android (via Chaquopy) and free of the heavy, platform-specific dependencies of
upstream exo (MLX, Zenoh/`exo_rs`, rustworkx, FastAPI, multiprocessing):

- ``exo_core.topology``   -- memory-weighted ring partitioning strategies
- ``exo_core.inference``  -- shard metadata, shard assignment, and the inference
                              ``Engine``/``Builder`` abstractions
- ``exo_core.worker``     -- runner lifecycle planning and an in-process runner
- ``exo_core.shared``     -- common value types, cluster state and a pure-Python
                              topology graph
- ``exo_core.networking`` -- the abstract ``IMeshNetwork`` transport interface and
                              a ``BitChatNetworkAdapter`` that bridges to the
                              Kotlin ``bitchat-core`` mesh

See ``DISTILLATION_REPORT.md`` for exactly what was extracted, abstracted or
stubbed relative to upstream exo.
"""

from __future__ import annotations

__version__ = "0.1.0"
__exo_upstream_version__ = "0.3.70"

__all__ = ["__version__", "__exo_upstream_version__"]
