# Saturn Mask ⇄ Exo ⇄ BitChat — integration guide

This document maps the architectural plan (merging **Exo** distributed inference and
**BitChat** P2P mesh into **Saturn Mask** / `gitShlak`) onto concrete, buildable steps and
records the real blockers discovered while distilling both projects.

## Current state of the pieces

| Piece | Location | Status |
|---|---|---|
| **exo-core** (Python) | `exo-core/` | ✅ Distilled + self-tested (`python -m exo_core.selftest`). Pure stdlib. |
| **bitchat-core** (Kotlin AAR) | `bitchat-core/` (PR #3) | ✅ Distilled + builds (`./gradlew :bitchat-core:assemble`). BLE mesh + Noise; Nostr stubbed; GeoHash functional. |
| **Saturn Mask** app | `app/` (`com.google.ai.edge.gallery`) | ⚠️ Early scaffold: `Skill`/`SkillManager` + `ModeState` toggles, **no** LLM runtime, **no** Chaquopy, **no** Bluetooth, **no** Service. Classes named in the plan (`AgentToolsImpl`, `MeshToolSet`, `AgentModeTriggers`, `SettingsActivity`, `Application`) do **not** exist yet. |

## Target architecture

```
┌─────────────────────────── Saturn Mask APK ───────────────────────────┐
│                                                                        │
│  UI (ChatFragment + mode toggles)                                      │
│      │  adds a "Mesh" toggle → ModeState.meshEnabled                   │
│      ▼                                                                  │
│  SkillManager ── MeshSkill (implements existing `Skill`)               │
│      │           • sendMeshMessage / broadcastMesh                     │
│      │           • inferOnCluster / getClusterNodes                    │
│      ▼                                                                  │
│  ┌───────────────┐        ┌───────────────────────────────┐           │
│  │  MeshService  │◄──────►│  ExoBridge (Chaquopy)          │           │
│  │ (Foreground)  │        │  Python.getInstance()          │           │
│  │  wraps        │        │   .getModule("exo_core.node")  │           │
│  │  BitchatCore  │        │  → ExoNode(mesh=BitChatAdapter)│           │
│  └──────┬────────┘        └───────────────┬───────────────┘           │
│         │                                 │                            │
│         │  ExoMeshBridge (Kotlin)  ◄──────┘ (BitChatNetworkAdapter     │
│         │  broadcast/sendTo/getNodes         calls back via Chaquopy)  │
│         ▼                                                              │
│  bitchat-core AAR  ──►  Bluetooth LE mesh (Noise-encrypted)           │
└────────────────────────────────────────────────────────────────────────┘
```

The **Python↔Kotlin boundary** is the plan's recommended shape: the transport is
implemented in Kotlin (`bitchat-core`), and exo's Python calls it through a thin Kotlin
`ExoMeshBridge` that `BitChatNetworkAdapter` (already in `exo-core`) drives via Chaquopy.

## Blockers & decisions (read before estimating)

1. **Python version.** Upstream exo needs **3.13**; Chaquopy supports up to **3.12**.
   `exo-core` is written to `requires-python >= 3.9` (stdlib only) specifically to sidestep
   this. Keep any future additions 3.9-compatible.
2. **No Android inference engine exists in exo.** Exo's only engines are **MLX** (Apple).
   Distributed inference on Android needs a new backend implementing
   `exo_core.inference.Engine`/`Builder` on **LiteRT/TFLite** (Saturn Mask already depends on
   `tensorflow-lite`) or ONNX Runtime. Until then `EchoEngine` proves the plumbing only.
3. **Build-system mismatch.** `app/` is AGP **8.2.2** / Kotlin **1.9.22** / compileSdk **34**;
   `bitchat-core` is AGP **8.10** / Kotlin **2.2** / compileSdk **35**. To include
   `bitchat-core` as a Gradle module you must bump the app toolchain (recommended:
   AGP 8.10+, Kotlin 2.x, compileSdk 35) or consume `bitchat-core` as a prebuilt AAR.
4. **Chaquopy plugin** is not yet applied to `app/`. Adding it changes the app build and
   requires a Python 3.12 on the build machine.
5. **Nostr/GeoHash stubs.** In `bitchat-core`, Nostr is already reduced to `Bech32`
   (relay networking removed); GeoHash is functional. The plan's "stubs for Nostr and
   GeoHash" is therefore already satisfied for Nostr; a `NostrStub`/`GeoHashStub` facade can
   be added if explicit no-op APIs are wanted.

## Stage-by-stage plan → concrete steps

### Stage 1 — Exo distilled (DONE)
`exo-core/` — see `exo-core/DISTILLATION_REPORT.md`. Verified via self-test.

### Stage 2 — bitchat-core (DONE)
`bitchat-core/` — see `bitchat-core/DISTILLATION_REPORT.md`. Builds to a ~1.1 MB AAR, no
native libs, no Google Play Services.

### Stage 3 — Nostr/GeoHash stubs (PARTIAL)
Nostr already stubbed in `bitchat-core`. Optional: add explicit `NostrStub`/`GeoHashStub`
classes that log and return success/empty, per the plan's "log calls, return empty/OK".

### Stage 4 — Exo ↔ BitChat adapter (Python side DONE, Kotlin side TODO)
- Python: `exo_core.networking.BitChatNetworkAdapter` implements `IMeshNetwork` and calls a
  Kotlin `ExoMeshBridge`. **Done.**
- Kotlin: implement `ExoMeshBridge` on top of `BitchatCore`:

```kotlin
// app/src/main/kotlin/.../mesh/ExoMeshBridge.kt   (sketch)
import com.bitchat.core.api.BitchatCore
import com.bitchat.android.model.BitchatMessage
import com.chaquo.python.PyObject

class ExoMeshBridge(private val core: BitchatCore) {
    private var handler: PyObject? = null   // the Python BitChatNetworkAdapter

    init {
        core.listener = object : BitchatCore.Listener {
            override fun onMessage(message: BitchatMessage) {
                // content carries the exo JSON frame; sender peerID is the exo node id
                handler?.callAttr("onMessage", message.senderPeerID ?: "", message.content.toByteArray())
            }
        }
    }

    fun setHandler(pyAdapter: PyObject) { handler = pyAdapter }
    fun broadcast(message: ByteArray) { core.sendBroadcast(String(message)) }
    fun sendTo(nodeId: String, message: ByteArray) { core.sendPrivate(String(message), nodeId) }
    fun getNodes(): Array<String> = core.getPeerNicknames().keys.toTypedArray()
}
```

> Note: exo frames are JSON (`exo_core.networking.protocol`). Sending them as message
> `content` works for bring-up; for binary efficiency later, add a raw-bytes path to
> `BitchatCore` and pack exo node-ids into the peer mapping.

### Stage 1.3 / 4 — ExoBridge (Kotlin → Python)

```kotlin
// app/src/main/kotlin/.../mesh/ExoBridge.kt   (sketch)
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.*

class ExoBridge(private val context: android.content.Context, private val meshBridge: ExoMeshBridge) {
    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private lateinit var node: com.chaquo.python.PyObject

    fun start(nodeId: String, memoryGb: Double) {
        if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        val py = Python.getInstance()
        val adapter = py.getModule("exo_core.networking")
            .callAttr("BitChatNetworkAdapter", meshBridge)
        val mem = py.getModule("exo_core.shared.types")
            .get("Memory")!!.callAttr("from_gb", memoryGb)
        node = py.getModule("exo_core.node").callAttr("ExoNode", nodeId, adapter, mem)
    }

    suspend fun inferOnCluster(prompt: String): String = withContext(Dispatchers.Default) {
        val card = /* build ModelCard via exo_core.shared.types.ModelCard */ TODO()
        val asyncio = Python.getInstance().getModule("asyncio")
        asyncio.callAttr("run", node.callAttr("generate", card, prompt)).toString()
    }

    fun stop() { scope.cancel() /* + node.callAttr("stop") */ }
}
```

### Stage 2.3 — MeshService (Foreground Service)
Create `app/src/main/kotlin/.../mesh/MeshService.kt` as a foreground service that owns a
`BitchatCore`, an `ExoMeshBridge`, and an `ExoBridge`; starts/stops them; exposes a binder
or a singleton holder for the `MeshSkill`. Declare it in `AndroidManifest.xml` with
`foregroundServiceType="connectedDevice|dataSync"` and the Bluetooth permissions from
`bitchat-core`'s manifest.

### Stage 5 — Saturn Mask integration
- **Tool:** add `MeshSkill : Skill` (the app's existing interface, `domain/skills/Skill.kt`)
  exposing `broadcast_mesh`, `send_mesh_message`, `infer_on_cluster`, `get_cluster_nodes`;
  register it in `SkillManager` when mesh mode is on.
- **UI toggle:** add `meshEnabled` to `ChatViewModel.ModeState` and a switch in
  `fragment_chat.xml` / `ChatFragment.setupModeToggles()`; toggling it starts/stops
  `MeshService`.
- **Settings:** add a "Mesh Bridge" screen (auto-start toggle + Exo/BitChat versions from
  `exo_core.__version__` / `bitchat-core`).

### Stage 6 — Multi-device testing
Requires 2+ physical Android devices with Bluetooth (BLE mesh cannot be exercised on a
single emulator). Validate Scenarios 2 (coordinator + satellites) and 3 (masterless ring)
from the plan; `exo-core`'s self-test already validates the ring logic in-process.

## Logging tags (per plan §7)
- `EXO_BRIDGE` — wired in `exo_core/log.py` (Python → `android.util.Log`).
- `BITCHAT_BRIDGE` / `MESH_INTEGRATION` — use these tags in the Kotlin `ExoMeshBridge` /
  `MeshService` / `ExoBridge` classes.
