# Splitting a model across devices (true pipeline parallelism)

exo-core's partitioner already decides *which layers go on which device*
(memory-weighted, `topology/partition.py`). This document explains how to make the
model **actually run split**, and what exo-core provides to drive it.

## The idea in one picture

A decoder-only LLM is:

```
tokens ─► embed ─► block[0] ─► … ─► block[N-1] ─► final_norm ─► lm_head ─► logits ─► sample
          └────────── shard 0 ───────┘ └── shard 1 ──┘ └──────── shard 2 ────────┘
```

Split it into **per-shard sub-models**. The interface between shards is the
**hidden-state tensor** `h ∈ ℝ^{d_model}` (one vector per token in decode). During
decode this forms a **ring**, because embedding is at the front and sampling at the
back:

```
        hidden states (few KB) ──►         ──►
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │ shard 0  │──►│ shard 1  │──►│ shard 2  │
   │ embed +  │   │ blocks   │   │ blocks + │
   │ blocks   │   │          │   │ lm_head  │
   └────▲─────┘   └──────────┘   └────┬─────┘
        │       sampled token id      │
        └──────────◄──────────────────┘   (tiny: one int)
```

**Only activations cross the wire; the KV cache never does** — each device keeps the
KV for *its own* layers and reuses it across decode steps. Per generated token you
send `d_model` floats forward per hop (e.g. 4096 × fp16 ≈ 8 KB) and one int back.

## What exo-core provides (implemented, tested)

`exo_core.inference.sharded`:

- **`ShardRunner`** — the host contract: `embed` (first shard), `forward` (every
  shard), `sample`/`detok` (last shard), `load(shard_json)`.
- **`ShardedPipeline`** — drives one node's role in the ring over any
  `IMeshNetwork`: receives `FEED`(token)/`ACTIVATION`(hidden), runs its band,
  forwards the activation or (if last) samples and feeds the token back to shard 0.
- **`NumericShardRunner`** — a dependency-free reference where each "layer" is `+1`
  to the hidden vector, so a token threaded through all shards advances by
  `total_layers`. The self-test uses it to prove **both devices' bands ran**:

  ```
  [8] TRUE layer-sharded split (activation-passing ring)
    layer split A(0, 4)+B(4, 6) -> tokens [7, 13, 19] (each +6 = both shards ran)
  ```

New wire messages (`networking/protocol.py`): `ACTIVATION` (base64 hidden-state
blob) and `FEED` (sampled token id, closes the ring).

The Kotlin host contract is `integration/kotlin/ShardBackend.kt`.

## What you must supply (offline export + host runtime)

exo-core relays bytes and orchestrates the ring; it does **not** do tensor math.
To run a real model you need:

### 1. Per-shard sub-model export (offline, one-time)
The practical target is **ONNX** (ORT supports arbitrary graphs, dynamic shapes,
external weights, and hidden-state I/O). Sketch with HuggingFace + PyTorch:

```python
import torch
from transformers import AutoModelForCausalLM

full = AutoModelForCausalLM.from_pretrained(model_id)
blocks = full.model.layers  # decoder blocks

class FirstShard(torch.nn.Module):      # embed + blocks[0:k]
    def forward(self, input_ids, past_kv): ...   # -> hidden, new_kv
class MiddleShard(torch.nn.Module):     # blocks[a:b]
    def forward(self, hidden, past_kv):  ...     # -> hidden, new_kv
class LastShard(torch.nn.Module):       # blocks[b:N] + norm + lm_head
    def forward(self, hidden, past_kv):  ...     # -> logits, new_kv

torch.onnx.export(FirstShard(...), ..., "shard0.onnx", dynamic_axes=...)
# ... one .onnx per shard; ship the shard that matches this device's band.
```

Key points:
- Each sub-model takes/produces `past_key_values` for **only its own layers**.
- Mark sequence + batch as dynamic axes (prefill runs many positions, decode one).
- Quantize (int4/int8) per shard to fit device memory (exo-core's partitioner sizes
  bands by available RAM, so heavier devices get more layers).

### 2. Host runtime implementing `ShardBackend`
Load the device's `shard_i.onnx` in ONNX Runtime Mobile; keep the ORT session +
this shard's KV tensors in the object; implement `embed`/`forward`/`sample`. See
`integration/kotlin/ShardBackend.kt` and `OnnxRuntimeBackend.kt`.

### 3. Tokenizer on the first/last shard
`embed` needs token ids (first shard), `detok` maps ids to text (last shard). Ship a
tokenizer (e.g. SentencePiece/`tokenizers`) on those devices.

## Prefill vs decode
- **Prefill**: shard 0 embeds the whole prompt and runs its blocks over all
  positions, populating its KV; the hidden states for all positions flow forward;
  the last shard produces logits for the final position and samples token 0. (For
  the bring-up demo, `ShardedPipeline.generate` seeds with the prompt's last token;
  extend it to stream the full prompt tensor for real prefill.)
- **Decode**: the ring loop above, one token per lap.

## Transport reality on Android
Hidden states are a few KB/token/hop. Over **BLE** (bitchat-core) that is slow but
functional for short generations; **Wi-Fi Aware** (also in bitchat-core) is the
better carrier for real throughput. Because only activations move (never weights or
KV), bandwidth scales with `d_model × hops`, not model size.

## Fallback modes (when you don't want to export sub-models)
- **Single device**: `world_size = 1`, whole model on one node (any backend).
- **Full-model-per-node routing**: every device loads the whole (small) model;
  exo-core routes each *request* to a device instead of splitting layers. Use
  `world_size = 1` placement and the whole-model `BridgeBuilder`.

See `BACKENDS.md` for the whole-model backends and `INTEGRATION.md` for app wiring.
