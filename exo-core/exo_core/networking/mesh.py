"""Abstract mesh transport.

Upstream exo has *no* Python mesh interface — networking is a Rust ``exo_rs``
handle (Zenoh gossipsub). This module defines the ``IMeshNetwork`` abstraction
described in the integration plan, so exo's orchestration can run over *any*
transport (in-memory for tests, or the Kotlin ``bitchat-core`` Bluetooth mesh).
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Dict, List

# A handler receives ``(from_node_id, payload)``. ``from_node_id`` is "" for
# broadcasts whose origin is unknown to the transport.
MessageHandler = Callable[[str, bytes], None]


class IMeshNetwork(ABC):
    """Transport abstraction used by the exo node as its network layer."""

    @abstractmethod
    async def broadcast(self, message: bytes) -> None:
        """Send ``message`` to every reachable node."""

    @abstractmethod
    async def send_to(self, node_id: str, message: bytes) -> None:
        """Send ``message`` to a single node."""

    @abstractmethod
    async def get_nodes(self) -> List[str]:
        """Return the currently reachable node IDs (excluding self)."""

    @abstractmethod
    def register_handler(self, handler: MessageHandler) -> None:
        """Register a callback invoked for each inbound message."""


class InMemoryMeshNetwork(IMeshNetwork):
    """Process-local mesh used by tests/self-test.

    All instances constructed with the same ``bus`` dict see each other, so a
    multi-node ring can be simulated in a single process.
    """

    def __init__(self, node_id: str, bus: Dict[str, "InMemoryMeshNetwork"]) -> None:
        self.node_id = node_id
        self._bus = bus
        self._handlers: List[MessageHandler] = []
        bus[node_id] = self

    def register_handler(self, handler: MessageHandler) -> None:
        self._handlers.append(handler)

    def _deliver(self, from_node: str, message: bytes) -> None:
        for handler in self._handlers:
            handler(from_node, message)

    async def broadcast(self, message: bytes) -> None:
        for node_id, peer in list(self._bus.items()):
            if node_id != self.node_id:
                peer._deliver(self.node_id, message)
        await asyncio.sleep(0)

    async def send_to(self, node_id: str, message: bytes) -> None:
        peer = self._bus.get(node_id)
        if peer is not None:
            peer._deliver(self.node_id, message)
        await asyncio.sleep(0)

    async def get_nodes(self) -> List[str]:
        return [n for n in self._bus if n != self.node_id]
