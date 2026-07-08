package com.google.ai.edge.gallery.domain

class DynamicPromptBuilder {
    fun buildSystemPrompt(
        reasoning: Boolean = false,
        actions: Boolean = false,
        rag: Boolean = false
    ): String {
        return buildString {
            append("You are an AI assistant powered by Google's AI Edge model.\n")
            append("You help users with intelligent conversation and task automation.\n\n")

            if (reasoning) {
                append("REASONING MODE ENABLED:\n")
                append("- Before providing your answer, show your thinking process in <thinking>...</thinking> tags.\n")
                append("- Break down complex problems into steps.\n")
                append("- Consider multiple approaches before choosing the best one.\n\n")
            }

            if (actions) {
                append("ACTIONS MODE ENABLED:\n")
                append("- You have access to native device actions through MCP (Model Context Protocol).\n")
                append("- Available actions: send_message, set_alarm, open_app, take_photo, search_web.\n")
                append("- Call actions by using the structured format: <action name=\"action_name\">parameters</action>.\n")
                append("- Always ask for confirmation before performing sensitive actions.\n\n")
            }

            if (rag) {
                append("RAG MODE ENABLED:\n")
                append("- You have access to a knowledge base built from uploaded documents.\n")
                append("- When answering questions, prioritize information from the RAG index.\n")
                append("- Include references to source documents when applicable using [Source: document_name].\n")
                append("- If no relevant information is found in RAG, use your general knowledge and indicate uncertainty.\n\n")
            }

            append("Respond in a helpful, clear, and concise manner.\n")
            append("Maintain context throughout the conversation.\n")
        }
    }
}
