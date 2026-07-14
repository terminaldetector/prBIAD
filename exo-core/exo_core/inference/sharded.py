"""True layer-sharded pipeline parallelism over the mesh.

This is the mechanism for *actually splitting a model across devices*. Each device
runs a **sub-model** covering a band of layers; the interface between devices is the
**hidden-state tensor**, and the KV cache is partitioned (each device keeps the KV
for its own layers, so only activations cross the wire).

Because a decoder LLM embeds tokens at the *front* and samples at the *back*, decode
is a **ring**: the last shard samples a token id and sends it back to the first
shard (which owns the embedding); hidden states then flow forward again. This module
drives that ring over any :class:`~exo_core.networking.mesh.IMeshNetwork`.

The actual tensor math lives in a :class:`ShardRunner` implemented on the host
(Kotlin ONNX/TFLite sub-model — see ``SHARDING.md`` / ``integration/kotlin``). A
pure-Python :class:`NumericShardRunner` is provided so the pipeline is fully testable
without a model: it proves that *every layer on every device* contributes to each
generated token.
"""

from __future__ import annotations

import asyncio
import json
from typing import List, Optional, Tuple

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    Protocol = object  # type: ignore

    def runtime_checkable(cls):  # type: ignore
        return cls

from exo_core.log import get_logger
from exo_core.networking import protocol as proto
from exo_core.networking.mesh import IMeshNetwork

logger = get_logger("inference.sharded")


@runtime_checkable
class ShardRunner(Protocol):
    """Host object that executes one shard's layers.

    ``embed`` is only called on the first shard, ``sample``/``detok`` only on the
    last shard, ``forward`` on every shard. Blobs are opaque serialized tensors
    (the host decides the encoding; the mesh only relays bytes).
    """

    def load(self, shard_json: str) -> None: ...
    def embed(self, token_id: int) -> bytes: ...          # first shard: token -> hidden
    def forward(self, hidden: bytes) -> bytes: ...        # any shard: hidden -> hidden
    def sample(self, hidden: bytes) -> int: ...           # last shard: hidden -> token id
    def detok(self, token_id: int) -> str: ...            # last shard: token id -> text
    def eos_id(self) -> int: ...


class NumericShardRunner:
    """Deterministic pure-Python reference runner (no model, no deps).

    Models each transformer "layer" as ``+1`` to every element of a small hidden
    vector. A shard covering ``L`` layers therefore adds ``L`` to each element in
    ``forward``. Starting from ``embed(t) = [t, 0, 0, 0]`` and sampling
    ``int(hidden[0])``, threading a token through *all* shards yields
    ``t + total_layers`` — which only holds if every device ran its band. This is
    the property the self-test checks.
    """

    def __init__(self) -> None:
        self._layers = 0
        self._dim = 4

    def load(self, shard_json: str) -> None:
        s = json.loads(shard_json)
        self._layers = int(s["end_layer"]) - int(s["start_layer"])

    def embed(self, token_id: int) -> bytes:
        return json.dumps([float(token_id)] + [0.0] * (self._dim - 1)).encode("utf-8")

    def forward(self, hidden: bytes) -> bytes:
        vec = json.loads(bytes(hidden).decode("utf-8"))
        vec = [x + self._layers for x in vec]
        return json.dumps(vec).encode("utf-8")

    def sample(self, hidden: bytes) -> int:
        vec = json.loads(bytes(hidden).decode("utf-8"))
        return int(round(vec[0]))

    def detok(self, token_id: int) -> str:
        return str(token_id)

    def eos_id(self) -> int:
        return -1


