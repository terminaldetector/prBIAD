# Exo → `exo-core` distillation report

**Source:** [exo-explore/exo](https://github.com/exo-explore/exo) v0.3.70, unpacked from
`exo-main.zip` in this repo (`/workspace/exo-main`, Python tree at `src/exo/`).
**Target:** a pure-Python, Android/Chaquopy-portable orchestration core.
**Result:** `python -m exo_core.selftest` → **ALL PASSED** (partitioning, shard
assignment, threaded runner, 2-node pipeline ring over the mesh).

## Reality check that shaped the distillation

The plan asked to keep `exo/topology`, `exo/inference`, `exo/worker`, `exo/shared`,
`exo/networking`. The real repo does **not** have that layout, and several parts are
fundamentally non-portable to Android:

| Plan assumption | Reality in upstream exo | Consequence |
|---|---|---|
| `exo/topology/` package | Logic lives in `shared/topology.py` + `master/placement*.py`; graph uses **rustworkx** (Rust) | Re-implemented graph in pure Python |
| `exo/inference/` package | Inference is `worker/engines/*` and is **MLX-only** (Apple) | Kept the `Engine`/`Builder` ABCs + algorithms; dropped MLX |
| `exo/networking/` with `IMeshNetwork` | No Python network ABC — networking is Rust `exo_rs`/**Zenoh** | Defined `IMeshNetwork` fresh |
| `exo/shared/` portable | Portable, but imports leak from `api/` (FastAPI) and `worker/runner/diagnostics` | Re-modelled the needed types with dataclasses |
| Python 3.12 (Chaquopy) | `requires-python == 3.13.*` | Re-wrote as stdlib, `requires-python >= 3.9` |
| `multiprocessing` → threading | Runners are spawned subprocesses via `AsyncProcess`+`mp_channel` | Re-implemented as a threading `Runner` |

So this is a **faithful re-expression** of exo's orchestration (algorithms ported, often
verbatim), not a file copy — because a file copy of upstream exo neither imports nor runs
on Android.

## Kept (ported, mostly verbatim where pure-Python)

- **`allocate_layers_proportionally`** — the memory-weighted, largest-remainder layer split
  (ported verbatim from `master/placement_utils.py`).
- **Cycle filtering / selection** — `filter_cycles_by_memory`, `get_smallest_cycles`, and a
  `select_cycle_for_model` distilled from `master/placement.place_instance`.
- **Shard assignment** — pipeline (memory-weighted bands) and tensor (full-layer fan-out),
  from `get_shard_assignments*`.
- **`Engine` / `Builder` ABCs** — from `worker/engines/base.py` (minus desktop-only
  `serve_prefill`).
- **Runner lifecycle** — a state-machine planner distilled from `worker/plan.py`.
- **Value types** — `NodeId`, `Memory` (with its arithmetic), `MemoryUsage`, `ModelCard`,
  `Sharding`, shard metadata, `ShardAssignments`.

## Removed (not portable / out of scope)

| Area | Upstream location | Why removed |
|---|---|---|
| MLX LLM + image engines | `worker/engines/mlx/*`, `worker/engines/image/*` | Apple-only; no Android runtime |
| Zenoh / libp2p networking | `routing/*` + `rust/exo_rs` | Rust extension; replaced by `IMeshNetwork` |
| rustworkx topology graph | `shared/topology.py` | Rust; replaced by pure-Python graph |
| FastAPI + hypercorn HTTP API + Svelte dashboard | `api/*`, `utils/banner.py`, `utils/dashboard_path.py` | Server/GUI; Android uses native UI |
| HuggingFace downloads (aiohttp) | `download/*` | Model provisioning is host-app concern |
| `multiprocessing` runner subprocess | `worker/runner/supervisor.py`, `utils/async_process.py`, `utils/channels.py` | No subprocess model under Chaquopy → threading |
| Election / daemon | `shared/election.py`, `python-daemon` in `main.py` | Single-process node; coordinator chosen by caller |
| Disaggregated KV-cache transfer | `worker/disaggregated/*` | TCP prefill server; desktop-only |
| Pydantic / msgspec / loguru / transformers / psutil | throughout | Replaced by dataclasses + stdlib logging + JSON |

## New (not in upstream)

- **`IMeshNetwork`** (`networking/mesh.py`) — the abstract transport from the plan
  (`broadcast` / `send_to` / `get_nodes` / `register_handler`).
- **`InMemoryMeshNetwork`** — process-local transport for tests.
- **`BitChatNetworkAdapter`** (`networking/bitchat_adapter.py`) — bridges `IMeshNetwork`
  to a Kotlin `ExoMeshBridge` (backed by `bitchat-core`) via Chaquopy; degrades to a
  logging no-op stub when no bridge is supplied.
- **JSON wire protocol** (`networking/protocol.py`) — `ANNOUNCE`/`ASSIGN`/`PROMPT`/`TOKEN`/`DONE`.
- **`EchoEngine`** — dependency-free reference backend for bring-up/tests.
- **Android logging shim** (`log.py`) — forwards to `android.util.Log` (tag `EXO_BRIDGE`)
  under Chaquopy, falls back to stdlib logging on CPython.

## Verification

```
$ python -m exo_core.selftest
[1] partitioning        6 layers @ [0.5,0.25,0.25] -> [3, 2, 1]
[2] shard assignment    A=[0,4) B=[4,6)
[3] threaded runner     'quick brown fox'
[4] distributed ring    'hello world foo bar'
ALL PASSED
```

`python -m compileall exo_core` also succeeds (byte-compiles clean on Python 3.12).

## Remaining work to reach a functional cluster

1. **A real inference backend** implementing `exo_core.inference.Engine`/`Builder` on a
   mobile runtime (LiteRT/TFLite/ONNX). This is the single biggest gap — exo's only engines
   are MLX.
2. **Wire `BitChatNetworkAdapter` to `bitchat-core`** through the Kotlin `ExoMeshBridge`
   (see `INTEGRATION.md`).
3. **Model provisioning** — decide how shards/weights reach each device (host app or a
   re-added downloader).
