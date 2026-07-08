package com.google.ai.edge.gallery.domain.skills

import com.google.ai.edge.gallery.data.SkillResult

interface Skill {
    val name: String
    val description: String
    val category: SkillCategory

    suspend fun execute(parameters: Map<String, Any>): SkillResult
}

enum class SkillCategory {
    NATIVE_ACTION,
    WEB_SCRAPER,
    RAG_SEARCH,
    REASONING
}
