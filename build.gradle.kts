plugins {
    id("com.android.application") version "8.2.2" apply false
    kotlin("android") version "1.9.22" apply false
    kotlin("kapt") version "1.9.22" apply false
}

tasks.register("clean", Delete::class) {
    delete(rootProject.buildDir)
}
