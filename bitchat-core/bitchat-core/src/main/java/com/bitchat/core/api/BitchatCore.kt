package com.bitchat.core.api

import android.content.Context
import android.util.Log
import com.bitchat.android.mesh.BluetoothMeshDelegate
import com.bitchat.android.mesh.BluetoothMeshService
import com.bitchat.android.model.BitchatMessage

/**
 * Minimal, UI-agnostic entry point for the distilled BitChat mesh transport.
 *
 * `BitchatCore` wraps [BluetoothMeshService] and exposes a small send/receive API so a host
 * application (or another process, via its own Intent/AIDL bridge) can participate in the
 * Bluetooth LE mesh without pulling in any of the original BitChat UI, analytics, file, voice
 * or Nostr/Tor code.
 *
 * Typical usage:
 * ```
 * val core = BitchatCore(context)
 * core.listener = object : BitchatCore.Listener {
 *     override fun onMessage(message: BitchatMessage) { /* render */ }
 *     override fun onPeerListUpdated(peerIDs: List<String>) { /* update roster */ }
 * }
 * core.start(nickname = "alice")
 * core.sendBroadcast("hello mesh")
 * core.sendPrivate("hi", recipientPeerID)
 * core.stop()
 * ```
 *
 * All Bluetooth permissions listed in the module manifest must be granted by the host before
 * calling [start].
 */
class BitchatCore(context: Context) {

    /** Callbacks delivered on the mesh worker threads; marshal to your own threads as needed. */
    interface Listener {
        /** A broadcast or (decrypted) private message was received. */
        fun onMessage(message: BitchatMessage)

        /** The set of currently reachable peer IDs changed. */
        fun onPeerListUpdated(peerIDs: List<String>) {}

        /** A delivery acknowledgement was received for a message we sent. */
        fun onDeliveryAck(messageID: String, fromPeerID: String) {}

        /** A read receipt was received for a message we sent. */
        fun onReadReceipt(messageID: String, fromPeerID: String) {}
    }

    private val appContext = context.applicationContext
    private val mesh = BluetoothMeshService(appContext)

    /** Stable local peer identifier (first 16 hex chars of the Noise identity fingerprint). */
    val myPeerID: String get() = mesh.myPeerID

    /** Host-provided display name announced to peers. */
    @Volatile
    var nickname: String = mesh.myPeerID

    /** Register to receive messages and peer/roster updates. */
    @Volatile
    var listener: Listener? = null

    init {
        mesh.delegate = object : BluetoothMeshDelegate {
            override fun didReceiveMessage(message: BitchatMessage) {
                listener?.onMessage(message)
            }

            override fun didUpdatePeerList(peers: List<String>) {
                listener?.onPeerListUpdated(peers)
            }

            override fun didReceiveChannelLeave(channel: String, fromPeer: String) {}

            override fun didReceiveDeliveryAck(messageID: String, recipientPeerID: String) {
                listener?.onDeliveryAck(messageID, recipientPeerID)
            }

            override fun didReceiveReadReceipt(messageID: String, recipientPeerID: String) {
                listener?.onReadReceipt(messageID, recipientPeerID)
            }

            override fun didReceiveVerifyChallenge(peerID: String, payload: ByteArray, timestampMs: Long) {}

            override fun didReceiveVerifyResponse(peerID: String, payload: ByteArray, timestampMs: Long) {}

            override fun decryptChannelMessage(encryptedContent: ByteArray, channel: String): String? = null

            override fun getNickname(): String = nickname

            override fun isFavorite(peerID: String): Boolean = false
        }
    }

    /** Start advertising, scanning and connecting on the Bluetooth LE mesh. */
    @JvmOverloads
    fun start(nickname: String? = null) {
        nickname?.let { this.nickname = it }
        Log.d(TAG, "Starting bitchat-core mesh as peer $myPeerID (nickname=${this.nickname})")
        mesh.startServices()
    }

    /** Stop all mesh activity and release Bluetooth resources. */
    fun stop() {
        mesh.stopServices()
    }

    /** Send an unencrypted broadcast message to the whole mesh. */
    @JvmOverloads
    fun sendBroadcast(content: String, mentions: List<String> = emptyList(), channel: String? = null) {
        mesh.sendMessage(content, mentions, channel)
    }

    /** Send an end-to-end encrypted (Noise) private message to a specific peer. */
    @JvmOverloads
    fun sendPrivate(content: String, recipientPeerID: String, recipientNickname: String = recipientPeerID, messageID: String? = null) {
        mesh.sendPrivateMessage(content, recipientPeerID, recipientNickname, messageID)
    }

    /** Send a read receipt for a received private message. */
    fun sendReadReceipt(messageID: String, recipientPeerID: String) {
        mesh.sendReadReceipt(messageID, recipientPeerID, nickname)
    }

    /** Current peerID -> nickname map for reachable peers. */
    fun getPeerNicknames(): Map<String, String> = mesh.getPeerNicknames()

    /** Whether an encrypted Noise session is established with the given peer. */
    fun hasEstablishedSession(peerID: String): Boolean = mesh.hasEstablishedSession(peerID)

    /** Direct access to the underlying mesh service for advanced use cases. */
    fun meshService(): BluetoothMeshService = mesh

    companion object {
        private const val TAG = "BitchatCore"
    }
}
