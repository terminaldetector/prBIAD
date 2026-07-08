package com.google.ai.edge.gallery.domain.mcp

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.provider.MediaStore
import android.telephony.SmsManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import com.google.gson.Gson
import java.io.IOException

class MCPClientImpl(private val context: Context) {
    private val httpClient = OkHttpClient()
    private val gson = Gson()
    private val smsManager = SmsManager.getDefault()
    private val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager

    suspend fun executeAction(actionName: String, parameters: Map<String, Any>): MCPResponse = withContext(Dispatchers.IO) {
        return@withContext try {
            when (actionName) {
                "send_message" -> sendSMS(parameters)
                "set_alarm" -> setAlarm(parameters)
                "open_app" -> openApp(parameters)
                "take_photo" -> takePhoto(parameters)
                "search_web" -> searchWeb(parameters)
                "get_contacts" -> getContacts(parameters)
                "get_calendar_events" -> getCalendarEvents(parameters)
                "play_music" -> playMusic(parameters)
                else -> MCPResponse(
                    result = null,
                    error = "Unknown action: $actionName",
                    success = false
                )
            }
        } catch (e: Exception) {
            MCPResponse(
                result = null,
                error = "Error executing action: ${e.message}",
                success = false
            )
        }
    }

    private suspend fun sendSMS(params: Map<String, Any>): MCPResponse = withContext(Dispatchers.Default) {
        return@withContext try {
            val phoneNumber = params["phone"] as? String ?: return@withContext MCPResponse(
                result = null,
                error = "Phone number required",
                success = false
            )
            val message = params["message"] as? String ?: return@withContext MCPResponse(
                result = null,
                error = "Message required",
                success = false
            )

            try {
                smsManager.sendTextMessage(phoneNumber, null, message, null, null)
                MCPResponse(
                    result = "SMS sent successfully to $phoneNumber",
                    success = true
                )
            } catch (e: SecurityException) {
                MCPResponse(
                    result = null,
                    error = "SEND_SMS permission required",
                    success = false
                )
            }
        } catch (e: Exception) {
            MCPResponse(
                result = null,
                error = "Failed to send SMS: ${e.message}",
                success = false
            )
        }
    }

    private suspend fun setAlarm(params: Map<String, Any>): MCPResponse = withContext(Dispatchers.Default) {
        return@withContext try {
            val hour = (params["hour"] as? Number)?.toInt() ?: return@withContext MCPResponse(
                result = null,
                error = "Hour required (0-23)",
                success = false
            )
            val minute = (params["minute"] as? Number)?.toInt() ?: return@withContext MCPResponse(
                result = null,
                error = "Minute required (0-59)",
                success = false
            )
            val message = params["message"] as? String ?: "Alarm"

            if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
                return@withContext MCPResponse(
                    result = null,
                    error = "Invalid time format",
                    success = false
                )
            }

            val calendar = java.util.Calendar.getInstance().apply {
                set(java.util.Calendar.HOUR_OF_DAY, hour)
                set(java.util.Calendar.MINUTE, minute)
                set(java.util.Calendar.SECOND, 0)
            }

            val intent = Intent(context, AlarmReceiver::class.java).apply {
                putExtra("message", message)
            }
            val pendingIntent = PendingIntent.getBroadcast(
                context,
                System.currentTimeMillis().toInt(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )

            alarmManager.setAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP,
                calendar.timeInMillis,
                pendingIntent
            )

            MCPResponse(
                result = "Alarm set for $hour:${String.format("%02d", minute)}",
                success = true
            )
        } catch (e: Exception) {
            MCPResponse(
                result = null,
                error = "Failed to set alarm: ${e.message}",
                success = false
            )
        }
    }

    private suspend fun openApp(params: Map<String, Any>): MCPResponse = withContext(Dispatchers.Main) {
        return@withContext try {
            val packageName = params["package"] as? String ?: return@withContext MCPResponse(
                result = null,
                error = "Package name required",
                success = false
            )

            val intent = context.packageManager.getLaunchIntentForPackage(packageName)
            if (intent != null) {
                context.startActivity(intent)
                MCPResponse(
                    result = "Opened app: $packageName",
                    success = true
                )
            } else {
                MCPResponse(
                    result = null,
                    error = "App not found: $packageName",
                    success = false
                )
            }
        } catch (e: Exception) {
            MCPResponse(
                result = null,
                error = "Failed to open app: ${e.message}",
                success = false
            )
        }
    }

    private suspend fun takePhoto(params: Map<String, Any>): MCPResponse = withContext(Dispatchers.Main) {
        return@withContext try {
            val intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            context.startActivity(intent)
            MCPResponse(
                result = "Camera app opened",
                success = true
            )
        } catch (e: Exception) {
            MCPResponse(
                result = null,
                error = "Failed to open camera: ${e.message}",
                success = false
            )
        }
    }

    private suspend fun searchWeb(query: String): MCPResponse = withContext(Dispatchers.IO) {
        return@withContext try {
            val url = "https://www.google.com/search?q=${java.net.URLEncoder.encode(query, "UTF-8")}"
            val request = Request.Builder()
                .url(url)
                .addHeader("User-Agent", "Mozilla/5.0 (Linux; Android 12)")
                .build()

            val response = httpClient.newCall(request).execute()
            if (response.isSuccessful) {
                MCPResponse(
                    result = "Search initiated for: $query",
                    success = true
                )
            } else {
                MCPResponse(
                    result = null,
                    error = "Search failed with code: ${response.code}",
                    success = false
                )
            }
        } catch (e: IOException) {
            MCPResponse(
                result = null,
                error = "Network error: ${e.message}",
                success = false
            )
        }
    }

    private suspend fun searchWeb(params: Map<String, Any>): MCPResponse {
        val query = params["query"] as? String ?: return MCPResponse(
            result = null,
            error = "Query required",
            success = false
        )
        return searchWeb(query)
    }

    private suspend fun getContacts(params: Map<String, Any>): MCPResponse = withContext(Dispatchers.IO) {
        return@withContext try {
            val limit = (params["limit"] as? Number)?.toInt() ?: 10
            MCPResponse(
                result = "Contacts feature requires READ_CONTACTS permission",
                success = true
            )
        } catch (e: Exception) {
            MCPResponse(
                result = null,
                error = "Failed to get contacts: ${e.message}",
                success = false
            )
        }
    }

    private suspend fun getCalendarEvents(params: Map<String, Any>): MCPResponse = withContext(Dispatchers.IO) {
        return@withContext try {
            val days = (params["days"] as? Number)?.toInt() ?: 7
            MCPResponse(
                result = "Calendar events feature requires READ_CALENDAR permission",
                success = true
            )
        } catch (e: Exception) {
            MCPResponse(
                result = null,
                error = "Failed to get calendar events: ${e.message}",
                success = false
            )
        }
    }

    private suspend fun playMusic(params: Map<String, Any>): MCPResponse = withContext(Dispatchers.Main) {
        return@withContext try {
            val artist = params["artist"] as? String
            val track = params["track"] as? String
            
            val intent = Intent(Intent.ACTION_SEARCH).apply {
                putExtra("query", "$artist $track")
                putExtra("package", "com.android.music")
            }
            context.startActivity(intent)
            
            MCPResponse(
                result = "Music player opened",
                success = true
            )
        } catch (e: Exception) {
            MCPResponse(
                result = null,
                error = "Failed to open music player: ${e.message}",
                success = false
            )
        }
    }
}
