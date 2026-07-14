# bitchat-core

A distilled, UI-agnostic **mesh communication core** extracted from
[permissionlesstech/bitchat-android](https://github.com/permissionlesstech/bitchat-android).

`bitchat-core` keeps only the transport layer — Bluetooth LE mesh, optional Wi‑Fi Aware,
GeoHash channel logic, the binary/Noise protocol and the data models — and drops the entire
app shell (Compose UI, onboarding, notifications UI, file/voice/media features, Nostr relay
networking and the Tor/Arti stack). It builds as a standalone Android **library (AAR)** that can
be embedded into another app or shipped as an external module and driven over Intent/AIDL.

> **License:** GPLv3, inherited from upstream BitChat (see `LICENSE.md`). The original assumption
> of Apache‑2.0 was incorrect; the upstream project is GPLv3, so this module is too.

## Building

```bash
cd bitchat-core
./gradlew :bitchat-core:assemble        # builds debug + release AARs
```

Requires JDK 17+ and the Android SDK (compileSdk 35). Output AARs land in
`bitchat-core/build/outputs/aar/`.

## Public API

The single entry point is `com.bitchat.core.api.BitchatCore`:

```kotlin
val core = BitchatCore(context)
core.listener = object : BitchatCore.Listener {
    override fun onMessage(message: BitchatMessage) { /* render */ }
    override fun onPeerListUpdated(peerIDs: List<String>) { /* roster */ }
}
core.start(nickname = "alice")   // requires Bluetooth + location permissions
core.sendBroadcast("hello mesh")
core.sendPrivate("hi", recipientPeerID)   // end-to-end encrypted via Noise
core.stop()
```

If you need the full surface, `core.meshService()` returns the underlying
`BluetoothMeshService` (implements the transport-agnostic `mesh.MeshService` contract).

## Package map (what each area does)

| Package | Responsibility |
|---|---|
| `mesh` | Bluetooth LE mesh: discovery, GATT client/server, connection tracking, fragmentation, store‑and‑forward, packet routing/relay, `BluetoothMeshService` (BLE) and `UnifiedMeshService` (BLE + Wi‑Fi Aware bridge). |
| `wifiaware` (`wifi-aware/`) | Optional Wi‑Fi Aware transport that plugs into the same mesh core. |
| `protocol` | Binary packet format (`BitchatPacket`, `MessageType`, TLV encode/decode). |
| `noise` | Noise Protocol (XX) session handling + bundled `southernstorm` primitives for payload encryption. |
| `crypto` | `EncryptionService`: Noise session management + Ed25519 signing (BouncyCastle). |
| `identity` | Persistent Noise/identity key storage. |
| `model` | Data models: `BitchatMessage`, packets, identity announcements, noise payloads. |
| `geohash` | Coordinate → geohash channel conversion, filtering, and framework‑`LocationManager` location provider (Google Play Services provider removed). |
| `sync` | Gossip sync (GCS/bloom-style set reconciliation of seen packets). |
| `favorites` | Favorite‑peer persistence. |
| `services` | Transport helpers: `AppStateStore`, `VerificationService`, `SeenMessageStore`, `MessageRetentionService`, `meshgraph` route planning/graph. |
| `service` | `TransportBridgeService` (multi‑transport bridge) and `MeshServiceHolder` (process-wide instance holder). |
| `util` / `utils` | Hex/byte helpers, app constants, notification interval throttling. |
| `nostr` | Stubbed: only `Bech32` (npub encode/decode) is retained for favorite parsing. |

## What was removed vs. kept

See `DISTILLATION_REPORT.md` for the full list of removed packages, edited files and retained
dependencies.
