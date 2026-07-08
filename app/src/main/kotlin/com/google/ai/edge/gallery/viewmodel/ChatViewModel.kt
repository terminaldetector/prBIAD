package com.google.ai.edge.gallery.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.ai.edge.gallery.data.ChatMessage
import com.google.ai.edge.gallery.domain.DynamicPromptBuilder
import com.google.ai.edge.gallery.domain.SkillManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class ModeState(
    val reasoningEnabled: Boolean = false,
    val actionsEnabled: Boolean = false,
    val ragEnabled: Boolean = false
)

class ChatViewModel : ViewModel() {
    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages

    private val _modeState = MutableStateFlow(ModeState())
    val modeState: StateFlow<ModeState> = _modeState

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading

    private val promptBuilder = DynamicPromptBuilder()
    private val skillManager = SkillManager()

    fun setReasoningMode(enabled: Boolean) {
        _modeState.value = _modeState.value.copy(reasoningEnabled = enabled)
    }

    fun setActionsMode(enabled: Boolean) {
        _modeState.value = _modeState.value.copy(actionsEnabled = enabled)
    }

    fun setRagMode(enabled: Boolean) {
        _modeState.value = _modeState.value.copy(ragEnabled = enabled)
    }

    fun sendMessage(userInput: String) {
        viewModelScope.launch {
            _isLoading.value = true

            // Add user message
            val userMessage = ChatMessage(
                id = System.currentTimeMillis(),
                content = userInput,
                isUser = true,
                timestamp = System.currentTimeMillis()
            )

            _messages.value = _messages.value + userMessage

            // Build system prompt based on current mode
            val state = _modeState.value
            val systemPrompt = promptBuilder.buildSystemPrompt(
                reasoning = state.reasoningEnabled,
                actions = state.actionsEnabled,
                rag = state.ragEnabled
            )

            // Update available skills based on mode
            skillManager.updateAvailableSkills(
                reasoning = state.reasoningEnabled,
                actions = state.actionsEnabled,
                rag = state.ragEnabled
            )

            // Get AI response
            val response = try {
                // TODO: Integrate actual AI inference here
                "Response from AI with modes: $state"
            } catch (e: Exception) {
                "Error: ${e.message}"
            }

            // Add AI message
            val aiMessage = ChatMessage(
                id = System.currentTimeMillis() + 1,
                content = response,
                isUser = false,
                timestamp = System.currentTimeMillis()
            )

            _messages.value = _messages.value + aiMessage
            _isLoading.value = false
        }
    }
}
