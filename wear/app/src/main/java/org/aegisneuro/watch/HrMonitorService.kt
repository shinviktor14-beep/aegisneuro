package org.aegisneuro.watch

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.health.services.client.HealthServices
import androidx.health.services.client.MeasureCallback
import androidx.health.services.client.data.Availability
import androidx.health.services.client.data.DataPointContainer
import androidx.health.services.client.data.DataType
import androidx.health.services.client.data.DeltaDataType
import com.google.android.gms.wearable.MessageClient
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import org.json.JSONArray
import org.json.JSONObject
import java.nio.charset.StandardCharsets
import kotlin.math.roundToInt

private const val TAG = "HrMonitorService"
private const val CHANNEL_ID = "aegis_hr_channel"
private const val NOTIFICATION_ID = 1001
private const val VITALS_PATH = "/aegis/watch/vitals"
private const val ACTION_START = "org.aegisneuro.watch.ACTION_START_HR"
private const val ACTION_STOP = "org.aegisneuro.watch.ACTION_STOP_HR"

class HrMonitorService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val measureClient by lazy { HealthServices.getClient(this).measureClient }
    private val messageClient: MessageClient by lazy { Wearable.getMessageClient(this) }

    private var isMeasuring = false
    private var lastHeartRateBpm: Int? = null
    private var senderJob: Job? = null
    private var wakeLock: PowerManager.WakeLock? = null

    private val measureCallback = object : MeasureCallback {
        override fun onAvailabilityChanged(dataType: DeltaDataType<*, *>, availability: Availability) {
            Log.d(TAG, "Доступность сенсора: $availability")
            updateNotification("Aegis: ${availability}")
        }

        override fun onDataReceived(data: DataPointContainer) {
            val heartRates = data.getData(DataType.HEART_RATE_BPM)
            val latestBpm = heartRates.lastOrNull()?.value?.roundToInt()
            if (latestBpm != null) {
                lastHeartRateBpm = latestBpm
                Log.d(TAG, "HR получен: $latestBpm bpm")
                updateNotification("Aegis: $latestBpm bpm")
                sendVitals(latestBpm, generateSyntheticIbi(latestBpm), "hr_only")
                broadcastHrUpdate(latestBpm)
                saveLastBpm(latestBpm)
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopHrMonitoring()
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_START -> {
                // fall through to start
            }
        }
        acquireWakeLock()
        startForeground(NOTIFICATION_ID, buildNotification("Aegis: Измерение пульса…"))
        startHrMonitoring()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        stopHrMonitoring()
        releaseWakeLock()
        clearPrefs()
        scope.cancel()
        super.onDestroy()
    }

    // ── WakeLock ──────────────────────────────────────────────────

    private fun acquireWakeLock() {
        if (wakeLock?.isHeld == true) return
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "AegisNeuro::HrMonitorWakeLock"
        ).apply {
            acquire(4 * 60 * 60 * 1000L) // 4 часа максимум, сервис обновит при необходимости
        }
        Log.d(TAG, "WakeLock получен")
    }

    private fun releaseWakeLock() {
        wakeLock?.let {
            if (it.isHeld) {
                it.release()
                Log.d(TAG, "WakeLock освобождён")
            }
        }
        wakeLock = null
    }

    // ── HR Measurement ───────────────────────────────────────────

    private fun startHrMonitoring() {
        if (isMeasuring) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.BODY_SENSORS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            Log.e(TAG, "Нет разрешения BODY_SENSORS")
            updateNotification("Aegis: Нет разрешения BODY_SENSORS")
            return
        }
        scope.launch {
            try {
                measureClient.registerMeasureCallback(DataType.HEART_RATE_BPM, measureCallback)
                isMeasuring = true
                startHeartbeatSender()
                Log.d(TAG, "Мониторинг HR запущен")
            } catch (exc: Exception) {
                Log.e(TAG, "Ошибка запуска HR: ${exc.message}", exc)
                updateNotification("Aegis: Ошибка — ${exc.message}")
            }
        }
    }

    private fun stopHrMonitoring() {
        if (!isMeasuring) return
        senderJob?.cancel()
        senderJob = null
        scope.launch {
            try {
                measureClient.unregisterMeasureCallbackAsync(DataType.HEART_RATE_BPM, measureCallback)
            } catch (_: Exception) {
            } finally {
                isMeasuring = false
                lastHeartRateBpm = null
                Log.d(TAG, "Мониторинг HR остановлен")
            }
        }
    }

    private fun startHeartbeatSender() {
        senderJob?.cancel()
        senderJob = scope.launch {
            while (isMeasuring) {
                lastHeartRateBpm?.let {
                    sendVitals(it, generateSyntheticIbi(it), "hr_only")
                }
                delay(2_000)
            }
        }
    }

    // ── Data Layer ───────────────────────────────────────────────

    private fun sendVitals(heartRateBpm: Int, ibiMs: List<Int>, quality: String) {
        scope.launch(Dispatchers.IO) {
            val payload = JSONObject()
                .put("source", "galaxy_watch4")
                .put("timestamp_ms", System.currentTimeMillis())
                .put("heart_rate_bpm", heartRateBpm)
                .put("ibi_ms", JSONArray(ibiMs))
                .put("quality", quality)
                .toString()
                .toByteArray(StandardCharsets.UTF_8)

            try {
                val nodes = Wearable.getNodeClient(this@HrMonitorService).connectedNodes.await()
                nodes.forEach { node ->
                    messageClient.sendMessage(node.id, VITALS_PATH, payload).await()
                }
                Log.d(TAG, "Данные отправлены на ${nodes.size} узлов")
            } catch (exc: Exception) {
                Log.w(TAG, "Ошибка отправки данных: ${exc.message}")
            }
        }
    }

    private fun generateSyntheticIbi(bpm: Int): List<Int> {
        val avgInterval = 60000.0 / bpm
        val ibiList = mutableListOf<Int>()
        for (i in 0 until 15) {
            val rsaFactor = java.lang.Math.sin(i * 0.8) * 45.0
            val randomNoise = (java.lang.Math.random() * 20.0 - 10.0)
            ibiList.add((avgInterval + rsaFactor + randomNoise).roundToInt())
        }
        return ibiList
    }

    // ── Notification ────────────────────────────────────────────

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notification_channel_name),
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = getString(R.string.notification_channel_desc)
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        val stopIntent = Intent(this, HrMonitorService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            this, 0, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val contentIntent = Intent(this, MainActivity::class.java)
        val contentPendingIntent = PendingIntent.getActivity(
            this, 0, contentIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.notification_title))
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setOngoing(true)
            .setContentIntent(contentPendingIntent)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "СТОП", stopPendingIntent)
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, buildNotification(text))
    }

    // ── Broadcast & SharedPrefs (for Activity UI sync) ──────────

    private fun broadcastHrUpdate(bpm: Int) {
        val intent = Intent(MainActivity.ACTION_HR_UPDATE).apply {
            putExtra(MainActivity.EXTRA_HR_BPM, bpm)
            setPackage(packageName)
        }
        sendBroadcast(intent)
    }

    private fun saveLastBpm(bpm: Int) {
        getSharedPreferences("aegis_hr_prefs", Context.MODE_PRIVATE)
            .edit()
            .putInt("last_hr_bpm", bpm)
            .putBoolean("hr_monitor_active", true)
            .apply()
    }

    private fun clearPrefs() {
        getSharedPreferences("aegis_hr_prefs", Context.MODE_PRIVATE)
            .edit()
            .remove("last_hr_bpm")
            .putBoolean("hr_monitor_active", false)
            .apply()
    }

    companion object {
        fun start(context: Context) {
            val intent = Intent(context, HrMonitorService::class.java).apply {
                action = ACTION_START
            }
            ContextCompat.startForegroundService(context, intent)
        }

        fun stop(context: Context) {
            val intent = Intent(context, HrMonitorService::class.java).apply {
                action = ACTION_STOP
            }
            ContextCompat.startForegroundService(context, intent)
        }
    }
}