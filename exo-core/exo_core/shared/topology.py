"""Pure-Python cluster topology graph.

Upstream ``exo.shared.topology.Topology`` is backed by ``rustworkx`` (a Rust
extension unavailable on Android). This is a dependency-free re-implementation of
the subset used by the partition/placement logic:

- add/remove nodes and (directed) connections
- enumerate simple cycles (used to find rings of devices)
- select the ring/cycle a model instance will be placed on

The ``Cycle`` type mirrors ``exo.shared.types.topology.Cycle`` (an ordered list
of ``NodeId`` forming a ring).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from exo_core.shared.types import NodeId


@dataclass(frozen=True)
class Cycle:
    """An ordered ring of nodes (distilled from ``types.topology.Cycle``)."""

    node_ids: List[NodeId]

    def __len__(self) -> int:
        return len(self.node_ids)

    def __iter__(self):
        return iter(self.node_ids)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self.node_ids


@dataclass
class Topology:
    """Directed connectivity graph between mesh nodes."""

    _nodes: Set[NodeId] = field(default_factory=set)
    _edges: Dict[NodeId, Set[NodeId]] = field(default_factory=dict)

    # -- mutation -----------------------------------------------------------
    def add_node(self, node_id: NodeId) -> None:
        self._nodes.add(node_id)
        self._edges.setdefault(node_id, set())

    def remove_node(self, node_id: NodeId) -> None:
        self._nodes.discard(node_id)
        self._edges.pop(node_id, None)
        for peers in self._edges.values():
            peers.discard(node_id)

    def add_connection(self, a: NodeId, b: NodeId, *, bidirectional: bool = True) -> None:
        self.add_node(a)
        self.add_node(b)
        self._edges[a].add(b)
        if bidirectional:
            self._edges[b].add(a)

    def remove_connection(self, a: NodeId, b: NodeId, *, bidirectional: bool = True) -> None:
        self._edges.get(a, set()).discard(b)
        if bidirectional:
            self._edges.get(b, set()).discard(a)

    # -- queries ------------------------------------------------------------
    def list_nodes(self) -> List[NodeId]:
        return list(self._nodes)

    def neighbours(self, node_id: NodeId) -> Set[NodeId]:
        return set(self._edges.get(node_id, set()))

    def is_connected(self, a: NodeId, b: NodeId) -> bool:
        return b in self._edges.get(a, set())

    def get_cycles(self) -> List[Cycle]:
        """Return simple cycles of length >= 2, plus singletons for lone nodes.

        A single node with no peers is a trivial "cycle" of length 1 (a model can
        still run wholly on one device). For multi-node rings we enumerate simple
        cycles using DFS and de-duplicate rotations/reflections.
        """
        cycles: List[Cycle] = []
        seen: Set[frozenset] = set()

        # Singletons (lone nodes) — a one-device deployment is valid.
        for node_id in self._nodes:
            if not self._edges.get(node_id):
                cycles.append(Cycle([node_id]))

        nodes = sorted(self._nodes)
        for start in nodes:
            self._dfs_cycles(start, start, [start], {start}, cycles, seen)
        return cycles

    def _dfs_cycles(
        self,
        start: NodeId,
        current: NodeId,
        path: List[NodeId],
        visited: Set[NodeId],
        cycles: List[Cycle],
        seen: Set[frozenset],
    ) -> None:
        for neighbour in sorted(self._edges.get(current, set())):
            if neighbour == start and len(path) >= 2:
                key = frozenset(path)
                if key not in seen:
                    seen.add(key)
                    cycles.append(Cycle(list(path)))
                continue
            if neighbour in visited or neighbour < start:
                # ``neighbour < start`` prunes rotations already covered by a
                # smaller start node, keeping enumeration bounded.
                continue
            visited.add(neighbour)
            path.append(neighbour)
            self._dfs_cycles(start, neighbour, path, visited, cycles, seen)
            path.pop()
            visited.discard(neighbour)
