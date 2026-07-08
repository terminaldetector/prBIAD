package com.google.ai.edge.gallery.data

data class ChatMessage(
    val id: Long,
    val content: String,
    val isUser: Boolean,
    val timestamp: Long,
    val sources: List<String> = emptyList(), // For RAG references
    val thinking: String? = null // For reasoning mode
)
