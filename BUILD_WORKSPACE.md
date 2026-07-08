# Build Workspace Notes

This file used to be `.github/workflows/maifn.yml` (a typo'd filename holding a
shell-script/instructions, not an actual GitHub Actions workflow - GitHub
would have failed to parse it as YAML, or silently ignored it). Moved here so
`.github/workflows/` only contains real workflow files.

## Setting up CI locally the way `main.yml` expects

```bash
git clone https://github.com/hren4073-cpu/gitShlak.git
cd gitShlak
git checkout feature/unified-chat-with-rag
```

The workflow in `.github/workflows/main.yml` provisions Gradle itself (via
`gradle/actions/setup-gradle`), so it does **not** require a committed
`gradlew`/`gradle-wrapper.jar` to run in CI.

## One remaining manual step for local development

This repo does not yet have a committed Gradle wrapper jar (`gradle/wrapper/gradle-wrapper.jar`).
`gradle/wrapper/gradle-wrapper.properties` is already in place (pinned to Gradle 8.5,
compatible with AGP 8.2.2 / Kotlin 1.9.22). To generate the actual wrapper scripts + jar:

- **Easiest:** open the project root in Android Studio. It will detect the
  missing wrapper and offer to generate it automatically.
- **Or, from a machine with Gradle installed:**
  ```bash
  gradle wrapper --gradle-version 8.5
  git add gradlew gradlew.bat gradle/wrapper/gradle-wrapper.jar
  git commit -m "Add Gradle wrapper"
  ```

After that, `./gradlew assembleDebug` / `./gradlew assembleRelease` will work
locally exactly like the CI job does.
