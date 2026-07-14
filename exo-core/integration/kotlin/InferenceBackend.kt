/*
 * REFERENCE SKETCH — not part of any Gradle build in this repo.
 *
 * This is the Kotlin side of exo-core's `bridge` inference backend. An instance
 * is passed into Python (Chaquopy) and adapted by
 * `exo_core.inference.backends.bridge.BridgeBuilder` / `BridgeEngine`.
 *
 * Copy these files into the Saturn Mask app (e.g.
 * `app/src/main/kotlin/com/google/ai/edge/gallery/mesh/inference/`) once the app
 * toolchain and Chaquopy are set up (see ../../../INTEGRATION.md).
 */
package com.google.ai.edge.gallery.mesh.inference

import java.util.concurrent.ConcurrentLinkedQueue

/**
 * Contract the Python bridge backend expects (see `HostLlmRunner` in
 * `exo_core/inference/backends/bridge.py`). Method names intentionally match the
 * Python side (`loadModel`, `submit`, `poll`, `cancel`, `close`).
 */
interface InferenceBackend {
    /**
     * @param modelPath on-device weights path (e.g. under context.getFilesDir()).
     * @param shardJson layer band for this device; full-model runtimes may ignore it.
     */
    fun loadModel(modelPath: String, shardJson: String)

    fun submit(taskId: String, prompt: String, maxTokens: Int)

    /** JSON array of pending chunks, then cleared. */
    fun poll(): String

    fun cancel(taskId: String)

    fun close()
}

/** A single streamed output chunk. */
data class OutChunk(val taskId: String, val text: String, val finished: Boolean)

/**
 * Base class handling the thread-safe chunk queue and JSON serialisation, so
 * concrete backends only implement model loading + generation.
 */
abstract class BaseInferenceBackend : InferenceBackend {

    protected val queue = ConcurrentLinkedQueue<OutChunk>()

    protected fun emit(chunk: OutChunk) = queue.add(chunk)

    override fun poll(): String {
        val sb = StringBuilder("[")
        var first = true
        while (true) {
            val c = queue.poll() ?: break
            if (!first) sb.append(',')
            first = false
            sb.append("{\"task_id\":").append(jsonStr(c.taskId))
                .append(",\"text\":").append(jsonStr(c.text))
                .append(",\"finished\":").append(c.finished).append('}')
        }
        sb.append(']')
        return sb.toString()
    }

    private fun jsonStr(s: String): String {
        val out = StringBuilder("\"")
        for (ch in s) {
            when (ch) {
                '\\' -> out.append("\\\\")
                '"' -> out.append("\\\"")
                '\n' -> out.append("\\n")
                '\r' -> out.append("\\r")
                '\t' -> out.append("\\t")
                else -> out.append(ch)
            }
        }
        return out.append('"').toString()
    }
}
