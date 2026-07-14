/*
 * REFERENCE SKETCH — not part of any Gradle build in this repo.
 *
 * Host contract for TRUE layer-sharded inference (pipeline parallelism), the
 * counterpart of `exo_core.inference.sharded.ShardRunner`. Unlike `InferenceBackend`
 * (whole-model), a `ShardBackend` runs only THIS device's band of layers and
 * exchanges hidden-state tensors with neighbours. See ../../SHARDING.md.
 *
 * ONNX Runtime is the recommended host: export a per-shard sub-model
 * (`shard_i.onnx`) whose inputs/outputs are hidden states (+ this shard's KV cache,
 * kept locally between decode steps).
 */
package com.google.ai.edge.gallery.mesh.inference

/**
 * One shard's executor. `embed` runs only on the first shard, `sample`/`detok`
 * only on the last, `forward` on every shard. Hidden states are opaque byte blobs
 * (e.g. little-endian float16) — exo-core only relays them; the encoding is a
 * private contract between neighbouring shards (identical model export).
 */
interface ShardBackend {
    /** Load this shard's sub-model. `shardJson` has start_layer/end_layer/world_size/… */
    fun load(shardJson: String)

    /** First shard only: token id -> input hidden state for layer `start_layer`. */
    fun embed(tokenId: Int): ByteArray

    /** Any shard: run layers [start_layer, end_layer); update this shard's local KV. */
    fun forward(hidden: ByteArray): ByteArray

    /** Last shard only: hidden state -> next token id (applies final norm + lm_head + sampling). */
    fun sample(hidden: ByteArray): Int

    /** Last shard only: token id -> text piece. */
    fun detok(tokenId: Int): String

    fun eosId(): Int

    fun close()
}

/*
 * Wiring (Chaquopy), on each participating device:
 *
 *   val shard: ShardBackend = OnnxShardBackend(context)   // your impl
 *   val py = Python.getInstance()
 *   val pipe = py.getModule("exo_core.inference.sharded").callAttr(
 *       "ShardedPipeline",
 *       nodeId, meshAdapter, ringArray, shard, coordinatorId,
 *       Kwarg("max_new_tokens", 64)
 *   )
 *   // non-coordinator devices:
 *   asyncio.callAttr("run", pipe.callAttr("run_forever"))
 *   // coordinator:
 *   val ids = asyncio.callAttr("run", pipe.callAttr("generate", promptTokenIds))
 *
 * Note: `ShardedPipeline` expects a ShardRunner-shaped object; a thin Python
 * shim can wrap `ShardBackend` if method-name / byte marshalling needs adjusting,
 * but the names above already match `ShardRunner`.
 */
