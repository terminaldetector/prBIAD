package com.google.ai.edge.gallery.ui.rag

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.ai.edge.gallery.domain.rag.RagEngineImpl
import com.google.ai.edge.gallery.domain.rag.RagDocument
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class RagDocumentUIState(
    val documents: List<RagDocument> = emptyList(),
    val totalChunks: Int = 0,
    val isLoading: Boolean = false,
    val error: String? = null
)

class RagDocumentManager(
    private val ragEngine: RagEngineImpl
) : ViewModel() {
    private val _uiState = MutableStateFlow(RagDocumentUIState())
    val uiState: StateFlow<RagDocumentUIState> = _uiState

    init {
        updateUI()
    }

    fun uploadDocument(uri: Uri, fileName: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            
            val result = ragEngine.addDocument(uri, fileName)
            
            result.onSuccess {
                updateUI()
                _uiState.value = _uiState.value.copy(isLoading = false)
            }
            
            result.onFailure { exception ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Failed to upload: ${exception.message}"
                )
            }
        }
    }

    fun removeDocument(documentId: String) {
        viewModelScope.launch {
            ragEngine.removeDocument(documentId)
            updateUI()
        }
    }

    fun clearAllDocuments() {
        viewModelScope.launch {
            ragEngine.clearAll()
            updateUI()
        }
    }

    private fun updateUI() {
        _uiState.value = _uiState.value.copy(
            documents = ragEngine.getDocuments(),
            totalChunks = ragEngine.getTotalChunks()
        )
    }
}
