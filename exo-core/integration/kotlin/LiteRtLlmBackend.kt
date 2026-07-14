/*
 * REFERENCE SKETCH — not part of any Gradle build in this repo.
 *
 * LiteRT / Google AI Edge LLM Inference backend. This is the RECOMMENDED Android
 * runtime: it ships a full generation loop + tokenizer, so exo-core only has to
 * feed it prompts and stream results.
 *
 * Gradle (app):
 *   implementation("com.google.mediapipe:tasks-genai:0.10.24")   // LLM Inference API
 * Model format: a LiteRT LLM bundle (`*.task`) placed under context.filesDir.
 */
package com.google.ai.edge.gallery.mesh.inference

import android.content.Context
import android.util.Log
import com.google.mediapipe.tasks.genai.llminference.LlmInference
import com.google.mediapipe.tasks.genai.llminference.LlmInference.LlmInferenceOptions

private const val TAG = "EXO_BRIDGE"

class LiteRtLlmBackend(private val context: Context) : BaseInferenceBackend() {

    private var llm: LlmInference? = null

    override fun loadModel(modelPath: String, shardJson: String) {
        // NOTE: LiteRT LLM Inference runs a WHOLE model. For a multi-device ring,
        // only the last-stage device should load+run; earlier stages act as relays.
        // See BACKENDS.md ("sharding caveat").
        val options = LlmInferenceOptions.builder()
            .setModelPath(modelPath)
            .setMaxTokens(1024)
            .build()
        llm = LlmInference.createFromOptions(context, options)
        Log.i(TAG, "LiteRT LLM loaded: $modelPath (shard=$shardJson)")
    }

    override fun submit(taskId: String, prompt: String, maxTokens: Int) {
        val engine = llm ?: run {
            emit(OutChunk(taskId, "", finished = true))
            return
        }
        // Stream partial results; the LiteRT progress listener reports (partial, done).
        engine.generateResponseAsync(prompt) { partialResult, done ->
            if (partialResult != null && partialResult.isNotEmpty()) {
                emit(OutChunk(taskId, partialResult, finished = false))
            }
            if (done) emit(OutChunk(taskId, "", finished = true))
        }
    }

    override fun cancel(taskId: String) {
        // LiteRT LLM Inference API has no per-request cancel; closing the session
        // cancels in-flight generation. For multi-task use, hold one session per task.
    }

    override fun close() {
        llm?.close()
        llm = null
    }
}
