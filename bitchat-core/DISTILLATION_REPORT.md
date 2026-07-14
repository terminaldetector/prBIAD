# BitChat → `bitchat-core` distillation report

**Source:** [permissionlesstech/bitchat-android](https://github.com/permissionlesstech/bitchat-android) (cloned `main`)
**License:** GPLv3 (upstream). The task brief assumed Apache‑2.0, but BitChat Android is GPLv3, so
`bitchat-core` inherits GPLv3. `LICENSE.md` is copied verbatim.
**Result:** standalone Android library that builds cleanly with
`./gradlew :bitchat-core:assemble`.

## Outcome

| Metric | Value |
|---|---|
| Kotlin source files (upstream `com/bitchat/android`) | 199 |
| Kotlin source files (bitchat-core) | 86 |
| Build | ✅ `BUILD SUCCESSFUL`, 0 errors |
| Warnings | 37 — all pre-existing Android SDK API deprecations in retained upstream code (`EncryptedSharedPreferences`, `MasterKey`, `LocationManager.requestSingleUpdate`, one upstream "condition always false"). No warnings originate from the distillation scaffolding. |
| Release AAR | ~1.1 MB (compiled transport code only; **no** bundled native libraries) |
| Native libraries | 0 (upstream shipped 22 MB of Arti/Tor `.so` files — fully removed) |
| Google Play Services | 0 dependencies |

The AAR is marginally above the 1 MB soft target. The dominant cost is the essential `mesh`
package (~1.4 MB uncompressed). The optional `wifiaware` package (~0.3 MB) can be dropped to fall
comfortably under 1 MB if a BLE-only core is acceptable.

## Removed (not in the core)

**Whole packages deleted**
- `ui/` — all Jetpack Compose UI, activities, sheets, view models, themes (58 files) *(except two headless helpers, see below)*
- `onboarding/` — permission/onboarding flows (14 files)
- `features/` — file / voice / media features *(except `features/file/FileUtils.kt`, reused by the receive path)*
- `core/ui/` — shared Compose UI components
- `net/` — OkHttp provider + **Arti/Tor** manager and preferences (Tor transport)
- `info/guardianproject/arti/`, `org/torproject/arti/` — Tor/Arti JNI bridge
- Most of `nostr/` — relay client, subscription/PoW/event/protocol, geohash handlers *(only `Bech32.kt` kept)*

**Native / resources**
- `jniLibs/` (arm64‑v8a, x86_64, x86, armeabi‑v7a) `libarti_android.so` — **22 MB removed**
- `res/` (all drawables, mipmaps, 30+ `values-*` translations), assets

**Individual files removed**
- `BitchatApplication.kt`, `MainActivity.kt`, `MainViewModel.kt` (app shell)
- `model/FileSharingManager.kt` (file *send* orchestration)
- `services/MessageRouter.kt`, `services/ConversationAliasResolver.kt` (Nostr/UI routing glue)
- `service/MeshForegroundService.kt`, `service/BootCompletedReceiver.kt`, `service/AppShutdownCoordinator.kt`, `service/MeshServicePreferences.kt`
- `geohash/FusedLocationProvider.kt` (Google Play Services location)
- `ui/debug/DebugSettingsSheet.kt`, `ui/debug/MeshGraph.kt` (Compose debug UI)

## Kept (the transport core)

- `mesh/` — Bluetooth LE mesh (discovery, GATT client/server, connection tracking, fragmentation,
  store-and-forward, packet processing/relay), `BluetoothMeshService`, `UnifiedMeshService`
- `wifi-aware/` (`com.bitchat.android.wifiaware`) — optional Wi‑Fi Aware transport
- `protocol/` — binary packet format & TLV
- `noise/` — Noise Protocol sessions + bundled `southernstorm` crypto primitives
- `crypto/`, `identity/` — Noise encryption service + secure identity key storage
- `model/` — `BitchatMessage`, packets, identity announcement, noise payloads
- `geohash/` — geohash channel conversion/filtering + framework `LocationManager` provider
- `sync/` — gossip sync (GCS set reconciliation)
- `favorites/` — favorite-peer persistence
- `services/` — `AppStateStore`, `VerificationService`, `SeenMessageStore`,
  `MessageRetentionService`, `NicknameProvider`, `meshgraph/*`
- `service/` — `TransportBridgeService`, `MeshServiceHolder`
- `util/`, `utils/` — hex/byte helpers, constants, notification-interval throttle
- `nostr/Bech32.kt` — npub encode/decode (used by favorites)
- **Retained headless helpers** kept from `ui/` because they are plain (no Compose/`R`):
  `ui/DataManager.kt`, `ui/NotificationTextUtils.kt`, `ui/debug/DebugSettingsManager.kt`,
  `ui/debug/DebugPreferenceManager.kt`

## Edits made to retained files

To sever the remaining coupling to removed packages (all edits are small and local):

| File | Change |
|---|---|
| `ui/NotificationManager.kt` | Replaced the full Compose/`MainActivity`-coupled implementation with a **headless stub** (same constructor + `setAppBackgroundState`/`showPrivateMessageNotification`, no-op). |
| `mesh/BluetoothMeshService.kt` | Removed the geohash/`MessageRouter` read-receipt branch; receipts go over the mesh only. |
| `mesh/UnifiedMeshService.kt` | Removed `NostrIdentityBridge` lookup in `sendFavoriteNotification` (empty npub). |
| `wifi-aware/WifiAwareMeshService.kt` | Removed the `MessageRouter.onSessionEstablished` callback. |
| `geohash/GeocoderFactory.kt`, `geohash/LocationChannelManager.kt` | Always use the framework `SystemLocationProvider`; removed Google Play Services detection and `FusedLocationProvider`. |

## Dependencies

**Kept (Android SDK + AndroidX + minimal 3rd-party):**
- `androidx.core:core-ktx`, `androidx.lifecycle:lifecycle-process`, `androidx.lifecycle:lifecycle-runtime-ktx`
- `androidx.security:security-crypto` (encrypted identity storage)
- `com.google.code.gson:gson` (model + preference JSON)
- `org.jetbrains.kotlinx:kotlinx-coroutines-android`
- `org.bouncycastle:bcprov-jdk15on` (Ed25519 signatures)
- `no.nordicsemi.android:ble` (Bluetooth LE)

**Removed:** Jetpack Compose (BOM + UI + material3 + icons), Navigation, Accompanist, CameraX,
ML Kit barcode, ZXing, OkHttp, Tor (`tor-android-binary` / Arti AAR + native libs),
Google Play Services location, ExifInterface, Compose tooling/testing.

## Public API

`com.bitchat.core.api.BitchatCore` — a thin facade over `BluetoothMeshService`:

```kotlin
val core = BitchatCore(context)
core.listener = object : BitchatCore.Listener {
    override fun onMessage(message: BitchatMessage) { /* ... */ }
    override fun onPeerListUpdated(peerIDs: List<String>) { /* ... */ }
}
core.start(nickname = "alice")
core.sendBroadcast("hello mesh")
core.sendPrivate("hi", recipientPeerID)   // Noise-encrypted
core.stop()
```

`core.meshService()` exposes the full `BluetoothMeshService` for advanced integrations.

## Known limitations

- **Nostr is stubbed** (only `Bech32` remains). Re-enabling relays would require restoring the
  `nostr` + `net` packages and an OkHttp (optionally Tor) dependency.
- **Notifications are no-ops** — the host app should present its own UI from `BitchatCore.Listener`.
- Geohash live-location uses the framework `LocationManager` (coarser than the removed fused
  provider) — the geohash channel math is unchanged.
