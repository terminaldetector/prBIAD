package com.google.ai.edge.gallery.domain.rag

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.jsoup.Jsoup
import java.io.BufferedReader
import java.io.InputStreamReader
import kotlin.math.sqrt

class RagEngineImpl(private val context: Context) {
    private val documents = mutableMapOf<String, RagDocument>()
    private val chunkIndex = mutableListOf<RagChunk>()
    private val embeddingCache = mutableMapOf<String, FloatArray>()

    suspend fun addDocument(uri: Uri, documentName: String): Result<RagDocument> = withContext(Dispatchers.IO) {
        return@withContext try {
            val content = readDocumentContent(uri)
            if (content.isEmpty()) {
                return@withContext Result.failure(Exception("Document is empty"))
            }

            val chunks = createChunks(content, documentName)
            val document = RagDocument(
                id = System.currentTimeMillis().toString(),
                name = documentName,
                chunks = chunks,
                uploadedAt = System.currentTimeMillis(),
                size = content.length
            )

            documents[document.id] = document
            chunkIndex.addAll(chunks)

            // Generate embeddings for chunks
            generateEmbeddings(chunks)

            Result.success(document)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun search(query: String, topK: Int = 5): List<RagSearchResult> = withContext(Dispatchers.Default) {
        return@withContext try {
            if (chunkIndex.isEmpty()) {
                return@withContext emptyList()
            }

            // Generate query embedding
            val queryEmbedding = generateSimpleEmbedding(query)

            // Calculate similarity scores
            val results = chunkIndex
                .filter { it.embedding != null }
                .map { chunk ->
                    val similarity = cosineSimilarity(queryEmbedding, chunk.embedding!!)
                    val document = documents.values.find { doc ->
                        doc.chunks.any { it.id == chunk.id }
                    }
                    RagSearchResult(
                        chunkId = chunk.id,
                        content = chunk.content,
                        documentName = document?.name ?: "Unknown",
                        similarity = similarity,
                        metadata = chunk.metadata
                    )
                }
                .sortedByDescending { it.similarity }
                .take(topK)

            results
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun getDocuments(): List<RagDocument> = documents.values.toList()

    fun getDocumentChunkCount(documentId: String): Int {
        return documents[documentId]?.chunks?.size ?: 0
    }

    fun getTotalChunks(): Int = chunkIndex.size

    fun removeDocument(documentId: String): Boolean {
        val document = documents.remove(documentId) ?: return false
        chunkIndex.removeAll(document.chunks)
        return true
    }

    fun clearAll() {
        documents.clear()
        chunkIndex.clear()
        embeddingCache.clear()
    }

    // Private methods

    private fun readDocumentContent(uri: Uri): String {
        return try {
            context.contentResolver.openInputStream(uri)?.use { inputStream ->
                BufferedReader(InputStreamReader(inputStream)).use { reader ->
                    reader.readText()
                }
            } ?: ""
        } catch (e: Exception) {
            ""
        }
    }

    private fun createChunks(
        content: String,
        documentName: String,
        chunkSize: Int = 512,
        overlap: Int = 50
    ): List<RagChunk> {
        val chunks = mutableListOf<RagChunk>()
        var startIdx = 0
        var chunkNumber = 0

        while (startIdx < content.length) {
            val endIdx = minOf(startIdx + chunkSize, content.length)
            val chunkContent = content.substring(startIdx, endIdx).trim()

            if (chunkContent.isNotEmpty()) {
                chunks.add(
                    RagChunk(
                        id = "${documentName}_chunk_${chunkNumber}",
                        content = chunkContent,
                        embedding = null, // Will be generated
                        metadata = mapOf(
                            "document" to documentName,
                            "chunk_number" to chunkNumber.toString(),
                            "position" to startIdx.toString()
                        )
                    )
                )
            }

            startIdx = if (endIdx < content.length) endIdx - overlap else content.length
            chunkNumber++
        }

        return chunks
    }

    private suspend fun generateEmbeddings(chunks: List<RagChunk>) {
        chunks.forEach { chunk ->
            // Generate simple embedding based on word frequency
            val embedding = generateSimpleEmbedding(chunk.content)
            chunk.embedding = embedding
            embeddingCache[chunk.id] = embedding
        }
    }

    // Simple embedding generation using word frequency (TF-IDF like approach)
    private fun generateSimpleEmbedding(text: String, dimension: Int = 384): FloatArray {
        val embedding = FloatArray(dimension)
        val words = text.toLowerCase()
            .split("\\s+".toRegex())
            .filter { it.isNotEmpty() }

        // Create word frequency map
        val wordFreq = mutableMapOf<String, Int>()
        words.forEach { word ->
            wordFreq[word] = (wordFreq[word] ?: 0) + 1
        }

        // Generate embedding by hashing words into vector
        wordFreq.forEach { (word, freq) ->
            val hash = word.hashCode().toLong() and 0xFFFFFFFF
            val indices = (0 until 3).map { (hash.rotateRight(it * 8) % dimension.toLong()).toInt().let { if (it < 0) it + dimension else it } }
            indices.forEach { idx ->
                embedding[idx] += freq.toFloat() / words.size.toFloat()
            }
        }

        // Normalize
        val norm = sqrt(embedding.map { it * it }.sum())
        if (norm > 0) {
            embedding.forEachIndexed { i, v -> embedding[i] = v / norm }
        }

        return embedding
    }

    private fun cosineSimilarity(embedding1: FloatArray, embedding2: FloatArray): Float {
        if (embedding1.size != embedding2.size) return 0f
        
        var dotProduct = 0f
        var norm1 = 0f
        var norm2 = 0f

        embedding1.indices.forEach { i ->
            dotProduct += embedding1[i] * embedding2[i]
            norm1 += embedding1[i] * embedding1[i]
            norm2 += embedding2[i] * embedding2[i]
        }

        val denominator = sqrt(norm1) * sqrt(norm2)
        return if (denominator > 0f) dotProduct / denominator else 0f
    }
}

data class RagDocument(
    val id: String,
    val name: String,
    val chunks: List<RagChunk>,
    val uploadedAt: Long = System.currentTimeMillis(),
    val size: Int = 0
)

data class RagChunk(
    val id: String,
    val content: String,
    var embedding: FloatArray? = null,
    val metadata: Map<String, String> = emptyMap()
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is RagChunk) return false

        if (id != other.id) return false
        if (content != other.content) return false
        if (embedding != null) {
            if (other.embedding == null) return false
            if (!embedding.contentEquals(other.embedding)) return false
        } else if (other.embedding != null) return false
        if (metadata != other.metadata) return false

        return true
    }

    override fun hashCode(): Int {
        var result = id.hashCode()
        result = 31 * result + content.hashCode()
        result = 31 * result + (embedding?.contentHashCode() ?: 0)
        result = 31 * result + metadata.hashCode()
        return result
    }
}

data class RagSearchResult(
    val chunkId: String,
    val content: String,
    val documentName: String,
    val similarity: Float,
    val metadata: Map<String, String> = emptyMap()
)
