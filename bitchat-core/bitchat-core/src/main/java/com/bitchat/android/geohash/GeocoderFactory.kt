package com.bitchat.android.geohash

import android.content.Context
import android.location.Geocoder

/**
 * Factory to provide the best available geocoder.
 */
object GeocoderFactory {
    fun get(context: Context): GeocoderProvider {
        // bitchat-core only ships the on-device Android geocoder. The network-backed
        // OpenStreetMap provider was excluded to avoid an OkHttp/Tor dependency.
        return AndroidGeocoderProvider(context)
    }
}
