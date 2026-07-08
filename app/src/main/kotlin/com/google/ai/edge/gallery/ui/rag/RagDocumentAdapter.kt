package com.google.ai.edge.gallery.ui.rag

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.google.ai.edge.gallery.databinding.ItemRagDocumentBinding
import com.google.ai.edge.gallery.domain.rag.RagDocument
import java.text.SimpleDateFormat
import java.util.*

class RagDocumentAdapter(
    private val onRemoveClick: (String) -> Unit
) : ListAdapter<RagDocument, RagDocumentAdapter.ViewHolder>(
    RagDocumentDiffCallback()
) {
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemRagDocumentBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return ViewHolder(binding, onRemoveClick)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class ViewHolder(
        private val binding: ItemRagDocumentBinding,
        private val onRemoveClick: (String) -> Unit
    ) : RecyclerView.ViewHolder(binding.root) {
        fun bind(document: RagDocument) {
            binding.apply {
                documentNameText.text = document.name
                chunkCountText.text = "${document.chunks.size} chunks"
                documentSizeText.text = "${(document.size / 1024).toInt()} KB"
                
                val dateFormat = SimpleDateFormat("MMM dd, yyyy HH:mm", Locale.getDefault())
                uploadedAtText.text = "Uploaded: ${dateFormat.format(Date(document.uploadedAt))}"
                
                removeButton.setOnClickListener {
                    onRemoveClick(document.id)
                }
            }
        }
    }

    private class RagDocumentDiffCallback : DiffUtil.ItemCallback<RagDocument>() {
        override fun areItemsTheSame(oldItem: RagDocument, newItem: RagDocument) =
            oldItem.id == newItem.id

        override fun areContentsTheSame(oldItem: RagDocument, newItem: RagDocument) =
            oldItem == newItem
    }
}
