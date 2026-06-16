# Имя файла: main.py
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.card import MDCard
from kivymd.uix.scrollview import MDScrollView
from kivy.clock import Clock
from kivy.utils import platform
from kivy.metrics import dp

import math
import random
import logging
import os
import sys
import json
import struct
import time
from pathlib import Path
from collections import deque

# ── Логирование в файл на Android ──
def _setup_file_logging():
    if platform == "android":
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            log_dir_obj = activity.getExternalFilesDir(None) if activity else None
            if log_dir_obj is None and activity is not None:
                log_dir_obj = activity.getFilesDir()
            log_dir = log_dir_obj.getAbsolutePath()
        except Exception as exc:  # noqa: BLE001
            logging.basicConfig(level=logging.DEBUG)
            logging.getLogger("aegis").warning("File logging disabled: %s", exc)
            return None
    else:
        log_dir = "/tmp"

    try:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "aegis_debug.log")
        file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.root.addHandler(file_handler)
        logging.root.setLevel(logging.DEBUG)
        return log_path
    except Exception as exc:  # noqa: BLE001
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("aegis").warning("File logging disabled: %s", exc)
        return None


log_path = _setup_file_logging()

log = logging.getLogger("aegis")
log.info(f"=== AegisNeuro started === platform={platform} log_path={log_path}")

# Импортируем ядра из пакета aegis
from aegis.core import AegisRLBrain, StormPredictor, WatchDataBuffer
from aegis.update_checker import check_for_update
from aegis_audio_engine import AegisAudioEngine

APP_VERSION = "1.0.0"


# ── Multidex classloader helper ──
# Custom classes in org.aegisneuro.aegisneuro live in secondary DEX files
# (classes4.dex etc.) that the default system ClassLoader doesn't know about.
# We must use the app's PathClassLoader (obtained via the Activity) to resolve them.

HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_CHAR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


