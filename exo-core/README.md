# exo-core

A distilled, **Android-portable** orchestration core extracted from
[exo-explore/exo](https://github.com/exo-explore/exo) for embedding in **Saturn Mask**
(the `gitShlak` app) via **Chaquopy**, using **bitchat-core** as its mesh transport.

Upstream exo cannot run on Android as-is: it requires **Python 3.13**, does inference
through **Apple MLX**, networks through a **Rust `exo_rs`/Zenoh** extension, and uses the
Rust **`rustworkx`** graph library and **FastAPI/hypercorn**. `exo-core` keeps only the
*portable orchestration logic* and re-expresses it in **pure-Python standard library**
(no third-party runtime deps), so it loads cleanly under Chaquopy.

## What it provides

| Module | Responsibility | Distilled from |
|---|---|---|
| `exo_core.topology` | Memory-weighted ring partitioning (`allocate_layers_proportionally`, cycle filtering/selection) | `exo.master.placement_utils`, `exo.master.placement` |
| `exo_core.inference` | Shard metadata, shard assignment (pipeline/tensor), `Engine`/`Builder` ABCs + `EchoEngine` | `exo.shared.types.worker.shards`, `exo.master.placement_utils`, `exo.worker.engines.base` |
| `exo_core.worker` | Runner lifecycle planner + threading-based in-process `Runner` | `exo.worker.plan`, `exo.worker.runner` |
| `exo_core.shared` | Value types (`NodeId`, `Memory`, `ModelCard`, …), pure-Python topology graph | `exo.shared.types.*`, `exo.shared.topology` |
| `exo_core.networking` | Abstract **`IMeshNetwork`** transport + `BitChatNetworkAdapter` + in-memory mesh | *new* (upstream has no Python mesh interface) |
| `exo_core.node` | `ExoNode` orchestrator (coordinator + worker in one) | `exo.main.Node`, `exo.master.Master`, `exo.worker.Worker` |

## Run the self-test

```bash
cd exo-core
python -m exo_core.selftest
```

Expected output ends with `ALL PASSED`. It verifies partitioning, shard assignment, the
threaded runner, and a **2-node pipeline ring** exchanging tokens over the in-memory mesh
(Scenarios 2 and 3 from the integration plan).

## Using a real transport (bitchat-core)

`ExoNode` talks to any `IMeshNetwork`. To run over Bluetooth, construct it with a
`BitChatNetworkAdapter` wrapping a Kotlin bridge object supplied through Chaquopy:

```python
from exo_core.networking import BitChatNetworkAdapter
from exo_core.node import ExoNode
from exo_core.shared.types import Memory

mesh = BitChatNetworkAdapter(bridge=kotlin_exo_mesh_bridge)   # bridge from Kotlin
node = ExoNode("this-device", mesh, Memory.from_gb(4))
```

See [`../INTEGRATION.md`](../INTEGRATION.md) for the full Saturn Mask wiring
(Chaquopy setup, `ExoBridge`, `MeshService`, the Kotlin `ExoMeshBridge`, and the
`Skill`/mode-toggle integration), plus the known feasibility blockers.

## Deliberately out of scope (stubbed / abstracted)

- **Real inference** — `EchoEngine` is a reference; a production backend implements
  `exo_core.inference.Engine`/`Builder` on LiteRT/TFLite/ONNX (MLX removed).
- **Real transport** — the concrete mesh is `bitchat-core` (Kotlin) via the adapter; the
  Zenoh/`exo_rs` layer is removed.
- **Model downloads, HTTP API, election/daemon, disaggregated KV-cache** — removed.
