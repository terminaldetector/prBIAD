package com.google.ai.edge.gallery.domain.skills

import com.google.ai.edge.gallery.data.SkillResult
import com.google.ai.edge.gallery.domain.rag.RagEngineImpl

class RAGSkillImpl(private val ragEngine: RagEngineImpl) : Skill {
    override val name = "rag_search"
    override val description = "Search and retrieve from RAG knowledge base"
    override val category = SkillCategory.RAG_SEARCH

    override suspend fun execute(parameters: Map<String, Any>): SkillResult {
        return try {
            val query = parameters["query"] as? String ?: return SkillResult.error("Query required")
            val topK = (parameters["topK"] as? Number)?.toInt() ?: 5

            val results = ragEngine.search(query, topK)

            if (results.isEmpty()) {
                SkillResult.success("No relevant documents found in RAG database")
            } else {
                val formattedResults = formatResults(results)
                SkillResult.success(formattedResults)
            }
        } catch (e: Exception) {
            SkillResult.error("RAG search failed: ${e.message}")
        }
    }

    private fun formatResults(results: List<com.google.ai.edge.gallery.domain.rag.RagSearchResult>): String {
        return buildString {
            append("Found ${results.size} relevant results:\n\n")
            results.forEachIndexed { index, result ->
                append("[${index + 1}] Source: ${result.documentName}\n")
                append("Similarity: ${(result.similarity * 100).toInt()}%\n")
                append("${result.content.take(300)}...\n\n")
            }
        }
    }
}
