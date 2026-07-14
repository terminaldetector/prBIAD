"""Concrete inference backends for exo-core.

exo-core is transport- and runtime-agnostic: the ``Engine``/``Builder`` ABCs in
``exo_core.inference.engine`` say *what* an engine must do, and a backend says
*how*. Two backends ship here:

- ``echo``   -- the dependency-free reference (``EchoBuilder``) used for bring-up.
- ``bridge`` -- delegates real inference to a **host runtime** (Kotlin LiteRT /
                TFLite / ONNX Runtime) supplied via Chaquopy. This is the Android
                path; see ``exo_core.inference.backends.bridge`` and ``BACKENDS.md``.

Use ``get_builder(name, **opts)`` to construct a backend by name.
"""

from __future__ import annotations

from exo_core.inference.backends.bridge import (
    BridgeBuilder,
    BridgeEngine,
    HostLlmRunner,
)
from exo_core.inference.backends.registry import (
    available_backends,
    get_builder,
    register_backend,
)

__all__ = [
    "BridgeBuilder",
    "BridgeEngine",
    "HostLlmRunner",
    "get_builder",
    "register_backend",
    "available_backends",
]