class BLEHeartRateScanner:
    """Сканер BLE-устройств, транслирующих Heart Rate Service (0x180D).

    Работает через pyjnius (Android BLE API). Поддерживает ЛЮБЫЕ устройства,
    рекламующие HR Service — Polar H10, нагрудные датчики, фитнес-браслеты,
    смарт-часы и т.д.
    """

    def __init__(self):
        self.is_scanning = False
        self.is_connected = False
        self.connected_device_name = None
        self.connected_device_address = None
        self.current_heart_rate = 0
        self.rr_intervals = deque(maxlen=200)
        self._scan_results = []  # (name, address, has_hr_service, is_watch)
        self._bluetooth_adapter = None
        self._bluetooth_gatt = None
        self._bluetooth_manager = None
        self._hr_callback = None
        self._scan_callback = None
        self._gatt_callback = None
        self._activity = None
        self._initialized = False
        self._watch_keywords = [
            "watch", "galaxy watch", "gear", "wear", "huawei watch",
            "ticwatch", "fossil watch", "amazfit", "gtr", "gts",
        ]

    def _init_android_ble(self):
        """Инициализация Android BLE API через pyjnius."""
        if self._initialized:
            return True
        if platform != "android":
            log.warning("BLE: не Android — сканирование недоступно")
            return False
        try:
            from jnius import autoclass, cast

            self._autoclass = autoclass
            self._cast = cast

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self._activity = PythonActivity.mActivity
            if not self._activity:
                log.error("BLE: Activity недоступна")
                return False

            self._bluetooth_manager = self._activity.getSystemService("bluetooth")
            if not self._bluetooth_manager:
                log.error("BLE: BluetoothManager недоступен")
                return False

            self._BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            self._BluetoothGatt = autoclass("android.bluetooth.BluetoothGatt")
            self._BluetoothGattCallback = autoclass("android.bluetooth.BluetoothGattCallback")
            self._BluetoothProfile = autoclass("android.bluetooth.BluetoothProfile")
            self._BluetoothDevice = autoclass("android.bluetooth.BluetoothDevice")
            self._ParcelUuid = autoclass("android.os.ParcelUuid")
            self._UUID = autoclass("java.util.UUID")
            self._ScanResult = autoclass("android.bluetooth.le.ScanResult")
            self._ScanSettings = autoclass("android.bluetooth.le.ScanSettings")
            self._ScanFilter = autoclass("android.bluetooth.le.ScanFilter")
            self._BluetoothLeScanner = autoclass("android.bluetooth.le.BluetoothLeScanner")
            self._Handler = autoclass("android.os.Handler")
            self._Looper = autoclass("android.os.Looper")

            adapter = self._bluetooth_manager.getAdapter()
            if not adapter or not adapter.isEnabled():
                log.error("BLE: Bluetooth адаптер выключен")
                return False

            self._bluetooth_adapter = adapter
            self._initialized = True
            log.info("BLE: Android BLE API инициализирован")
            return True
        except Exception as exc:
            log.error(f"BLE: ошибка инициализации: {exc}")
            return False

    def _is_watch_device(self, name):
        """Определяет, является ли устройство смарт-часами по имени."""
        if not name:
            return False
        name_lower = name.lower()
        for kw in self._watch_keywords:
            if kw in name_lower:
                return True
        return False

    def start_scan(self, timeout_ms=10000):
        """Запускает BLE-сканирование на timeout_ms миллисекунд.

        Возвращает dict:
          status: 'found_hr' | 'watch_no_hr' | 'nothing' | 'bluetooth_off' | 'error'
          devices: список найденных устройств [{name, address, has_hr_service, is_watch}]
          message: человекочитаемое описание
        """
        self._scan_results = []
        if not self._init_android_ble():
            return {
                "status": "bluetooth_off",
                "devices": [],
                "message": "Bluetooth недоступен. Включите Bluetooth и повторите.",
            }

        try:
            return self._android_scan(timeout_ms)
        except Exception as exc:
            log.error(f"BLE scan error: {exc}")
            return {
                "status": "error",
                "devices": [],
                "message": f"Ошибка сканирования: {exc}",
            }

    def _extract_hr_devices(self, callback):
        """Извлекает устройства с HR Service из результатов AegisScanCallback."""
        results = []
        java_results = callback.getResults()
        if java_results is None:
            return results
        seen_addrs = set()
        for result in java_results:
            device = result.getDevice()
            name = device.getName() or ""
            address = device.getAddress()
            if address in seen_addrs:
                continue
            scan_record = result.getScanRecord()
            has_hr_service = False
            if scan_record:
                service_uuids = scan_record.getServiceUuids()
                if service_uuids:
                    for pu in service_uuids:
                        if pu.getUuid().toString() == HR_SERVICE_UUID:
                            has_hr_service = True
                            break
            is_watch = self._is_watch_device(name)
            if has_hr_service:
                seen_addrs.add(address)
                results.append({
                    "name": name,
                    "address": address,
                    "has_hr_service": has_hr_service,
                    "is_watch": is_watch,
                })
        return results

    def _extract_watch_devices(self, callback):
        """Извлекает часы без HR Service из результатов AegisScanCallback."""
        results = []
        java_results = callback.getResults()
        if java_results is None:
            return results
        seen_addrs = set()
        for result in java_results:
            device = result.getDevice()
            name = device.getName() or ""
            address = device.getAddress()
            if address in seen_addrs:
                continue
            seen_addrs.add(address)
            scan_record = result.getScanRecord()
            has_hr_service = False
            if scan_record:
                service_uuids = scan_record.getServiceUuids()
                if service_uuids:
                    for pu in service_uuids:
                        if pu.getUuid().toString() == HR_SERVICE_UUID:
                            has_hr_service = True
                            break
            is_watch = self._is_watch_device(name)
            if is_watch and not has_hr_service:
                results.append({
                    "name": name,
                    "address": address,
                    "has_hr_service": has_hr_service,
                    "is_watch": is_watch,
                })
        return results

    def _extract_all_devices(self, callback):
        """Извлекает все устройства из результатов AegisScanCallback."""
        results = []
        java_results = callback.getResults()
        if java_results is None:
            return results
        seen_addrs = set()
        for result in java_results:
            device = result.getDevice()
            name = device.getName() or ""
            address = device.getAddress()
            if address in seen_addrs:
                continue
            seen_addrs.add(address)
            scan_record = result.getScanRecord()
            has_hr_service = False
            if scan_record:
                service_uuids = scan_record.getServiceUuids()
                if service_uuids:
                    for pu in service_uuids:
                        if pu.getUuid().toString() == HR_SERVICE_UUID:
                            has_hr_service = True
                            break
            is_watch = self._is_watch_device(name)
            results.append({
                "name": name,
                "address": address,
                "has_hr_service": has_hr_service,
                "is_watch": is_watch,
            })
        return results

    def _android_scan(self, timeout_ms=10000):
        """Реальное Android BLE-сканирование через pyjnius."""
        from jnius import autoclass, cast, PythonJavaClass, java_method

        scanner = self._bluetooth_adapter.getBluetoothLeScanner()
        if not scanner:
            return {"status": "bluetooth_off", "devices": [], "message": "BLE сканер недоступен"}

        # Фильтр по Heart Rate Service UUID
        hr_uuid = self._UUID.fromString(HR_SERVICE_UUID)
        parcel_uuid = self._ParcelUuid.fromString(HR_SERVICE_UUID)

        # ScanFilter для HR Service
        scan_filter_builder = autoclass("android.bluetooth.le.ScanFilter$Builder")()
        scan_filter_builder.setServiceUuid(parcel_uuid)
        scan_filter = scan_filter_builder.build()

        # ScanSettings
        settings_builder = autoclass("android.bluetooth.le.ScanSettings$Builder")()
        settings_builder.setScanMode(autoclass("android.bluetooth.le.ScanSettings").SCAN_MODE_LOW_LATENCY)
        settings = settings_builder.build()

        # Java-обёртки ScanCallback (вместо PythonJavaClass, который не работает
        # с абстрактными классами android/bluetooth/le/ScanCallback)
        AegisScanCallback = autoclass("org.aegisneuro.aegisneuro.AegisScanCallback")

        # Сначала запускаем отфильтрованное сканирование (HR Service)
        hr_callback = AegisScanCallback()
        scanner.startScan([scan_filter], settings, hr_callback)

        # И общее сканирование (для обнаружения часов без HR)
        general_settings_builder = autoclass("android.bluetooth.le.ScanSettings$Builder")()
        general_settings_builder.setScanMode(autoclass("android.bluetooth.le.ScanSettings").SCAN_MODE_LOW_LATENCY)
        general_settings = general_settings_builder.build()
        general_callback = AegisScanCallback()
        scanner.startScan(None, general_settings, general_callback)

        # Ждём timeout_ms
        handler = self._Handler(self._Looper.getMainLooper())
        import threading

        scan_done = threading.Event()

        def stop_scan():
            try:
                scanner.stopScan(hr_callback)
            except Exception:
                pass
            try:
                scanner.stopScan(general_callback)
            except Exception:
                pass
            scan_done.set()

        # Используем Clock для ожидания, т.к. это Kivy-поток
        # На Android используем Handler.postDelayed
        runnable_class = autoclass("java.lang.Runnable")

        class StopRunnable(PythonJavaClass):
            __javainterfaces__ = ["java/lang/Runnable"]
            def __init__(self):
                super().__init__()
            def run(self):
                stop_scan()

        stop_runnable = StopRunnable()
        handler.postDelayed(stop_runnable, timeout_ms)

        # Блокируем на время сканирования (но в отдельном потоке, чтобы не заморозить UI)
        scan_done.wait(timeout_ms / 1000.0 + 2)

        # Объединяем результаты
        all_found = {}
        for dev in self._extract_hr_devices(hr_callback):
            all_found[dev["address"]] = dev
        for dev in self._extract_all_devices(general_callback):
            if dev["address"] not in all_found:
                all_found[dev["address"]] = dev

        hr_devices = [d for d in all_found.values() if d["has_hr_service"]]
        watch_devices_no_hr = [d for d in all_found.values() if d["is_watch"] and not d["has_hr_service"]]

        self._scan_results = list(all_found.values())

        if hr_devices:
            best = hr_devices[0]
            return {
                "status": "found_hr",
                "devices": hr_devices,
                "best_device": best,
                "message": f"Найден датчик ЧСС: {best['name'] or best['address']}",
            }
        elif watch_devices_no_hr:
            watch = watch_devices_no_hr[0]
            return {
                "status": "watch_no_hr",
                "devices": watch_devices_no_hr,
                "best_device": watch,
                "message": "Часы найдены, но не транслируют ЧСС",
            }
        else:
            return {
                "status": "nothing",
                "devices": [],
                "message": "BLE-устройства с ЧСС не найдены",
            }

    def connect_and_read_hr(self, device_info):
        """Подключается к BLE-устройству и подписывается на Heart Rate Measurement.

        device_info: dict с 'address'
        Возвращает True если подключение успешно.
        """
        if not self._initialized:
            return False

        try:
            return self._android_connect(device_info)
        except Exception as exc:
            log.error(f"BLE connect error: {exc}")
            return False

    def _android_connect(self, device_info):
        """Реальное Android BLE-подключение через pyjnius."""
        from jnius import autoclass, cast

        address = device_info["address"]
        device = self._bluetooth_adapter.getRemoteDevice(address)
        if not device:
            log.error(f"BLE: устройство {address} не найдено")
            return False

        # Java-обёртка GattCallback (вместо PythonJavaClass, который не работает
        # с абстрактными классами android/bluetooth/BluetoothGattCallback)
        AegisGattCallback = autoclass("org.aegisneuro.aegisneuro.AegisGattCallback")
        gatt_callback = AegisGattCallback()

        # Подключаемся (autoConnect=False для быстрого подключения)
        self._bluetooth_gatt = device.connectGatt(self._activity, False, gatt_callback)

        self.connected_device_name = device_info.get("name", "")
        self.connected_device_address = address
        self.is_connected = True
        self._gatt_callback = gatt_callback

        log.info(f"BLE: подключение к {device_info.get('name', address)}...")
        return True

    def disconnect(self):
        """Отключается от BLE-устройства."""
        if self._bluetooth_gatt:
            try:
                self._bluetooth_gatt.disconnect()
                self._bluetooth_gatt.close()
            except Exception as exc:
                log.warning(f"BLE disconnect error: {exc}")
            finally:
                self._bluetooth_gatt = None
        self.is_connected = False
        self.connected_device_name = None
        self.connected_device_address = None
        self.current_heart_rate = 0

    def get_status(self):
        """Возвращает текущий статус BLE-подключения."""
        return {
            "is_connected": self.is_connected,
            "device_name": self.connected_device_name,
            "heart_rate": self.current_heart_rate,
            "rr_count": len(self.rr_intervals),
            "rr_intervals": list(self.rr_intervals),
        }


