"""``IMeshNetwork`` backed by the Kotlin ``bitchat-core`` Bluetooth mesh.

Per the integration plan the adapter is *thin on the Python side*: the actual
transport is implemented in Kotlin (``bitchat-core`` / ``MeshService``) and
passed into Python via Chaquopy. The Kotlin object ("bridge") must expose:

    interface ExoMeshBridge {
        fun broadcast(message: ByteArray)
        fun sendTo(nodeId: String, message: ByteArray)
        fun getNodes(): Array<String>          // or List<String>
        fun setHandler(handler: PyMeshHandler)  // handler.onMessage(from, bytes)
    }

where ``PyMeshHandler`` is *this* adapter (Chaquopy lets Kotlin call back into
a Python object). When no bridge is supplied the adapter logs calls and behaves
as a no-op stub, which keeps the exo pipeline runnable during bring-up.
"""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from exo_core.log import get_logger
from exo_core.networking.mesh import IMeshNetwork, MessageHandler

logger = get_logger("networking.bitchat")


class BitChatNetworkAdapter(IMeshNetwork):
    def __init__(self, bridge: Optional[Any] = None) -> None:
        """``bridge`` is the Kotlin ``ExoMeshBridge`` (or ``None`` for stub mode)."""
        self._bridge = bridge
        self._handlers: List[MessageHandler] = []
        if bridge is not None:
            try:
                bridge.setHandler(self)
            except Exception as exc:  # pragma: no cover - depends on Chaquopy
                logger.warning("Failed to register handler on bridge: %s", exc)

    # -- IMeshNetwork -------------------------------------------------------
    def register_handler(self, handler: MessageHandler) -> None:
        self._handlers.append(handler)

    async def broadcast(self, message: bytes) -> None:
        if self._bridge is None:
            logger.debug("[stub] broadcast(%d bytes)", len(message))
        else:
            self._bridge.broadcast(_to_java_bytes(message))
        await asyncio.sleep(0)

    async def send_to(self, node_id: str, message: bytes) -> None:
        if self._bridge is None:
            logger.debug("[stub] send_to(%s, %d bytes)", node_id, len(message))
        else:
            self._bridge.sendTo(node_id, _to_java_bytes(message))
        await asyncio.sleep(0)

    async def get_nodes(self) -> List[str]:
        if self._bridge is None:
            return []
        try:
            return [str(n) for n in self._bridge.getNodes()]
        except Exception as exc:  # pragma: no cover
            logger.warning("getNodes() failed: %s", exc)
            return []

    # -- called from Kotlin via Chaquopy -----------------------------------
    def onMessage(self, from_node: str, message: Any) -> None:  # noqa: N802 (Java naming)
        """Invoked by the Kotlin bridge when a mesh message arrives."""
        payload = bytes(message)
        for handler in self._handlers:
            try:
                handler(str(from_node), payload)
            except Exception as exc:  # pragma: no cover
                logger.warning("mesh handler raised: %s", exc)


def _to_java_bytes(data: bytes):
    """Best-effort conversion of ``bytes`` to a Java ``byte[]`` for Chaquopy.

    Under Chaquopy, ``bytes`` are auto-converted; when running on CPython we just
    return the ``bytes`` unchanged so the stub path works in tests.
    """
    try:  # pragma: no cover - only meaningful under Chaquopy
        from java import jarray, jbyte  # type: ignore

        arr = jarray(jbyte)(len(data))
        for i, b in enumerate(data):
            arr[i] = b - 256 if b > 127 else b
        return arr
    except Exception:
        return data
