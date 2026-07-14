# Keep Gson-serialised model fields intact for host apps that enable R8/ProGuard.
-keep class com.bitchat.android.model.** { *; }
-keepattributes Signature, *Annotation*
