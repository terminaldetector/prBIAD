"""Backend registry — select an inference ``Builder`` by name.

``echo``    -> reference builder (no deps).
``bridge``  -> host runtime via Chaquopy; requires ``runner=<HostLlmRunner>``.
``litert``/``tflite``/``onnx`` -> aliases of ``bridge``. From Python's side all
three native runtimes are identical (they run host-side); the *host* decides which
runtime the supplied ``runner`` uses. The alias is kept so callers can record
intent and map from the :class:`exo_core.shared.types.Backend` enum.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from exo_core.inference.backends.bridge import BridgeBuilder
from exo_core.inference.engine import Builder, EchoBuilder

BuilderFactory = Callable[..., Builder]

_REGISTRY: Dict[str, BuilderFactory] = {}


def register_backend(name: str, factory: BuilderFactory) -> None:
    _REGISTRY[name.lower()] = factory


def available_backends() -> List[str]:
    return sorted(_REGISTRY)


def get_builder(name: str, **opts: Any) -> Builder:
    """Construct a backend ``Builder`` by name.

    Examples::

        get_builder("echo")
        get_builder("litert", runner=kotlin_backend, model_path="/data/.../model.task")
    """
    key = name.lower()
    if key not in _REGISTRY:
        raise ValueError(
            "Unknown backend {!r}; available: {}".format(name, available_backends())
        )
    return _REGISTRY[key](**opts)


def _make_echo(**_opts: Any) -> Builder:
    return EchoBuilder()


def _make_bridge(runner: Any = None, model_path: Any = None, **_opts: Any) -> Builder:
    if runner is None:
        raise ValueError("bridge backend requires a host runner: get_builder('bridge', runner=...)")
    return BridgeBuilder(runner, model_path=model_path)


register_backend("echo", _make_echo)
register_backend("bridge", _make_bridge)
# Native runtimes all route through the bridge (host picks the actual runtime).
register_backend("litert", _make_bridge)
register_backend("tflite", _make_bridge)
register_backend("onnx", _make_bridge)
