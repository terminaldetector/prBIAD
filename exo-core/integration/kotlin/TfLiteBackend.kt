/*
 * REFERENCE SKETCH — not part of any Gradle build in this repo.
 *
 * TensorFlow Lite backend using the raw `Interpreter` (Saturn Mask already depends
 * on `org.tensorflow:tensorflow-lite`). Like ONNX, you own tokenization + the
 * autoregressive loop; prefer LiteRtLlmBackend for turnkey LLM generation.
 *
 * Gradle (app): org.tensorflow:tensorflow-lite (+ optional tensorflow-lite-gpu)
 * Model format: `*.tflite` (a decoder graph you drive step-by-step).
 */
package com.google.ai.edge.gallery.mesh.inference

import android.util.Log
import org.tensorflow.lite.Interpreter
import java.io.File

private const val TAG = "EXO_BRIDGE"

class TfLiteBackend(
    private val tokenizer: TextTokenizer,
) : BaseInferenceBackend() {

    private var interpreter: Interpreter? = null

    override fun loadModel(modelPath: String, shardJson: String) {
        val options = Interpreter.Options().apply {
            setNumThreads(4)
            // addDelegate(GpuDelegate())  // optional GPU acceleration
        }
        interpreter = Interpreter(File(modelPath), options)
        Log.i(TAG, "TFLite model loaded: $modelPath (shard=$shardJson)")
    }

    override fun submit(taskId: String, prompt: String, maxTokens: Int) {
        val interp = interpreter ?: run { emit(OutChunk(taskId, "", true)); return }
        Thread {
            try {
                var ids = tokenizer.encode(prompt)
                for (i in 0 until maxTokens) {
                    val next = decodeStep(interp, ids) ?: break   // TODO real forward
                    if (tokenizer.isEos(next)) break
                    ids = ids + next
                    emit(OutChunk(taskId, tokenizer.decode(intArrayOf(next)), finished = false))
                }
            } finally {
                emit(OutChunk(taskId, "", finished = true))
            }
        }.start()
    }

    /** TODO: run one decode step (with KV cache tensors) and return next token id. */
    private fun decodeStep(interp: Interpreter, ids: IntArray): Int? = null

    override fun cancel(taskId: String) { /* per-task cancel flag */ }

    override fun close() {
        interpreter?.close()
        interpreter = null
    }
}
