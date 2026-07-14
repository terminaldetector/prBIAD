package com.bitchat.android.ui

import android.content.Context
import android.util.Log
import androidx.core.app.NotificationManagerCompat
import com.bitchat.android.util.NotificationIntervalManager

/**
 * Headless stub of the original UI NotificationManager.
 *
 * The full BitChat app posts rich Android notifications for direct messages and
 * geohash chats. The distilled `bitchat-core` transport module is UI-agnostic, so
 * this stub preserves the constructor and the two methods the mesh transports call
 * while performing no UI work. Host applications should observe messages via the
 * [com.bitchat.android.mesh.MeshDelegate]/[com.bitchat.core.api.BitchatCore] API and
 * present their own notifications.
 */
class NotificationManager(
    private val context: Context,
    private val notificationManager: NotificationManagerCompat,
    private val notificationIntervalManager: NotificationIntervalManager
) {
    companion object {
        private const val TAG = "NotificationManager(core-stub)"
    }

    @Volatile
    private var isAppInBackground = false

    fun setAppBackgroundState(inBackground: Boolean) {
        isAppInBackground = inBackground
    }

    fun showPrivateMessageNotification(senderPeerID: String, senderNickname: String, messagePreview: String) {
        // No-op in the headless core. Kept for API compatibility with the mesh layer.
        Log.d(TAG, "Private message from $senderNickname ($senderPeerID) [notifications disabled in core]")
    }
}
