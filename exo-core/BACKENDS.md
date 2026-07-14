# exo-core inference backends (LiteRT / TFLite / ONNX)

exo-core is pure Python and does **not** embed a native model runtime. A backend
implements the `Engine`/`Builder` ABCs (`exo_core/inference/engine.py`). Two ship
today:

| Backend name | Builder | Runs where | Use |
|---|---|---|---|
| `echo` | `EchoBuilder` | in Python | bring-up / tests (no model) |
| `bridge` (aliases: `litert`, `tflite`, `onnx`) | `BridgeBuilder` | **host runtime (Kotlin) via Chaquopy** | real Android inference |

## Why a bridge (not a Python runtime)

Under Chaquopy there is no reliable pip-installable LLM runtime, and exo's own
engines are Apple-MLX only. So the model runs in **Kotlin** (where LiteRT/TFLite/
ONNX have first-class Android support) and exo-core drives it through a thin
adapter — exactly the pattern used for the mesh transport (`BitChatNetworkAdapter`).

```
exo_core.node.ExoNode
      │ builds Engine on the running node
      ▼
BridgeBuilder / BridgeEngine  (Python, exo_core.inference.backends.bridge)
      │ submit(prompt) / poll() -> JSON chunks         ▲ onMessage-style pull
      ▼                                                │
InferenceBackend  (Kotlin: LiteRtLlmBackend | TfLiteBackend | OnnxRuntimeBackend)
      ▼
LiteRT LLM API / TFLite Interpreter / ONNX Runtime
```

The Kotlin contract (`InferenceBackend`) and reference implementations are in
[`integration/kotlin/`](integration/kotlin/): `InferenceBackend.kt`,
`LiteRtLlmBackend.kt`, `TfLiteBackend.kt`, `OnnxRuntimeBackend.kt`.

## Runtime comparison

| Runtime | Gradle dependency | Model format | Generation loop | Recommendation |
|---|---|---|---|---|
| **LiteRT LLM** (Google AI Edge / MediaPipe) | `com.google.mediapipe:tasks-genai` | `*.task` bundle | **built-in** (tokenizer + streaming) | ✅ default — least code |
| **TFLite** (raw `Interpreter`) | `org.tensorflow:tensorflow-lite` (already an app dep) | `*.tflite` decoder graph | you own it (tokenizer + KV cache) | when you have a TFLite graph |
| **ONNX Runtime Mobile** | `com.microsoft.onnxruntime:onnxruntime-android` | `*.onnx` | you own it | enables per-shard sub-models |

## Selecting a backend

**Python** (which builder to use):

```python
from exo_core.inference.backends import get_builder

builder = get_builder("echo")                                  # tests
builder = get_builder("litert", runner=kotlin_backend,         # Android
                       model_path="/data/user/0/<pkg>/files/model.task")
node = ExoNode(node_id, mesh, memory, builder=builder)
```

**Kotlin** (which runtime to instantiate, then hand to Python via Chaquopy):

```kotlin
val backend: InferenceBackend = LiteRtLlmBackend(context)      // or TfLite/Onnx
val py = Python.getInstance()
val builder = py.getModule("exo_core.inference.backends")
    .callAttr("get_builder", "litert", null, backend)          // runner=backend
// pass `builder` into ExoNode(...) from ExoBridge (see ../INTEGRATION.md)
```

`ModelCard.model_path` (or the `model_path=` option) tells the backend where the
on-device weights live — resolve it from `context.getFilesDir()` on the app side.

## ⚠️ Sharding caveat (important)

exo-core computes a memory-weighted **layer partition** (each device gets a band
`[start_layer, end_layer)`). But LiteRT/TFLite/ONNX run a **whole model** by
default — they do not expose "run layers N..M and pass hidden state onward". So:

- **Single device** — trivial: `world_size = 1`, one full model. Works today with
  any backend.
- **Full-model-per-node (routing)** — every device loads the whole (small) model;
  exo-core routes each request to a node. Change placement to `world_size = 1`
  rings; the partition math is bypassed. Works today.
- **True layer-pipeline across devices** — needs **per-shard sub-models exported
  offline** (e.g. split the ONNX/TFLite graph at layer boundaries) plus a runtime
  path that accepts an input hidden-state tensor and emits an output hidden-state
  tensor. The `shardJson` passed to `loadModel` (with `start_layer`/`end_layer`/
  `is_first_layer`/`is_last_layer`) carries exactly the metadata such a backend
  needs; ONNX Runtime is the most practical target. This is future work — the
  reference `LiteRtLlmBackend` runs the whole model and only the last stage speaks.

## Verification

The bridge path is covered by the self-test using a pure-Python `FakeHostRunner`
that implements the same JSON `poll()` contract as the Kotlin backends:

```
$ python -m exo_core.selftest
...
[5] backend registry     ['bridge', 'echo', 'litert', 'onnx', 'tflite']
[6] bridge backend (LiteRT/TFLite/ONNX host runtime): 'alpha beta gamma'
[7] distributed ring over bridge backend: 'one two three'
ALL PASSED
```
