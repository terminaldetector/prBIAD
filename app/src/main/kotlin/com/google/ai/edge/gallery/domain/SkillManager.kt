package com.google.ai.edge.gallery.domain

import com.google.ai.edge.gallery.domain.skills.Skill
import com.google.ai.edge.gallery.domain.skills.NativeActionSkill
import com.google.ai.edge.gallery.domain.skills.WebScraperSkill
import com.google.ai.edge.gallery.domain.skills.RAGSkill

class SkillManager {
    private val nativeSkills = mutableListOf<Skill>()
    private var availableSkills = mutableListOf<Skill>()

    init {
        // Initialize always-available native skills
        nativeSkills.add(NativeActionSkill())
        nativeSkills.add(WebScraperSkill())
    }

    fun updateAvailableSkills(
        reasoning: Boolean = false,
        actions: Boolean = false,
        rag: Boolean = false
    ) {
        availableSkills.clear()

        // Always available
        availableSkills.addAll(nativeSkills)

        // Conditional skills based on modes
        if (actions) {
            availableSkills.add(NativeActionSkill())
        }

        if (rag) {
            availableSkills.add(RAGSkill())
        }
    }

    fun getAvailableSkills(): List<Skill> {
        return availableSkills.toList()
    }

    fun getSkillByName(name: String): Skill? {
        return availableSkills.find { it.name == name }
    }
}