class ShardedPipeline:
    """Drives one node's role in a layer-sharded ring over an ``IMeshNetwork``.

    Construct one per node with the (already computed) ``ring`` order and this
    node's ``runner``. The coordinator additionally calls :meth:`generate`.
    """

    def __init__(
        self,
        node_id: str,
        mesh: IMeshNetwork,
        ring: List[str],
        runner: ShardRunner,
        coordinator: str,
        max_new_tokens: int = 16,
    ) -> None:
        self.node_id = node_id
        self.mesh = mesh
        self.ring = ring
        self.runner = runner
        self.coordinator = coordinator
        self.max_new_tokens = max_new_tokens

        self.rank = ring.index(node_id)
        self.is_first = self.rank == 0
        self.is_last = self.rank == len(ring) - 1

        self._outbox: List[Tuple[Optional[str], bytes]] = []
        self._tokens: List[int] = []      # coordinator: collected token ids
        self._done: set = set()
        self._running = False

        mesh.register_handler(self._on_message)

    # -- ring plumbing ------------------------------------------------------
    def _next(self) -> str:
        return self.ring[(self.rank + 1) % len(self.ring)]

    def _on_message(self, from_node: str, data: bytes) -> None:
        msg = proto.Message.decode(data)
        if msg.type == proto.MsgType.FEED.value:
            self._on_feed(msg)
        elif msg.type == proto.MsgType.ACTIVATION.value:
            self._on_activation(msg)
        elif msg.type == proto.MsgType.TOKEN.value:
            self._tokens.append(int(msg.body["token_id"]))
        elif msg.type == proto.MsgType.DONE.value:
            self._done.add(msg.body["task_id"])

    def _on_feed(self, msg: proto.Message) -> None:
        # First stage: embed the fed-back token and run our layers.
        if not self.is_first:
            return
        task_id = msg.body["task_id"]
        step = int(msg.body["step"])
        token_id = int(msg.body["token"])
        hidden = self.runner.forward(self.runner.embed(token_id))
        self._advance(task_id, step, hidden)

    def _on_activation(self, msg: proto.Message) -> None:
        task_id = msg.body["task_id"]
        step = int(msg.body["step"])
        hidden = self.runner.forward(proto.activation_blob(msg))
        self._advance(task_id, step, hidden)

    def _advance(self, task_id: str, step: int, hidden: bytes) -> None:
        """Either forward the activation onward, or (if last) sample + close ring."""
        if not self.is_last:
            self._outbox.append((self._next(), proto.activation(task_id, step, hidden).encode()))
            return

        token_id = self.runner.sample(hidden)
        self._outbox.append((
            self.coordinator,
            proto.Message(proto.MsgType.TOKEN.value, {"task_id": task_id, "token_id": token_id}).encode(),
        ))
        next_step = step + 1
        if token_id == self.runner.eos_id() or next_step >= self.max_new_tokens:
            self._outbox.append((self.coordinator, proto.done(task_id).encode()))
        else:
            # Close the ring: feed the sampled token back to the first stage.
            self._outbox.append((self.ring[0], proto.feed(task_id, next_step, token_id).encode()))

    async def _flush(self) -> None:
        while self._outbox:
            target, data = self._outbox.pop(0)
            if target is None:
                await self.mesh.broadcast(data)
            else:
                await self.mesh.send_to(target, data)

    async def run_forever(self, poll_s: float = 0.002) -> None:
        self._running = True
        while self._running:
            await self._flush()
            await asyncio.sleep(poll_s)

    def stop(self) -> None:
        self._running = False

    # -- coordinator role ---------------------------------------------------
    async def generate(self, prompt_token_ids: List[int], timeout_s: float = 5.0) -> List[int]:
        """Seed the ring with the prompt's last token and collect generated ids."""
        assert prompt_token_ids, "prompt_token_ids must be non-empty"
        task_id = "shard-task"
        self._tokens = []
        self._done.discard(task_id)

        seed = prompt_token_ids[-1]
        self._outbox.append((self.ring[0], proto.feed(task_id, 0, seed).encode()))

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while task_id not in self._done and loop.time() < deadline:
            await self._flush()
            await asyncio.sleep(0.005)
        await self._flush()
        return list(self._tokens)
