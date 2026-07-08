# Add project specific ProGuard rules here.
# Keep data models that are (de)serialized via Gson reflection.
-keep class com.google.ai.edge.gallery.data.** { *; }
-keep class com.google.ai.edge.gallery.domain.mcp.MCPRequest { *; }
-keep class com.google.ai.edge.gallery.domain.mcp.MCPResponse { *; }
-keep class com.google.ai.edge.gallery.domain.rag.** { *; }

# OkHttp / Okio
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn javax.annotation.**
