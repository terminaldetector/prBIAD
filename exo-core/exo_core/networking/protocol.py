"""Tiny JSON wire protocol for exo-core mesh messages.

Kept deliberately transport-agnostic and dependency-free (stdlib ``json``) so
the same frames travel over the in-memory bus or the Bluetooth mesh.
"""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List


class MsgType(str, Enum):
    ANNOUNCE = "ANNOUNCE"   # node -> all: "I exist" (discovery)
    ASSIGN = "ASSIGN"       # coordinator -> node: your shard + the ring order
    PROMPT = "PROMPT"       # stage -> next stage: activations (prompt text for echo)
    TOKEN = "TOKEN"         # last stage -> coordinator: an output token
    DONE = "DONE"           # last stage -> coordinator: generation finished
    # --- true layer-sharded pipeline (see sharded.py / SHARDING.md) ---
    ACTIVATION = "ACTIVATION"  # stage i -> stage i+1: hidden-state tensor blob
    FEED = "FEED"              # last stage -> first stage: sampled token id (ring)


@dataclass
class Message:
    type: str
    body: Dict[str, Any]

    def encode(self) -> bytes:
        return json.dumps({"type": self.type, "body": self.body}).encode("utf-8")

    @staticmethod
    def decode(data: bytes) -> "Message":
        obj = json.loads(bytes(data).decode("utf-8"))
        return Message(type=obj["type"], body=obj.get("body", {}))


def announce(node_id: str, memory_bytes: int) -> Message:
    return Message(MsgType.ANNOUNCE.value, {"node_id": node_id, "memory": memory_bytes})


def assign(
    ring: List[str],
    model_id: str,
    shard: Dict[str, Any],
    model_path: str = "",
) -> Message:
    return Message(
        MsgType.ASSIGN.value,
        {"ring": ring, "model_id": model_id, "model_path": model_path, "shard": shard},
    )


def prompt(task_id: str, coordinator: str, text: str) -> Message:
    return Message(MsgType.PROMPT.value, {"task_id": task_id, "coordinator": coordinator, "text": text})


def token(task_id: str, text: str) -> Message:
    return Message(MsgType.TOKEN.value, {"task_id": task_id, "text": text})


def done(task_id: str) -> Message:
    return Message(MsgType.DONE.value, {"task_id": task_id})


def activation(task_id: str, step: int, blob: bytes) -> Message:
    """Carry a hidden-state tensor between pipeline stages (base64 for JSON)."""
    return Message(
        MsgType.ACTIVATION.value,
        {"task_id": task_id, "step": step, "blob": base64.b64encode(bytes(blob)).decode("ascii")},
    )


def activation_blob(msg: "Message") -> bytes:
    return base64.b64decode(msg.body["blob"])


def feed(task_id: str, step: int, token_id: int) -> Message:
    """Send the sampled token id back to the first stage to close the ring."""
    return Message(MsgType.FEED.value, {"task_id": task_id, "step": step, "token": int(token_id)})
