package org.aegisneuro.watch

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private lateinit var statusText: TextView
    private lateinit var hrText: TextView
    private lateinit var detailText: TextView
    private lateinit var actionButton: Button

    private var isMonitoring = false

    /** Receives HR updates broadcast by HrMonitorService so the UI stays current. */
    private val hrUpdateReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == ACTION_HR_UPDATE) {
                val bpm = intent.getIntExtra(EXTRA_HR_BPM, -1)
                if (bpm > 0) {
                    hrText.text = "$bpm bpm"
                    detailText.text = "HR получен. Расчет IBI активен."
                }
            }
        }
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted: Boolean ->
        if (granted) {
            startMonitoring()
        } else {
            setStatus("Нет доступа", "Разрешите BODY_SENSORS на часах")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
        setStatus("Готово", "Нажмите старт для потока HR")
        registerReceiver(hrUpdateReceiver, IntentFilter(ACTION_HR_UPDATE))
        checkIfServiceRunning()
    }

    override fun onDestroy() {
        unregisterReceiver(hrUpdateReceiver)
        scope.cancel()
        super.onDestroy()
    }

    private fun checkIfServiceRunning() {
        // Simple heuristic: if we can detect the service is running, reflect it in UI.
        // Since ForegroundService persists across activity recreation, check via intent.
        // We'll poll a small flag via shared prefs that the service updates.
        val prefs = getSharedPreferences("aegis_hr_prefs", Context.MODE_PRIVATE)
        val running = prefs.getBoolean("hr_monitor_active", false)
        if (running) {
            isMonitoring = true
            actionButton.text = "СТОП"
            setStatus("Измеряем", "Отправляем HR на телефон")
            val lastBpm = prefs.getInt("last_hr_bpm", -1)
            if (lastBpm > 0) {
                hrText.text = "$lastBpm bpm"
                detailText.text = "HR получен. Расчет IBI активен."
            }
        }
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
                if (isMonitoring) {
                    stopMonitoring()
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
            startMonitoring()
        } else {
            permissionLauncher.launch(Manifest.permission.BODY_SENSORS)
        }
    }

    private fun startMonitoring() {
        if (isMonitoring) return
        isMonitoring = true
        actionButton.text = "СТОП"
        setStatus("Измеряем", "Отправляем HR на телефон")
        HrMonitorService.start(this)
    }

    private fun stopMonitoring() {
        if (!isMonitoring) return
        isMonitoring = false
        actionButton.text = "СТАРТ"
        setStatus("Остановлено", "Поток HR остановлен")
        hrText.text = "-- bpm"
        HrMonitorService.stop(this)
    }

    private fun setStatus(title: String, detail: String) {
        statusText.text = title
        detailText.text = detail
    }

    companion object {
        const val ACTION_HR_UPDATE = "org.aegisneuro.watch.HR_UPDATE"
        const val EXTRA_HR_BPM = "hr_bpm"
    }
}