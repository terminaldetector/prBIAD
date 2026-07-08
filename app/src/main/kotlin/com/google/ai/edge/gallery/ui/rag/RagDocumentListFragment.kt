package com.google.ai.edge.gallery.ui.rag

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.ai.edge.gallery.databinding.FragmentRagDocumentListBinding
import kotlinx.coroutines.launch

class RagDocumentListFragment : Fragment() {
    private lateinit var binding: FragmentRagDocumentListBinding
    private lateinit var adapter: RagDocumentAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        binding = FragmentRagDocumentListBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupRecyclerView()
        observeUIState()
    }

    private fun setupRecyclerView() {
        adapter = RagDocumentAdapter { documentId ->
            // Remove document callback
        }
        binding.documentsRecyclerView.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = this@RagDocumentListFragment.adapter
        }
    }

    private fun observeUIState() {
        viewLifecycleOwner.lifecycleScope.launch {
            // TODO: Get RagDocumentManager from shared ViewModel
            // viewModel.uiState.collect { state ->
            //     adapter.submitList(state.documents)
            //     binding.totalChunksTextView.text = "Total chunks: ${state.totalChunks}"
            // }
        }
    }
}
