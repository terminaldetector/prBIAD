# AGENTS.md

## Cursor Cloud specific instructions

### What this repo is
A single **Android application** (Kotlin, Gradle/Kotlin-DSL) — package `com.google.ai.edge.gallery`,
module `:app`. It is a client-only mobile app: there are **no backend services, databases, or ports**
to start. "Running" the product means building the APK and installing it on an Android device/emulator.
The three root-level `*.zip` archives and the `*.apk` are unrelated reference material and are **not**
part of the Gradle build (`settings.gradle.kts` only includes `:app`).

### Toolchain (installed in the VM image)
- **JDK 17** at `/usr/lib/jvm/java-17-openjdk-amd64` (AGP 8.2.2 / Kotlin 1.9.22 do not support JDK 21,
  which is also present — always build with JDK 17).
- **Android SDK** at `~/android-sdk` (`platform-tools`, `platforms;android-34`, `build-tools;34.0.0`).
- **Gradle 8.5** available system-wide as `gradle`; a committed Gradle wrapper (`./gradlew`) also exists.
- `JAVA_HOME`, `ANDROID_HOME`, `ANDROID_SDK_ROOT`, and `PATH` are exported for interactive shells in
  `~/.bashrc`. Non-login/non-interactive shells may not inherit these — prefer `./gradlew` (it reads
  `local.properties`) and set `JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64` explicitly if a task can't
  find the JDK.

### local.properties
Gradle needs `local.properties` with `sdk.dir=<ANDROID_HOME>` to locate the SDK. It is machine-specific
and git-ignored; the update script regenerates it on startup.

### Common commands (run from repo root)
- Build debug APK: `./gradlew assembleDebug` → `app/build/outputs/apk/debug/app-debug.apk`
- Lint: `./gradlew lintDebug` (HTML report under `app/build/reports/`)
- Unit tests: `./gradlew testDebugUnitTest` (note: the project currently ships **no** unit tests, so this
  reports `NO-SOURCE` and passes)
- Install to a running device/emulator: `./gradlew installDebug`

### Running the app (important caveat)
This VM has **no `/dev/kvm`**, so a hardware-accelerated Android emulator cannot run. A software-only
(TCG) emulator is impractically slow/unreliable here. Verify changes via `assembleDebug` + `lintDebug`
and by inspecting the APK (`$ANDROID_HOME/build-tools/34.0.0/aapt dump badging <apk>`). To exercise the
UI end-to-end, install the debug APK on a real device or a KVM-capable machine.

### Pre-existing source bugs (fixed on the setup branch)
CI has never produced a successful build. Two trivial, unambiguous source bugs blocked compilation and
were fixed so the project builds:
- `app/src/main/res/layout/fragment_chat.xml`: `android:gravity="space_around"` is not a valid gravity
  value (it's a flexbox/Compose concept) → changed to `center`.
- `app/src/main/kotlin/.../domain/skills/WebScraperSkillImpl.kt`: `elements.isEmpty` → `elements.isEmpty()`
  (Jsoup `Elements.isEmpty()` is a method, not a property).