# ==============================================================================
# FOREGROUND SERVICE — приложение работает в фоне
# ==============================================================================

def start_foreground_service():
    """Запускает Android Foreground Service для работы в фоне."""
    if platform != "android":
        return

    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        if not activity:
            return

        Intent = autoclass("android.content.Intent")
        Context = autoclass("android.content.Context")
        Notification = autoclass("android.app.Notification")
        NotificationChannel = autoclass("android.app.NotificationChannel")
        NotificationManager = autoclass("android.app.NotificationManager")
        PendingIntent = autoclass("android.app.PendingIntent")
        BuildVERSION = autoclass("android.os.Build$VERSION")
        Integer = autoclass("java.lang.Integer")

        CHANNEL_ID = "aegisneuro_foreground"
        NOTIFICATION_ID = 1001

        # Создаём NotificationChannel (Android 8+)
        if BuildVERSION.SDK_INT >= 26:
            channel_name = "AegisNeuro Сервис"
            channel_desc = "Мониторинг сердечного ритма и нейрорегуляция"
            importance = Integer.valueOf(NotificationManager.IMPORTANCE_LOW)
            channel = NotificationChannel(CHANNEL_ID, channel_name, importance)
            channel.setDescription(channel_desc)
            channel.setShowBadge(False)

            nm = activity.getSystemService(Context.NOTIFICATION_SERVICE)
            if nm:
                nm.createNotificationChannel(channel)

        # Строим уведомление
        NotificationBuilder = autoclass("android.app.Notification$Builder")

        if BuildVERSION.SDK_INT >= 26:
            builder = NotificationBuilder(activity, CHANNEL_ID)
        else:
            builder = NotificationBuilder(activity)

        builder.setSmallIcon(autoclass("org.aegisneuro.aegisneuro.R").drawable.icon)
        builder.setContentTitle("AegisNeuro работает")
        builder.setContentText("Мониторинг ЧСС и нейрорегуляция активны")
        builder.setOngoing(True)
        builder.setPriority(Notification.PRIORITY_LOW)

        # PendingIntent для возврата в приложение при нажатии
        intent = Intent(activity, PythonActivity)
        intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        pi_flags = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        pending = PendingIntent.getActivity(activity, 0, intent, pi_flags)
        builder.setContentIntent(pending)

        notification = builder.build()

        # Запускаем как Foreground Service через p4a service API
        try:
            service_class = autoclass("org.aegisneuro.aegisneuro.ServiceAegisNeuro")
            activity.startForegroundService(Intent(activity, service_class))

            # Альтернативно, если p4a service не определён, используем сервис Kivy
            try:
                PythonService = autoclass("org.kivy.android.PythonService")
                PythonService.start("AegisNeuro", "Мониторинг ЧСС активен")
            except Exception:
                pass

        except Exception as exc:
            log.warning(f"Foreground service start error: {exc}")
            # Запускаем сервис через Kivy's PythonService как фоллбэк
            try:
                PythonService = autoclass("org.kivy.android.PythonService")
                PythonService.start("AegisNeuro", "Мониторинг ЧСС активен")
            except Exception as exc2:
                log.warning(f"PythonService fallback error: {exc2}")

        log.info("Foreground Service запущен")

    except Exception as exc:
        log.error(f"Foreground Service initialization error: {exc}")


def stop_foreground_service():
    """Останавливает Foreground Service."""
    if platform != "android":
        return
    try:
        from jnius import autoclass

        try:
            PythonService = autoclass("org.kivy.android.PythonService")
            PythonService.stop()
        except Exception:
            pass

        try:
            service_class = autoclass("org.aegisneuro.aegisneuro.ServiceAegisNeuro")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            if activity:
                Intent = autoclass("android.content.Intent")
                activity.stopService(Intent(activity, service_class))
        except Exception:
            pass

        log.info("Foreground Service остановлен")
    except Exception as exc:
        log.error(f"Foreground Service stop error: {exc}")


