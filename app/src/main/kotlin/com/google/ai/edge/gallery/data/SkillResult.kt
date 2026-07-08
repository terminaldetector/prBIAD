package com.google.ai.edge.gallery.data

sealed class SkillResult {
    data class Success(val data: String) : SkillResult()
    data class Error(val message: String) : SkillResult()

    companion object {
        fun success(data: String) = Success(data)
        fun error(message: String) = Error(message)
    }
}
