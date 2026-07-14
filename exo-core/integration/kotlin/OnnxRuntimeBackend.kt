/*
 * REFERENCE SKETCH — not part of any Gradle build in this repo.
 *
 * ONNX Runtime (Mobile) backend. Unlike the LiteRT LLM API, ORT gives you a raw
 * session: you own tokenization, the autoregressive loop and the KV cache. Use
 * this when you have an exported `*.onnx` decoder (optionally a per-shard
 * sub-model, which is what enables TRUE layer-pipeline across devices).
 *
 * Gradle (app):
 *   implementation("com.microsoft.onnxruntime:onnxruntime-android:1.19.0")
 */
package com.google.ai.edge.gallery.mesh.inference

import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.util.Log

private const val TAG = "EXO_BRIDGE"

class OnnxRuntimeBackend(
    private val tokenizer: TextTokenizer,     // supply an on-device tokenizer
) : BaseInferenceBackend() {

    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private var session: OrtSession? = null
    private var shardIsLast: Boolean = true

    override fun loadModel(modelPath: String, shardJson: String) {
        shardIsLast = shardJson.contains("\"is_last_layer\": true") ||
            shardJson.contains("\"is_last_layer\":true")
        val opts = OrtSession.SessionOptions().apply {
            // addNnapi()  // enable NNAPI/GPU EPs where available
        }
        session = env.createSession(modelPath, opts)
        Log.i(TAG, "ONNX session loaded: $modelPath (isLast=$shardIsLast)")
    }

    override fun submit(taskId: String, prompt: String, maxTokens: Int) {
        val sess = session ?: run { emit(OutChunk(taskId, "", true)); return }
        Thread {
            try {
                generate(sess, taskId, prompt, maxTokens)
            } catch (t: Throwable) {
                Log.e(TAG, "ONNX generate failed", t)
                emit(OutChunk(taskId, "", finished = true))
            }
        }.start()
    }

    private fun generate(sess: OrtSession, taskId: String, prompt: String, maxTokens: Int) {
        // Skeleton greedy loop. A production impl must:
        //   1) tokenize `prompt`
        //   2) run prefill, cache K/V
        //   3) loop: run decode step with past_kv, argmax next token, detokenize, emit
        //   4) stop on EOS or maxTokens
        // For a sharded sub-model, feed/emit hidden-state tensors instead of tokens
        // when !shardIsLast (see BACKENDS.md).
        var ids = tokenizer.encode(prompt)
        for (i in 0 until maxTokens) {
            val next = decodeStep(sess, ids) ?: break   // TODO: real forward pass
            if (tokenizer.isEos(next)) break
            ids = ids + next
            emit(OutChunk(taskId, tokenizer.decode(intArrayOf(next)), finished = false))
        }
        emit(OutChunk(taskId, "", finished = true))
    }

    /** TODO: run one decode step and return the next token id (null to stop). */
    private fun decodeStep(sess: OrtSession, ids: IntArray): Int? = null

    override fun cancel(taskId: String) { /* set a per-task flag checked in generate() */ }

    override fun close() {
        session?.close()
        session = null
    }
}

/** Minimal tokenizer contract the ONNX/TFLite backends need. */
interface TextTokenizer {
    fun encode(text: String): IntArray
    fun decode(ids: IntArray): String
    fun isEos(id: Int): Boolean
}