# ==============================================================================
# МОСТ ДЛЯ ДАННЫХ GALAXY WATCH (оставлено для обратной совместимости)
# ==============================================================================
class WatchDataBridge:
    """Канал данных Wear OS / Galaxy Watch.

    v42: принимает JSONL-пакеты от Android/Wear receiver.
    """

    def __init__(self):
        self.buffer = WatchDataBuffer()
        self.inbox_path = self._resolve_inbox_path()
        self._read_offset = 0

    def latest_rr_intervals(self):
        self.refresh()
        return self.buffer.latest_rr_intervals()

    def status(self):
        self.refresh()
        return self.buffer.summary()

    def refresh(self):
        if self.inbox_path is None or not self.inbox_path.exists():
            return

        try:
            with self.inbox_path.open("r", encoding="utf-8") as f:
                f.seek(self._read_offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    self.ingest_payload(json.loads(line))
                self._read_offset = f.tell()
        except Exception as exc:  # noqa: BLE001
            log.warning("Watch inbox read failed: %s", exc)

    def ingest_payload(self, payload):
        accepted = self.buffer.ingest(payload)
        if accepted:
            log.info("Watch packet accepted: %s RR intervals", accepted)

    def _resolve_inbox_path(self):
        try:
            if platform == "android":
                from jnius import autoclass

                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                activity = PythonActivity.mActivity
                root = activity.getExternalFilesDir(None) if activity else None
                if root is None and activity is not None:
                    root = activity.getFilesDir()
                if root is not None:
                    return Path(root.getAbsolutePath()) / "watch_payloads.jsonl"
            return Path("data") / "watch_payloads.jsonl"
        except Exception as exc:  # noqa: BLE001
            log.warning("Watch inbox path unavailable: %s", exc)
            return None


# ==============================================================================
# МОНОЛИТНЫЙ ИНТЕРФЕЙС И КОНТУР БИОЛОГИЧЕСКОЙ ОБРАТНОЙ СВЯЗИ
# ==============================================================================
class AegisNeuroMobileScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.ai_brain = AegisRLBrain()
        self.audio_engine = AegisAudioEngine()
        self.watch_bridge = WatchDataBridge()
        self.predictor = StormPredictor()
        self.ble_scanner = BLEHeartRateScanner()

        self.current_stress = 120.0
        self.current_rmssd = 35.0
        self.old_stress = self.current_stress
        self.old_rmssd = self.current_rmssd
        self.current_action_idx = 0
        self.active_frequency = 8.0

        self.gender_profile = "male"
        self.scan_timer = 0
        self.is_scanning = False
        self.current_bpm = 0
        self.storm_prob = 0

        self.audio_engine.start_tone()
        self.build_ui()

    def build_ui(self):
        # ── Корневой ScrollView для предотвращения обрезки на маленьких экранах ──
        scroll = MDScrollView()

        content = MDBoxLayout(
            orientation='vertical',
            padding=dp(16),
            spacing=dp(12),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter('height'))

        # ── 1. Карточка заголовка ──
        title_card = MDCard(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(4),
            size_hint_y=None,
            radius=[dp(12)],
            md_bg_color=[0.06, 0.10, 0.14, 1],
            elevation=2,
        )
        title_card.bind(minimum_height=title_card.setter('height'))

        self.title_label = MDLabel(
            text="AEGISNEURO",
            halign="center",
            font_style="H4",
            theme_text_color="Custom",
            text_color=[0, 1, 0.8, 1],
            size_hint_y=None,
            height=dp(44),
        )
        title_label_sub = MDLabel(
            text=f"Система нейрорегуляции v{APP_VERSION}",
            halign="center",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.55, 0.65, 0.70, 1],
            size_hint_y=None,
            height=dp(24),
        )
        title_card.add_widget(self.title_label)
        title_card.add_widget(title_label_sub)
        content.add_widget(title_card)

        # ── Баннер обновления (скрыт по умолчанию) ──
        self.update_banner = MDCard(
            orientation='horizontal',
            padding=[dp(16), dp(10)],
            spacing=dp(12),
            size_hint_y=None,
            radius=[dp(12)],
            md_bg_color=[0.12, 0.18, 0.08, 1],
            elevation=2,
            opacity=0,
            height=0,
        )
        self.update_banner_label = MDLabel(
            text="",
            halign="left",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=[0.6, 0.9, 0.4, 1],
            size_hint_x=0.7,
        )
        self.update_download_btn = MDRaisedButton(
            text="Обновить",
            md_bg_color=[0.2, 0.7, 0.3, 1],
            size_hint_x=0.3,
            on_release=self._open_update_url,
        )
        self.update_banner.add_widget(self.update_banner_label)
        self.update_banner.add_widget(self.update_download_btn)
        content.add_widget(self.update_banner)
        self._update_url = None

        # ── 2. Карточка статуса ──
        self.status_card = MDCard(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(6),
            size_hint_y=None,
            radius=[dp(12)],
            md_bg_color=[0.08, 0.12, 0.18, 1],
            elevation=2,
        )
        self.status_card.bind(minimum_height=self.status_card.setter('height'))

        self.status_label = MDLabel(
            text="Готов к подключению",
            halign="center",
            font_style="H6",
            theme_text_color="Custom",
            text_color=[0.85, 0.92, 0.96, 1],
            size_hint_y=None,
            height=dp(32),
        )
        self.status_label.bind(
            width=lambda inst, w: setattr(inst, 'text_size', (w, None))
        )
        self.status_label.bind(
            texture_size=lambda inst, ts: setattr(inst, 'height', max(dp(32), ts[1]))
        )

        self.status_detail_label = MDLabel(
            text="Подключите датчик ЧСС через Bluetooth",
            halign="center",
            font_style="Body1",
            theme_text_color="Custom",
            text_color=[0.55, 0.65, 0.70, 1],
            size_hint_y=None,
            height=dp(24),
        )
        self.status_detail_label.bind(
            width=lambda inst, w: setattr(inst, 'text_size', (w, None))
        )
        self.status_detail_label.bind(
            texture_size=lambda inst, ts: setattr(inst, 'height', max(dp(24), ts[1]))
        )

        self.status_card.add_widget(self.status_label)
        self.status_card.add_widget(self.status_detail_label)
        content.add_widget(self.status_card)

        # ── 3. Селектор профиля ──
        profile_card = MDCard(
            orientation='vertical',
            padding=dp(16),
            spacing=dp(10),
            size_hint_y=None,
            radius=[dp(12)],
            md_bg_color=[0.07, 0.09, 0.13, 1],
            elevation=1,
        )
        profile_card.bind(minimum_height=profile_card.setter('height'))

        profile_title = MDLabel(
            text="Профиль пользователя",
            halign="left",
            font_style="Subtitle2",
            theme_text_color="Custom",
            text_color=[0.6, 0.7, 0.75, 1],
            size_hint_y=None,
            height=dp(28),
        )
        profile_card.add_widget(profile_title)

        gender_row = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(48),
            spacing=dp(12),
        )
        self.male_btn = MDRaisedButton(
            text="♂ Мужской",
            md_bg_color=[0, 0.6, 0.8, 1],
            size_hint_x=0.5,
            on_release=self.set_male_profile,
        )
        try:
            self.female_btn = MDFlatButton(
                text="♀ Женский",
                theme_text_color="Custom",
                text_color=[1, 1, 1, 0.6],
                size_hint_x=0.5,
                on_release=self.set_female_profile,
            )
        except Exception:
            self.female_btn = MDRaisedButton(
                text="♀ Женский",
                theme_text_color="Custom",
                text_color=[1, 1, 1, 0.6],
                size_hint_x=0.5,
                on_release=self.set_female_profile,
            )
        gender_row.add_widget(self.male_btn)
        gender_row.add_widget(self.female_btn)
        profile_card.add_widget(gender_row)
        content.add_widget(profile_card)

        # ── 4. Карточка метрик ──
        self.metrics_card = MDCard(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(10),
            size_hint_y=None,
            radius=[dp(12)],
            md_bg_color=[0.06, 0.08, 0.12, 1],
            elevation=2,
        )
        self.metrics_card.bind(minimum_height=self.metrics_card.setter('height'))

        metrics_title = MDLabel(
            text="Показатели",
            halign="center",
            font_style="Subtitle2",
            theme_text_color="Custom",
            text_color=[0.5, 0.6, 0.65, 1],
            size_hint_y=None,
            height=dp(28),
        )
        self.metrics_card.add_widget(metrics_title)

        # Строка метрик: два значения рядом
        metrics_row = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            spacing=dp(16),
        )
        metrics_row.bind(minimum_height=metrics_row.setter('height'))

        # Левая колонка — Индекс Стресса
        stress_col = MDBoxLayout(
            orientation='vertical',
            size_hint_x=0.5,
            padding=[0, dp(8), 0, dp(8)],
            spacing=dp(4),
            size_hint_y=None,
        )
        stress_col.bind(minimum_height=stress_col.setter('height'))
        self.stress_value_label = MDLabel(
            text="--",
            halign="center",
            font_style="H4",
            theme_text_color="Custom",
            text_color=[1, 0.6, 0.4, 1],
            size_hint_y=None,
            height=dp(48),
        )
        stress_unit_label = MDLabel(
            text="у.е.",
            halign="center",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.5, 0.55, 0.6, 1],
            size_hint_y=None,
            height=dp(20),
        )
        stress_name_label = MDLabel(
            text="Индекс Стресса",
            halign="center",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=[0.7, 0.75, 0.8, 1],
            size_hint_y=None,
            height=dp(24),
        )
        stress_col.add_widget(self.stress_value_label)
        stress_col.add_widget(stress_unit_label)
        stress_col.add_widget(stress_name_label)

        # Правая колонка — RMSSD
        rmssd_col = MDBoxLayout(
            orientation='vertical',
            size_hint_x=0.5,
            padding=[0, dp(8), 0, dp(8)],
            spacing=dp(4),
            size_hint_y=None,
        )
        rmssd_col.bind(minimum_height=rmssd_col.setter('height'))
        self.rmssd_value_label = MDLabel(
            text="--",
            halign="center",
            font_style="H4",
            theme_text_color="Custom",
            text_color=[0.3, 0.85, 0.6, 1],
            size_hint_y=None,
            height=dp(48),
        )
        rmssd_unit_label = MDLabel(
            text="ms",
            halign="center",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.5, 0.55, 0.6, 1],
            size_hint_y=None,
            height=dp(20),
        )
        rmssd_name_label = MDLabel(
            text="RMSSD (Парасимпатика)",
            halign="center",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=[0.7, 0.75, 0.8, 1],
            size_hint_y=None,
            height=dp(24),
        )
        rmssd_col.add_widget(self.rmssd_value_label)
        rmssd_col.add_widget(rmssd_unit_label)
        rmssd_col.add_widget(rmssd_name_label)

        # Вторая строка метрик: три значения рядом
        metrics_row_2 = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            spacing=dp(12),
        )
        metrics_row_2.bind(minimum_height=metrics_row_2.setter('height'))

        # Левая колонка второй строки — Пульс (ЧСС)
        hr_col = MDBoxLayout(
            orientation='vertical',
            size_hint_x=0.33,
            padding=[0, dp(8), 0, dp(8)],
            spacing=dp(4),
            size_hint_y=None,
        )
        hr_col.bind(minimum_height=hr_col.setter('height'))
        self.hr_value_label = MDLabel(
            text="--",
            halign="center",
            font_style="H5",
            theme_text_color="Custom",
            text_color=[0, 0.8, 0.9, 1],
            size_hint_y=None,
            height=dp(40),
        )
        hr_unit_label = MDLabel(
            text="bpm",
            halign="center",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.5, 0.55, 0.6, 1],
            size_hint_y=None,
            height=dp(18),
        )
        hr_name_label = MDLabel(
            text="Пульс (ЧСС)",
            halign="center",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=[0.7, 0.75, 0.8, 1],
            size_hint_y=None,
            height=dp(20),
        )
        hr_col.add_widget(self.hr_value_label)
        hr_col.add_widget(hr_unit_label)
        hr_col.add_widget(hr_name_label)

        # Средняя колонка второй строки — Частота ИИ
        freq_col = MDBoxLayout(
            orientation='vertical',
            size_hint_x=0.33,
            padding=[0, dp(8), 0, dp(8)],
            spacing=dp(4),
            size_hint_y=None,
        )
        freq_col.bind(minimum_height=freq_col.setter('height'))
        self.freq_value_label = MDLabel(
            text="--",
            halign="center",
            font_style="H5",
            theme_text_color="Custom",
            text_color=[0.7, 0.4, 0.9, 1],
            size_hint_y=None,
            height=dp(40),
        )
        freq_unit_label = MDLabel(
            text="Гц",
            halign="center",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.5, 0.55, 0.6, 1],
            size_hint_y=None,
            height=dp(18),
        )
        freq_name_label = MDLabel(
            text="Частота ИИ",
            halign="center",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=[0.7, 0.75, 0.8, 1],
            size_hint_y=None,
            height=dp(20),
        )
        freq_col.add_widget(self.freq_value_label)
        freq_col.add_widget(freq_unit_label)
        freq_col.add_widget(freq_name_label)

        # Правая колонка второй строки — Риск Шторма
        storm_col = MDBoxLayout(
            orientation='vertical',
            size_hint_x=0.34,
            padding=[0, dp(8), 0, dp(8)],
            spacing=dp(4),
            size_hint_y=None,
        )
        storm_col.bind(minimum_height=storm_col.setter('height'))
        self.storm_value_label = MDLabel(
            text="--",
            halign="center",
            font_style="H5",
            theme_text_color="Custom",
            text_color=[0.3, 0.85, 0.6, 1],
            size_hint_y=None,
            height=dp(40),
        )
        storm_unit_label = MDLabel(
            text="%",
            halign="center",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.5, 0.55, 0.6, 1],
            size_hint_y=None,
            height=dp(18),
        )
        storm_name_label = MDLabel(
            text="Риск Шторма",
            halign="center",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=[0.7, 0.75, 0.8, 1],
            size_hint_y=None,
            height=dp(20),
        )
        storm_col.add_widget(self.storm_value_label)
        storm_col.add_widget(storm_unit_label)
        storm_col.add_widget(storm_name_label)

        metrics_row_2.add_widget(hr_col)
        metrics_row_2.add_widget(freq_col)
        metrics_row_2.add_widget(storm_col)

        metrics_row.add_widget(stress_col)
        metrics_row.add_widget(rmssd_col)
        self.metrics_card.add_widget(metrics_row)
        self.metrics_card.add_widget(metrics_row_2)
        content.add_widget(self.metrics_card)

        # ── 5. Кнопка действия ──
        action_container = MDBoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(72),
            padding=[dp(8), dp(8), dp(8), dp(8)],
        )

        self.action_btn = MDRaisedButton(
            text="ПОДКЛЮЧИТЬ ДАТЧИК",
            pos_hint={"center_x": 0.5},
            md_bg_color=[0, 0.78, 0.35, 1],
            size_hint_x=1.0,
            size_hint_y=None,
            height=dp(52),
            on_release=self.start_ble_scan,
            font_style="Button",
        )
        action_container.add_widget(self.action_btn)
        content.add_widget(action_container)

        # ── Нижний отступ для скролла ──
        bottom_spacer = MDBoxLayout(size_hint_y=None, height=dp(24))
        content.add_widget(bottom_spacer)

        scroll.add_widget(content)
        self.add_widget(scroll)

        # ── Фоновые задачи ──
        Clock.schedule_interval(self.mobile_lifecycle_loop, 1.0)
        Clock.schedule_interval(self._update_ble_status, 1.0)
        Clock.schedule_once(self._check_for_update, 3.0)

    # ── Обновление цвета метрик в зависимости от значений ──
    def _update_metric_colors(self):
        stress = self.current_stress
        rmssd = self.current_rmssd

        # Стресс: зелёный (<150) → жёлтый (150–300) → красный (>300)
        if stress < 150:
            self.stress_value_label.text_color = [0.3, 0.85, 0.6, 1]
        elif stress < 300:
            self.stress_value_label.text_color = [1, 0.75, 0.2, 1]
        else:
            self.stress_value_label.text_color = [1, 0.35, 0.3, 1]

        # RMSSD: зелёный (>40) → жёлтый (20–40) → красный (<20)
        if rmssd > 40:
            self.rmssd_value_label.text_color = [0.3, 0.85, 0.6, 1]
        elif rmssd > 20:
            self.rmssd_value_label.text_color = [1, 0.75, 0.2, 1]
        else:
            self.rmssd_value_label.text_color = [1, 0.35, 0.3, 1]

        # Риск Шторма: зелёный (<40%) → жёлтый (40–70%) → красный (>=70%)
        if self.storm_prob < 40:
            self.storm_value_label.text_color = [0.3, 0.85, 0.6, 1]
        elif self.storm_prob < 70:
            self.storm_value_label.text_color = [1, 0.75, 0.2, 1]
        else:
            self.storm_value_label.text_color = [1, 0.35, 0.3, 1]

    def _update_ble_status(self, dt=None):
        """Обновляет статус BLE-подключения и отображает ЧСС в реальном времени."""
        ble_status = self.ble_scanner.get_status()

        if ble_status["is_connected"]:
            hr = ble_status["heart_rate"]
            if hr > 0:
                self.current_bpm = hr
                self.hr_value_label.text = str(hr)

                # Если есть RR-интервалы от BLE, отправляем в буфер
                rr_data = ble_status["rr_intervals"]
                if rr_data:
                    # Инжектим в WatchDataBuffer для совместимости с StormPredictor
                    payload = {
                        "type": "ble_hr",
                        "heart_rate": hr,
                        "rr_intervals_ms": rr_data[-10:],  # последние 10
                    }
                    self.watch_bridge.ingest_payload(payload)

                # Обновляем статус только если не идёт замер
                if not self.is_scanning:
                    self.status_card.md_bg_color = [0.08, 0.16, 0.1, 1]
                    device_name = ble_status["device_name"] or "Датчик ЧСС"
                    rr_count = len(self.ble_scanner.rr_intervals)
                    self.status_label.text = f"Подключено: {device_name}"
                    self.status_detail_label.text = f"ЧСС: {hr} bpm | R-R: {rr_count} интервалов"
            elif not self.is_scanning:
                self.status_detail_label.text = "Ожидание данных ЧСС..."
        else:
            # Проверяем Watch bridge как фоллбэк (Wear OS)
            if not self.is_scanning:
                self._refresh_watch_fallback()

    def _refresh_watch_fallback(self):
        """Проверяет Wear OS watch inbox как фоллбэк."""
        watch_status = self.watch_bridge.status()
        rr_count = watch_status["rr_count"]
        bpm = watch_status["heart_rate_bpm"]
        connected = watch_status["connected"]

        if rr_count >= 10:
            self.status_card.md_bg_color = [0.08, 0.16, 0.1, 1]
            self.status_label.text = "Часы подключены"
            bpm_text = f"ЧСС: {bpm} bpm" if bpm else "ЧСС: ожидаем"
            self.status_detail_label.text = f"{bpm_text}\nR-R: {rr_count} интервалов"
        elif connected:
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = "Часы подключены"
            bpm_text = f"ЧСС: {bpm} bpm" if bpm else "ЧСС получаем"
            self.status_detail_label.text = f"{bpm_text}\nДля HRV нужно минимум 10 IBI, сейчас: {rr_count}"

    def start_ble_scan(self, *args):
        """Запускает BLE-сканирование для поиска датчика ЧСС."""
        if self.is_scanning:
            return

        self.is_scanning = True
        self.action_btn.disabled = True
        self.action_btn.text = "СКАНИРОВАНИЕ..."
        self.status_card.md_bg_color = [0.06, 0.14, 0.22, 1]
        self.status_label.text = "Поиск датчика ЧСС..."
        self.status_detail_label.text = "Сканирование Bluetooth..."

        # Запускаем сканирование в отдельном потоке, чтобы не блокировать UI
        import threading

        def _scan_thread():
            result = self.ble_scanner.start_scan(timeout_ms=10000)
            Clock.schedule_once(lambda dt: self._on_ble_scan_result(result))

        t = threading.Thread(target=_scan_thread, daemon=True)
        t.start()

    def _on_ble_scan_result(self, result):
        """Обрабатывает результат BLE-сканирования."""
        self.is_scanning = False
        self.action_btn.disabled = False
        self.action_btn.md_bg_color = [0, 0.78, 0.35, 1]

        status = result["status"]

        if status == "found_hr":
            # Найдено устройство с HR Service — подключаемся автоматически
            best = result.get("best_device", result["devices"][0] if result["devices"] else None)
            if best:
                self.action_btn.text = "ПОДКЛЮЧЕНИЕ..."
                self.status_label.text = f"Найден: {best.get('name', best['address'])}"
                self.status_detail_label.text = "Подключение к датчику ЧСС..."

                import threading

                def _connect_thread():
                    success = self.ble_scanner.connect_and_read_hr(best)
                    Clock.schedule_once(lambda dt: self._on_ble_connected(success, best))

                t = threading.Thread(target=_connect_thread, daemon=True)
                t.start()
            else:
                self.action_btn.text = "ПОДКЛЮЧИТЬ ДАТЧИК"
                self.status_label.text = "Ошибка подключения"
                self.status_detail_label.text = "Устройство не найдено"

        elif status == "watch_no_hr":
            # Часы найдены, но не транслируют HR
            watch = result.get("best_device", result["devices"][0] if result["devices"] else None)
            watch_name = watch.get("name", "Часы") if watch else "Часы"
            self.action_btn.text = "ПОДКЛЮЧИТЬ ДАТЧИК"
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = f"{watch_name} найдены"
            self.status_detail_label.text = (
                "Для работы нужно установить Heart for Bluetooth на ваши часы\n"
                "Установить: https://play.google.com/store/apps/details?id=com.easy.heart4bluetooth"
            )

        elif status == "nothing":
            # Ничего не найдено
            self.action_btn.text = "ПОДКЛЮЧИТЬ ДАТЧИК"
            self.status_card.md_bg_color = [0.35, 0.12, 0.12, 1]
            self.status_label.text = "Датчик ЧСС не найден"
            self.status_detail_label.text = (
                "Без датчика приложение не работает. "
                "Включите Bluetooth и подключите устройство.\n\n"
                "Рекомендуемые устройства:\n"
                "• Polar H10 — профессиональный нагрудный датчик\n"
                "• Xiaomi Smart Band 8 — фитнес-браслет с ЧСС\n"
                "• Galaxy Watch 4/5/6 — смарт-часы с датчиком ЧСС"
            )

        elif status == "bluetooth_off":
            self.action_btn.text = "ПОДКЛЮЧИТЬ ДАТЧИК"
            self.status_card.md_bg_color = [0.35, 0.12, 0.12, 1]
            self.status_label.text = "Bluetooth выключен"
            self.status_detail_label.text = (
                "Без датчика приложение не работает. "
                "Включите Bluetooth и подключите устройство.\n\n"
                "Рекомендуемые устройства:\n"
                "• Polar H10 — профессиональный нагрудный датчик\n"
                "• Xiaomi Smart Band 8 — фитнес-браслет с ЧСС\n"
                "• Galaxy Watch 4/5/6 — смарт-часы с датчиком ЧСС"
            )

        else:
            # error
            self.action_btn.text = "ПОДКЛЮЧИТЬ ДАТЧИК"
            self.status_card.md_bg_color = [0.35, 0.12, 0.12, 1]
            self.status_label.text = "Ошибка сканирования"
            self.status_detail_label.text = result.get("message", "Не удалось выполнить сканирование BLE")

    def _on_ble_connected(self, success, device_info):
        """Обрабатывает результат подключения к BLE-устройству."""
        if success:
            device_name = device_info.get("name", device_info.get("address", "Датчик"))
            self.status_card.md_bg_color = [0.08, 0.16, 0.1, 1]
            self.status_label.text = f"Подключено: {device_name}"
            self.status_detail_label.text = "Ожидание данных ЧСС..."
            self.action_btn.text = "НАЧАТЬ ЗАМЕР"

            # Меняем действие кнопки на начало замера
            self.action_btn.unbind(on_release=self.start_ble_scan)
            self.action_btn.bind(on_release=self.start_measurement)

            # Запускаем Foreground Service
            start_foreground_service()
        else:
            self.status_card.md_bg_color = [0.35, 0.12, 0.12, 1]
            self.status_label.text = "Ошибка подключения"
            self.status_detail_label.text = f"Не удалось подключиться к {device_info.get('name', device_info.get('address', 'устройству'))}"
            self.action_btn.text = "ПОДКЛЮЧИТЬ ДАТЧИК"

    def start_measurement(self, *args):
        """Начинает замер HRV с данными от BLE-датчика."""
        if self.is_scanning:
            return

        # Проверяем, достаточно ли данных
        ble_status = self.ble_scanner.get_status()
        rr_from_ble = ble_status["rr_intervals"]
        rr_from_watch = self.watch_bridge.latest_rr_intervals()

        # Объединяем RR-интервалы из обоих источников
        all_rr = list(rr_from_ble) if rr_from_ble else []
        if not all_rr:
            all_rr = rr_from_watch

        if len(all_rr) < 10:
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = "Недостаточно данных"
            self.status_detail_label.text = f"Нужно минимум 10 R-R интервалов, сейчас: {len(all_rr)}. Подождите..."
            return

        self.scan_timer = 1
        self.is_scanning = True

        self.status_card.md_bg_color = [0.06, 0.14, 0.22, 1]
        self.status_label.text = "Идёт замер..."
        self.status_detail_label.text = "Анализируем данные сердечного ритма"

        self.action_btn.text = "ИДЁТ ЗАМЕР..."
        self.action_btn.disabled = True

    def on_measurement_complete(self):
        """Завершает замер и отображает результаты."""
        self.is_scanning = False

        self.action_btn.disabled = False
        self.action_btn.md_bg_color = [0, 0.78, 0.35, 1]
        self.action_btn.text = "ЗАМЕР"

        # Получаем RR-интервалы
        ble_status = self.ble_scanner.get_status()
        rr_from_ble = ble_status["rr_intervals"]
        rr_from_watch = self.watch_bridge.latest_rr_intervals()

        rr_data = list(rr_from_ble) if rr_from_ble else rr_from_watch

        if len(rr_data) < 10:
            self.status_card.md_bg_color = [0.35, 0.12, 0.12, 1]
            self.status_label.text = "⚠ Замер не удался"
            self.status_detail_label.text = "Недостаточно данных. Повторите замер."
            return

        # Анализ через StormPredictor.analyze()
        prediction = self.predictor.analyze(rr_data)

        if prediction["status"] == "INSUFFICIENT_DATA":
            self.status_card.md_bg_color = [0.35, 0.12, 0.12, 1]
            self.status_label.text = "⚠ Замер не удался"
            self.status_detail_label.text = "Недостаточно данных. Повторите замер."
            return

        self.current_rmssd = prediction["metrics"]["rmssd"]
        self.current_stress = prediction["metrics"]["stress_index"]
        self.storm_prob = prediction["storm_probability_pct"]

        # ОБУЧЕНИЕ ИИ
        rmssd_growth = self.current_rmssd - self.old_rmssd
        self.ai_brain.learn(
            old_stress=self.old_stress,
            action_idx=self.current_action_idx,
            new_stress=self.current_stress,
            rmssd_growth=rmssd_growth
        )
        self.ai_brain.save_profile()

        # ВЫБОР ЧАСТОТЫ
        self.active_frequency, self.current_action_idx, strategy_name = self.ai_brain.choose_frequency(self.current_stress)
        self.audio_engine.set_frequency(self.active_frequency)

        if prediction["status"] == "STORM_ALERT":
            self.status_card.md_bg_color = [0.4, 0.1, 0.1, 1]
            anomaly_text = prediction["triggers"][0] if prediction["triggers"] else "Хаос ЦНС"
            self.status_label.text = f"⚠ Угроза штурма ({prediction['storm_probability_pct']}%)"
            self.status_detail_label.text = f"{anomaly_text}\nИИ подает: {self.active_frequency} Гц"
        elif prediction["status"] == "WARNING":
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = f"Напряжение ({prediction['storm_probability_pct']}%)"
            self.status_detail_label.text = f"Рекомендуется релаксация\nЧастота ИИ: {self.active_frequency} Гц"
        else:
            self.status_card.md_bg_color = [0.08, 0.16, 0.1, 1]
            self.status_label.text = "Результат"
            self.status_detail_label.text = f"Вегетативный баланс в норме\nИИ: {self.active_frequency} Гц"

        self._update_metric_display()
        self.old_stress = self.current_stress
        self.old_rmssd = self.current_rmssd

    def _update_metric_display(self):
        self.stress_value_label.text = str(int(self.current_stress))
        self.rmssd_value_label.text = str(int(self.current_rmssd))

        ble_status = self.ble_scanner.get_status()
        hr = ble_status["heart_rate"]
        if hr > 0:
            self.current_bpm = hr
            self.hr_value_label.text = str(hr)
        else:
            watch_status = self.watch_bridge.status()
            bpm = watch_status.get("heart_rate_bpm")
            if bpm:
                self.current_bpm = bpm
                self.hr_value_label.text = str(bpm)
            else:
                self.hr_value_label.text = "--"

        self.freq_value_label.text = f"{self.active_frequency:.1f}"
        self.storm_value_label.text = str(int(self.storm_prob))

        self._update_metric_colors()

    def set_male_profile(self, instance):
        self.gender_profile = "male"
        self.male_btn.md_bg_color = [0, 0.6, 0.8, 1]
        self.female_btn.text_color = [1, 1, 1, 0.6]

    def set_female_profile(self, instance):
        self.gender_profile = "female"
        self.male_btn.md_bg_color = [0.2, 0.2, 0.2, 1]
        self.female_btn.text_color = [1, 0.3, 0.6, 1]

    def mobile_lifecycle_loop(self, dt):
        if self.scan_timer > 0:
            self.scan_timer -= 1
            self.status_label.text = "Идёт замер..."
            self.status_detail_label.text = f"Осталось: {self.scan_timer} сек."
            if self.scan_timer == 0:
                self.on_measurement_complete()
            return

        self._update_metric_display()

    def _check_for_update(self, dt=None):
        """Фоновая проверка обновлений через GitHub Releases."""
        try:
            result = check_for_update(APP_VERSION)
            if result is not None:
                self._update_url = result.get("apk_url")
                tag = result.get("tag", "?")
                self.update_banner_label.text = f"🔄 Доступно обновление {tag}"
                self.update_banner.opacity = 1
                self.update_banner.height = dp(56)
        except Exception:  # noqa: BLE001
            pass

    def _open_update_url(self, instance):
        """Открыть URL скачивания APK в браузере."""
        if self._update_url:
            try:
                import webbrowser
                webbrowser.open(self._update_url)
            except Exception:  # noqa: BLE001
                pass


class AegisNeuroMobileApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        return AegisNeuroMobileScreen()

    def on_start(self):
        """Activity создана. Инициализация BLE и Foreground Service."""
        if platform == "android":
            start_foreground_service()

    def on_resume(self):
        """После разблокировки экрана."""

    def on_pause(self):
        screen = self.root
        if screen is not None:
            screen.is_scanning = False
            screen.scan_timer = 0
        return True

    def on_stop(self):
        screen = self.root
        if screen is None:
            return
        try:
            if getattr(screen, "audio_engine", None) is not None:
                screen.audio_engine.stop_tone()
            if getattr(screen, "ble_scanner", None) is not None:
                screen.ble_scanner.disconnect()
        except Exception as exc:
            print(f"[Aegis-System] stop: {exc}")
        stop_foreground_service()


if __name__ == "__main__":
    try:
        AegisNeuroMobileApp().run()
    finally:
        print("[Aegis-System] Закрытие приложения. Освобождение ресурсов...")