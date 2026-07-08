package com.google.ai.edge.gallery.ui

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.commit
import com.google.ai.edge.gallery.R
import com.google.ai.edge.gallery.ui.chat.ChatFragment

/**
 * Single-activity host for the unified chat screen. Per the project roadmap,
 * there is intentionally no navigation graph / tab layout - ChatFragment is
 * the entire app.
 */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        if (savedInstanceState == null) {
            supportFragmentManager.commit {
                replace(R.id.fragmentContainer, ChatFragment())
            }
        }
    }
}
