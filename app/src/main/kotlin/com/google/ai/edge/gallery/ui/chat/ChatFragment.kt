package com.google.ai.edge.gallery.ui.chat

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.ai.edge.gallery.databinding.FragmentChatBinding
import com.google.ai.edge.gallery.ui.adapter.ChatMessageAdapter
import com.google.ai.edge.gallery.viewmodel.ChatViewModel
import com.google.ai.edge.gallery.viewmodel.ModeState
import kotlinx.coroutines.launch

class ChatFragment : Fragment() {
    private lateinit var binding: FragmentChatBinding
    private val viewModel: ChatViewModel by viewModels()
    private lateinit var adapter: ChatMessageAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        binding = FragmentChatBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupRecyclerView()
        setupModeToggles()
        setupChatInput()
        observeViewModel()
    }

    private fun setupRecyclerView() {
        adapter = ChatMessageAdapter()
        binding.messagesRecyclerView.apply {
            layoutManager = LinearLayoutManager(requireContext()).apply {
                stackFromEnd = true
            }
            adapter = this@ChatFragment.adapter
        }
    }

    private fun setupModeToggles() {
        // Reasoning toggle
        binding.toggleReasoning.setOnCheckedChangeListener { _, isChecked ->
            viewModel.setReasoningMode(isChecked)
            updateModeIndicators()
        }

        // Actions toggle
        binding.toggleActions.setOnCheckedChangeListener { _, isChecked ->
            viewModel.setActionsMode(isChecked)
            updateModeIndicators()
        }

        // RAG toggle
        binding.toggleRag.setOnCheckedChangeListener { _, isChecked ->
            viewModel.setRagMode(isChecked)
            updateModeIndicators()
        }

        // Load document button (visible only when RAG is enabled)
        binding.buttonLoadDocument.setOnClickListener {
            // TODO: Implement document picker
            Toast.makeText(requireContext(), "Document picker will open", Toast.LENGTH_SHORT).show()
        }
    }

    private fun setupChatInput() {
        binding.sendButton.setOnClickListener {
            val message = binding.inputEditText.text.toString().trim()
            if (message.isNotEmpty()) {
                viewModel.sendMessage(message)
                binding.inputEditText.text.clear()
            }
        }
    }

    private fun observeViewModel() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.messages.collect { messages ->
                adapter.submitList(messages)
                binding.messagesRecyclerView.scrollToPosition(messages.size - 1)
            }
        }

        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.modeState.collect { state ->
                binding.apply {
                    toggleReasoning.isChecked = state.reasoningEnabled
                    toggleActions.isChecked = state.actionsEnabled
                    toggleRag.isChecked = state.ragEnabled
                }
            }
        }

        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.isLoading.collect { isLoading ->
                binding.progressBar.visibility = if (isLoading) View.VISIBLE else View.GONE
            }
        }
    }

    private fun updateModeIndicators() {
        val reasoning = binding.toggleReasoning.isChecked
        val actions = binding.toggleActions.isChecked
        val rag = binding.toggleRag.isChecked

        val modeText = buildString {
            append("Modes: ")
            if (reasoning) append("🧠 Reasoning ")
            if (actions) append("⚡ Actions ")
            if (rag) append("📚 RAG")
        }

        binding.modeIndicator.text = modeText
    }
}
