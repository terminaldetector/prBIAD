"""``ExoNode`` — the top-level orchestrator.

Distilled/simplified from ``exo.main.Node`` + ``exo.master.Master`` +
``exo.worker.Worker``. A single class plays both roles here (there is no
separate election/master process): any node can act as *coordinator* for a
generation, partition the model across the discovered ring, and drive a
pipeline-parallel pass over the :class:`IMeshNetwork`.

Message handling is synchronous (the transport delivers inbound frames to a
callback); outbound sends are queued and flushed from the coordinator's async
driver so the same code works over the in-memory bus and a real async mesh.
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple

from exo_core.inference.engine import Builder, EchoBuilder, GenerationTask
from exo_core.inference.shards import PipelineShardMetadata, ShardMetadata, Sharding
from exo_core.inference.sharder import get_shard_assignments
from exo_core.log import get_logger
from exo_core.networking import protocol as proto
from exo_core.networking.mesh import IMeshNetwork
from exo_core.shared.topology import Topology
from exo_core.shared.types import Memory, MemoryUsage, ModelCard, NodeId
from exo_core.topology.partition import select_cycle_for_model

logger = get_logger("node")


class ExoNode:
    def __init__(
        self,
        node_id: str,
        mesh: IMeshNetwork,
        available_memory: Memory,
        builder: Optional[Builder] = None,
    ) -> None:
        self.node_id = node_id
        self.mesh = mesh
        self.available_memory = available_memory
        self._builder = builder or EchoBuilder()

        self._peers_memory: Dict[str, Memory] = {node_id: available_memory}
        self._shard: Optional[ShardMetadata] = None
        self._ring: List[str] = []
        self._outbox: List[Tuple[Optional[str], bytes]] = []

        # Coordinator-side collection state.
        self._collected: Dict[str, List[str]] = {}
        self._done_tasks: set = set()
        self._running = False

        mesh.register_handler(self._on_message)

    # -- lifecycle ----------------------------------------------------------
    async def announce(self) -> None:
        await self.mesh.broadcast(proto.announce(self.node_id, self.available_memory.in_bytes).encode())

    async def run_forever(self, poll_s: float = 0.002) -> None:
        """Continuously flush queued outbound messages (worker/satellite role)."""
        self._running = True
        while self._running:
            await self._flush()
            await asyncio.sleep(poll_s)

    def stop(self) -> None:
        self._running = False

    # -- inbound handling (synchronous) ------------------------------------
    def _on_message(self, from_node: str, data: bytes) -> None:
        msg = proto.Message.decode(data)
        if msg.type == proto.MsgType.ANNOUNCE.value:
            self._peers_memory[msg.body["node_id"]] = Memory(int(msg.body["memory"]))
        elif msg.type == proto.MsgType.ASSIGN.value:
            self._handle_assign(msg)
        elif msg.type == proto.MsgType.PROMPT.value:
            self._handle_prompt(msg)
        elif msg.type == proto.MsgType.TOKEN.value:
            self._collected.setdefault(msg.body["task_id"], []).append(msg.body["text"])
        elif msg.type == proto.MsgType.DONE.value:
            self._done_tasks.add(msg.body["task_id"])

    def _handle_assign(self, msg: proto.Message) -> None:
        self._ring = list(msg.body["ring"])
        s = msg.body["shard"]
        card = ModelCard(
            model_id=msg.body["model_id"],
            n_layers=s["n_layers"],
            storage_size=Memory(),
            model_path=msg.body.get("model_path") or None,
        )
        self._shard = PipelineShardMetadata(
            model_card=card,
            device_rank=s["device_rank"],
            world_size=s["world_size"],
            start_layer=s["start_layer"],
            end_layer=s["end_layer"],
            n_layers=s["n_layers"],
        )
        self._builder.connect(self._shard)
        for _ in self._builder.load(self._shard):
            pass
        logger.info(
            "%s assigned layers [%d,%d) rank %d/%d",
            self.node_id, self._shard.start_layer, self._shard.end_layer,
            self._shard.device_rank, self._shard.world_size,
        )

    def _handle_prompt(self, msg: proto.Message) -> None:
        assert self._shard is not None, "received PROMPT before ASSIGN"
        task_id = msg.body["task_id"]
        coordinator = msg.body["coordinator"]
        text = msg.body["text"]

        if not self._shard.is_last_layer:
            # Forward activations to the next stage in the ring.
            my_idx = self._ring.index(self.node_id)
            nxt = self._ring[(my_idx + 1) % len(self._ring)]
            self._outbox.append((nxt, proto.prompt(task_id, coordinator, text).encode()))
            return

        # Last stage: run the engine and stream tokens back to the coordinator.
        engine = self._builder.build()
        engine.warmup()
        engine.submit(GenerationTask(prompt=text, task_id=task_id))
        finished = False
        while not finished:
            for _tid, chunk in engine.step():
                if chunk.finished:
                    finished = True
                    self._outbox.append((coordinator, proto.done(task_id).encode()))
                elif chunk.text:
                    self._outbox.append((coordinator, proto.token(task_id, chunk.text).encode()))
        engine.close()

    async def _flush(self) -> None:
        while self._outbox:
            target, data = self._outbox.pop(0)
            if target is None:
                await self.mesh.broadcast(data)
            else:
                await self.mesh.send_to(target, data)

    # -- coordinator role ---------------------------------------------------
    def plan(self, model_card: ModelCard, sharding: Sharding = Sharding.Pipeline):
        """Discover the ring, select a cycle and assign shards (coordinator)."""
        ring_ids = [self.node_id] + sorted(p for p in self._peers_memory if p != self.node_id)
        topo = Topology()
        for nid in ring_ids:
            topo.add_node(NodeId(nid))
        # Connect as a ring so cycle detection yields the full loop (or a
        # singleton when only this node is present).
        for i in range(len(ring_ids)):
            if len(ring_ids) >= 2:
                topo.add_connection(NodeId(ring_ids[i]), NodeId(ring_ids[(i + 1) % len(ring_ids)]))
        node_memory = {
            NodeId(nid): MemoryUsage(ram_total=mem, ram_available=mem)
            for nid, mem in self._peers_memory.items()
        }
        cycle = select_cycle_for_model(topo.get_cycles(), node_memory, model_card)
        if cycle is None:
            raise RuntimeError("No viable ring for model " + model_card.model_id)
        assignments = get_shard_assignments(model_card, cycle, sharding, node_memory)
        return cycle, assignments

    async def generate(
        self,
        model_card: ModelCard,
        prompt_text: str,
        sharding: Sharding = Sharding.Pipeline,
        timeout_s: float = 5.0,
    ) -> str:
        """Place the model, run one pipeline pass and return the concatenated output."""
        cycle, assignments = self.plan(model_card, sharding)
        ring = [str(n) for n in cycle.node_ids]

        # Broadcast per-node shard assignments.
        for nid in cycle.node_ids:
            shard = assignments.shard_for_node(nid)
            body_shard = {
                "device_rank": shard.device_rank,
                "world_size": shard.world_size,
                "start_layer": shard.start_layer,
                "end_layer": shard.end_layer,
                "n_layers": shard.n_layers,
            }
            self._outbox.append((
                str(nid),
                proto.assign(ring, model_card.model_id, body_shard, model_card.model_path or "").encode(),
            ))
        await self._flush()

        # Kick off the pipeline at the first stage.
        task_id = "task-" + model_card.model_id
        self._collected[task_id] = []
        self._outbox.append((ring[0], proto.prompt(task_id, self.node_id, prompt_text).encode()))

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while task_id not in self._done_tasks and loop.time() < deadline:
            await self._flush()
            await asyncio.sleep(0.005)
        await self._flush()

        return "".join(self._collected.get(task_id, [])).strip()
