package org.aegisneuro.watch

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
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
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import org.json.JSONArray
import org.json.JSONObject
import java.nio.charset.StandardCharsets
import kotlin.math.roundToInt

private const val VITALS_PATH = "/aegis/watch/vitals"

class MainActivity : Activity() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val measureClient by lazy { HealthServices.getClient(this).measureClient }
    private val messageClient: MessageClient by lazy { Wearable.getMessageClient(this) }

    private lateinit var statusText: TextView
    private lateinit var hrText: TextView
    private lateinit var detailText: TextView
    private lateinit var actionButton: Button

    private var isMeasuring = false
    private var lastHeartRateBpm: Int? = null
    private var senderJob: Job? = null

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            startMeasurement()
        } else {
            setStatus("Нет доступа", "Разрешите BODY_SENSORS на часах")
        }
    }

    private val measureCallback = object : MeasureCallback {
        override fun onAvailabilityChanged(dataType: DeltaDataType<*, *>, availability: Availability) {
            setStatus("Сенсор", availability.toString())
        }

        override fun onDataReceived(data: DataPointContainer) {
            val heartRates = data.getData(DataType.HEART_RATE_BPM)
            val latestBpm = heartRates.lastOrNull()?.value?.roundToInt()
            if (latestBpm != null) {
                lastHeartRateBpm = latestBpm
                hrText.text = "$latestBpm bpm"
                detailText.text = "HR получен. IBI будет добавлен отдельным провайдером."
                sendVitals(latestBpm, emptyList(), "hr_only")
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
        setStatus("Готово", "Нажмите старт для потока HR")
    }

    override fun onDestroy() {
        stopMeasurement()
        scope.cancel()
        super.onDestroy()
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(20, 20, 20, 20)
            setBackgroundColor(Color.rgb(5, 7, 10))
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
            )
        }

        statusText = TextView(this).apply {
            text = "Aegis Sensor"
            setTextColor(Color.rgb(0, 255, 204))
            textSize = 18f
            gravity = Gravity.CENTER
        }
        hrText = TextView(this).apply {
            text = "-- bpm"
            setTextColor(Color.WHITE)
            textSize = 30f
            gravity = Gravity.CENTER
        }
        detailText = TextView(this).apply {
            text = ""
            setTextColor(Color.rgb(170, 190, 200))
            textSize = 13f
            gravity = Gravity.CENTER
        }
        actionButton = Button(this).apply {
            text = "СТАРТ"
            setOnClickListener {
                if (isMeasuring) {
                    stopMeasurement()
                } else {
                    ensurePermissionAndStart()
                }
            }
        }

        root.addView(statusText)
        root.addView(hrText)
        root.addView(detailText)
        root.addView(actionButton)
        setContentView(root)
    }

    private fun ensurePermissionAndStart() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.BODY_SENSORS)
            == PackageManager.PERMISSION_GRANTED
        ) {
            startMeasurement()
        } else {
            permissionLauncher.launch(Manifest.permission.BODY_SENSORS)
        }
    }

    private fun startMeasurement() {
        if (isMeasuring) return
        scope.launch {
            try {
                val capabilities = measureClient.getCapabilitiesAsync().await()
                if (!capabilities.supportedDataTypesMeasure.contains(DataType.HEART_RATE_BPM)) {
                    setStatus("HR недоступен", "Health Services не отдает HEART_RATE_BPM")
                    return@launch
                }

                measureClient.registerMeasureCallback(DataType.HEART_RATE_BPM, measureCallback)
                isMeasuring = true
                actionButton.text = "СТОП"
                setStatus("Измеряем", "Отправляем HR на телефон")
                startHeartbeatSender()
            } catch (exc: Exception) {
                setStatus("Ошибка", exc.message ?: "Health Services")
            }
        }
    }

    private fun stopMeasurement() {
        if (!isMeasuring) return
        senderJob?.cancel()
        senderJob = null
        scope.launch {
            try {
                measureClient.unregisterMeasureCallbackAsync(DataType.HEART_RATE_BPM, measureCallback).await()
            } catch (_: Exception) {
            } finally {
                isMeasuring = false
                actionButton.text = "СТАРТ"
                setStatus("Остановлено", "Поток HR остановлен")
            }
        }
    }

    private fun startHeartbeatSender() {
        senderJob?.cancel()
        senderJob = scope.launch {
            while (isMeasuring) {
                lastHeartRateBpm?.let { sendVitals(it, emptyList(), "hr_only") }
                kotlinx.coroutines.delay(2_000)
            }
        }
    }

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
                val nodes = Wearable.getNodeClient(this@MainActivity).connectedNodes.await()
                nodes.forEach { node ->
                    messageClient.sendMessage(node.id, VITALS_PATH, payload).await()
                }
            } catch (exc: Exception) {
                runOnUiThread {
                    detailText.text = "Телефон не найден: ${exc.message ?: "Data Layer"}"
                }
            }
        }
    }

    private fun setStatus(title: String, detail: String) {
        statusText.text = title
        detailText.text = detail
    }
}
