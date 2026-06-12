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
from pathlib import Path

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
WATCH_APK_URL = "https://github.com/shinviktor14-beep/aegisneuro/releases/latest/download/app-debug.apk"


# ==============================================================================
# МОСТ ДЛЯ ДАННЫХ GALAXY WATCH
# ==============================================================================
class WatchDataBridge:
    """Заготовка канала данных Wear OS / Galaxy Watch.

    v42: принимает JSONL-пакеты от будущего Android/Wear receiver.
    """

    def __init__(self):
        self.buffer = WatchDataBuffer()
        self.inbox_path = self._resolve_inbox_path()
        self._read_offset = 0
        self._last_connection_status = {
            "node_connected": platform != "android",
            "node_count": 0,
            "node_names": [],
            "watch_app_ready": platform != "android",
            "watch_app_node_count": 0,
            "watch_app_node_names": [],
            "node_error": None,
        }
        self._start_runtime_bridge()

    def latest_rr_intervals(self):
        self.refresh()
        return self.buffer.latest_rr_intervals()

    def status(self):
        self.refresh()
        status = self.buffer.summary()
        status.update(self.connection_status())
        return status

    def connection_status(self):
        if platform != "android":
            return dict(self._last_connection_status)

        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            ConnectionBridge = autoclass("org.aegisneuro.aegisneuro.AegisWatchConnectionBridge")
            activity = PythonActivity.mActivity
            raw_status = ConnectionBridge.getStatusJson(activity)
            payload = json.loads(str(raw_status))
            nodes = payload.get("nodes") or []
            capability_nodes = payload.get("capability_nodes") or []
            self._last_connection_status = {
                "node_connected": bool(payload.get("connected")),
                "node_count": int(payload.get("node_count") or 0),
                "node_names": [node.get("display_name", "") for node in nodes],
                "watch_app_ready": bool(payload.get("watch_app_ready")),
                "watch_app_node_count": int(payload.get("capability_node_count") or 0),
                "watch_app_node_names": [
                    node.get("display_name", "") for node in capability_nodes
                ],
                "node_error": payload.get("error"),
            }
        except Exception as exc:  # noqa: BLE001
            log.warning("Watch connection check failed: %s", exc)
            self._last_connection_status = {
                "node_connected": False,
                "node_count": 0,
                "node_names": [],
                "watch_app_ready": False,
                "watch_app_node_count": 0,
                "watch_app_node_names": [],
                "node_error": str(exc),
            }
        return dict(self._last_connection_status)

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
        elif payload.get("heart_rate_bpm") or payload.get("bpm"):
            log.info("Watch HR packet accepted without IBI")

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

    def _start_runtime_bridge(self):
        if platform != "android":
            return
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            RuntimeBridge = autoclass("org.aegisneuro.aegisneuro.AegisWatchRuntimeBridge")
            activity = PythonActivity.mActivity
            if activity is not None:
                RuntimeBridge.start(activity)
                log.info("Watch runtime bridge started")
        except Exception as exc:  # noqa: BLE001
            log.warning("Watch runtime bridge unavailable: %s", exc)


class AudioOutputBridge:
    """Checks whether binaural audio can be delivered through headphones."""

    HEADPHONE_TYPES = {
        "TYPE_WIRED_HEADSET": "проводная гарнитура",
        "TYPE_WIRED_HEADPHONES": "проводные наушники",
        "TYPE_BLUETOOTH_A2DP": "Bluetooth-наушники",
        "TYPE_USB_HEADSET": "USB-наушники",
        "TYPE_BLE_HEADSET": "BLE-наушники",
    }

    def __init__(self):
        self._last_status = {
            "connected": platform != "android",
            "device_name": "desktop",
            "detail": "desktop audio",
        }

    def status(self):
        if platform != "android":
            return dict(self._last_status)

        try:
            from jnius import autoclass

            Context = autoclass("android.content.Context")
            AudioDeviceInfo = autoclass("android.media.AudioDeviceInfo")
            AudioManager = autoclass("android.media.AudioManager")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")

            activity = PythonActivity.mActivity
            if activity is None:
                return self._store(False, "нет Activity", "Android Activity недоступна")

            audio_manager = activity.getSystemService(Context.AUDIO_SERVICE)
            devices = audio_manager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)

            for device in devices:
                device_type = device.getType()
                for attr_name, label in self.HEADPHONE_TYPES.items():
                    if (
                        hasattr(AudioDeviceInfo, attr_name)
                        and device_type == getattr(AudioDeviceInfo, attr_name)
                    ):
                        name = str(device.getProductName() or label)
                        return self._store(True, name, label)

            return self._store(False, "нет наушников", "Подключите стерео-наушники")
        except Exception as exc:  # noqa: BLE001
            log.warning("Audio output check failed: %s", exc)
            return self._store(False, "не удалось проверить", str(exc))

    def _store(self, connected, device_name, detail):
        self._last_status = {
            "connected": bool(connected),
            "device_name": device_name,
            "detail": detail,
        }
        return dict(self._last_status)


# ==============================================================================
# МОНОЛИТНЫЙ ИНТЕРФЕЙС И КОНТУР БИОЛОГИЧЕСКОЙ ОБРАТНОЙ СВЯЗИ
# ==============================================================================
class AegisNeuroMobileScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.ai_brain = AegisRLBrain()
        self.audio_engine = AegisAudioEngine()
        self.audio_bridge = AudioOutputBridge()
        self.watch_bridge = WatchDataBridge()
        self.predictor = StormPredictor()

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
        self.audio_calibration_ok = False
        self.audio_left_ok = False
        self.audio_right_ok = False
        self.watch_registration_ok = False
        self.registration_mode = "registration"
        self._audio_device_name = None
        self._headphone_check_running = False
        self._headphone_check_played = False

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
        self.content = content

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
        self.title_card = title_card

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

        self.registration_card = MDCard(
            orientation='vertical',
            padding=dp(18),
            spacing=dp(12),
            size_hint_y=None,
            radius=[dp(12)],
            md_bg_color=[0.06, 0.08, 0.12, 1],
            elevation=2,
        )
        self.registration_card.bind(minimum_height=self.registration_card.setter('height'))

        self.registration_title = MDLabel(
            text="Регистрация оборудования",
            halign="center",
            font_style="H6",
            theme_text_color="Custom",
            text_color=[0.85, 0.92, 0.96, 1],
            size_hint_y=None,
            height=dp(34),
        )
        self.registration_detail = MDLabel(
            text="Перед началом нужно проверить наушники и часы",
            halign="center",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=[0.58, 0.68, 0.74, 1],
            size_hint_y=None,
            height=dp(28),
        )
        self.registration_detail.bind(
            width=lambda inst, w: setattr(inst, 'text_size', (w, None))
        )
        self.registration_detail.bind(
            texture_size=lambda inst, ts: setattr(inst, 'height', max(dp(28), ts[1]))
        )
        self.check_headphones_btn = MDRaisedButton(
            text="1. ПРОВЕРКА НАУШНИКОВ",
            md_bg_color=[0.18, 0.45, 0.72, 1],
            size_hint_x=1.0,
            size_hint_y=None,
            height=dp(52),
            on_release=self.open_headphone_registration,
        )
        self.check_watch_btn = MDRaisedButton(
            text="2. ПРОВЕРКА ЧАСОВ / СЕНСОРОВ",
            md_bg_color=[0.18, 0.55, 0.26, 1],
            size_hint_x=1.0,
            size_hint_y=None,
            height=dp(52),
            on_release=self.open_watch_registration,
        )
        self.registration_card.add_widget(self.registration_title)
        self.registration_card.add_widget(self.registration_detail)
        self.registration_card.add_widget(self.check_headphones_btn)
        self.registration_card.add_widget(self.check_watch_btn)
        content.add_widget(self.registration_card)

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
            text="Готов к замеру",
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
            text="Подключите Galaxy Watch4 и дождитесь потока HR/IBI",
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

        self.audio_status_card = MDCard(
            orientation='vertical',
            padding=dp(16),
            spacing=dp(4),
            size_hint_y=None,
            radius=[dp(12)],
            md_bg_color=[0.12, 0.09, 0.05, 1],
            elevation=1,
        )
        self.audio_status_card.bind(minimum_height=self.audio_status_card.setter('height'))

        self.audio_status_label = MDLabel(
            text="Аудиовыход",
            halign="center",
            font_style="Subtitle2",
            theme_text_color="Custom",
            text_color=[0.9, 0.85, 0.72, 1],
            size_hint_y=None,
            height=dp(28),
        )
        self.audio_status_detail_label = MDLabel(
            text="Подключите стерео-наушники",
            halign="center",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=[0.72, 0.68, 0.58, 1],
            size_hint_y=None,
            height=dp(22),
        )
        self.audio_status_detail_label.bind(
            width=lambda inst, w: setattr(inst, 'text_size', (w, None))
        )
        self.audio_status_detail_label.bind(
            texture_size=lambda inst, ts: setattr(inst, 'height', max(dp(22), ts[1]))
        )
        audio_check_row = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8),
        )
        self.audio_test_btn = MDRaisedButton(
            text="ТЕСТ 4.7 ГЦ",
            md_bg_color=[0.18, 0.45, 0.72, 1],
            size_hint_x=0.34,
            on_release=self.start_headphone_check,
        )
        self.audio_left_btn = MDRaisedButton(
            text="ЛЕВЫЙ",
            md_bg_color=[0.18, 0.55, 0.26, 1],
            size_hint_x=0.33,
            on_release=self.confirm_left_headphone,
        )
        self.audio_right_btn = MDRaisedButton(
            text="ПРАВЫЙ",
            md_bg_color=[0.18, 0.55, 0.26, 1],
            size_hint_x=0.33,
            on_release=self.confirm_right_headphone,
        )
        audio_check_row.add_widget(self.audio_test_btn)
        audio_check_row.add_widget(self.audio_left_btn)
        audio_check_row.add_widget(self.audio_right_btn)
        self.audio_status_card.add_widget(self.audio_status_label)
        self.audio_status_card.add_widget(self.audio_status_detail_label)
        self.audio_status_card.add_widget(audio_check_row)
        content.add_widget(self.audio_status_card)

        self.headphone_actions = MDBoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(56),
            padding=[dp(8), dp(4), dp(8), dp(4)],
        )
        self.headphone_back_btn = MDRaisedButton(
            text="НАЗАД",
            md_bg_color=[0.18, 0.22, 0.28, 1],
            size_hint_x=1.0,
            size_hint_y=None,
            height=dp(48),
            on_release=self.back_to_registration,
        )
        self.headphone_actions.add_widget(self.headphone_back_btn)

        self.watch_check_actions = MDBoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(168),
            spacing=dp(8),
            padding=[dp(8), dp(4), dp(8), dp(4)],
        )
        self.watch_retry_btn = MDRaisedButton(
            text="ПОВТОРИТЬ",
            md_bg_color=[0.18, 0.45, 0.72, 1],
            size_hint_x=1.0,
            size_hint_y=None,
            height=dp(48),
            on_release=self.open_watch_registration,
        )
        self.watch_install_btn = MDRaisedButton(
            text="УСТАНОВИТЬ НА ЧАСЫ",
            md_bg_color=[0.55, 0.22, 0.12, 1],
            size_hint_x=1.0,
            size_hint_y=None,
            height=dp(48),
            on_release=self.open_watch_install,
        )
        self.watch_back_btn = MDRaisedButton(
            text="НАЗАД",
            md_bg_color=[0.18, 0.22, 0.28, 1],
            size_hint_x=1.0,
            size_hint_y=None,
            height=dp(48),
            on_release=self.back_to_registration,
        )
        self.watch_check_actions.add_widget(self.watch_retry_btn)
        self.watch_check_actions.add_widget(self.watch_install_btn)
        self.watch_check_actions.add_widget(self.watch_back_btn)

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
        self.profile_card = profile_card
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

        # ── 5. Кнопка действия (с отступом снизу) ──
        action_container = MDBoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(72),
            padding=[dp(8), dp(8), dp(8), dp(8)],
        )

        self.action_btn = MDRaisedButton(
            text="ПРОВЕРИТЬ WATCH",
            pos_hint={"center_x": 0.5},
            md_bg_color=[0, 0.78, 0.35, 1],
            size_hint_x=1.0,
            size_hint_y=None,
            height=dp(52),
            on_release=self.start_scan,
            font_style="Button",
        )
        action_container.add_widget(self.action_btn)
        self.action_container = action_container
        content.add_widget(action_container)

        # ── Нижний отступ для скролла ──
        bottom_spacer = MDBoxLayout(size_hint_y=None, height=dp(24))
        self.bottom_spacer = bottom_spacer
        content.add_widget(bottom_spacer)

        scroll.add_widget(content)
        self.add_widget(scroll)

        # ── Фоновые задачи ──
        Clock.schedule_interval(self.mobile_lifecycle_loop, 1.0)
        Clock.schedule_interval(self.refresh_watch_status, 1.0)
        Clock.schedule_interval(self.refresh_audio_status, 1.0)
        Clock.schedule_once(self._check_for_update, 3.0)
        self._render_registration_mode("registration")

    def _render_registration_mode(self, mode):
        self.registration_mode = mode
        widgets = [self.title_card]

        if mode == "registration":
            self._update_registration_summary()
            widgets.append(self.registration_card)
        elif mode == "headphones":
            widgets.append(self.audio_status_card)
            widgets.append(self.headphone_actions)
        elif mode == "watch_check":
            widgets.append(self.status_card)
            widgets.append(self.watch_check_actions)
        elif mode == "main":
            widgets.extend([
                self.status_card,
                self.audio_status_card,
                self.profile_card,
                self.metrics_card,
                self.action_container,
                self.bottom_spacer,
            ])

        self.content.clear_widgets()
        for widget in widgets:
            self.content.add_widget(widget)

    def _update_registration_summary(self):
        audio_text = "наушники проверены" if self.audio_calibration_ok else "наушники не проверены"
        watch_text = "часы/сенсоры готовы" if self.watch_registration_ok else "часы/сенсоры не проверены"
        self.registration_detail.text = f"{audio_text}\n{watch_text}"
        self.check_headphones_btn.md_bg_color = (
            [0.08, 0.55, 0.24, 1] if self.audio_calibration_ok else [0.58, 0.12, 0.12, 1]
        )
        self.check_watch_btn.md_bg_color = (
            [0.08, 0.55, 0.24, 1] if self.watch_registration_ok else [0.58, 0.12, 0.12, 1]
        )
        self._update_headphone_button_colors()

    def _update_headphone_button_colors(self):
        if hasattr(self, "audio_left_btn"):
            self.audio_left_btn.md_bg_color = (
                [0.08, 0.55, 0.24, 1] if self.audio_left_ok else [0.58, 0.12, 0.12, 1]
            )
        if hasattr(self, "audio_right_btn"):
            self.audio_right_btn.md_bg_color = (
                [0.08, 0.55, 0.24, 1] if self.audio_right_ok else [0.58, 0.12, 0.12, 1]
            )
        if hasattr(self, "watch_retry_btn"):
            self.watch_retry_btn.md_bg_color = (
                [0.08, 0.55, 0.24, 1] if self.watch_registration_ok else [0.58, 0.12, 0.12, 1]
            )

    def _complete_registration_step(self):
        self.watch_registration_ok = self._is_watch_ready_for_registration()
        if self.audio_calibration_ok and self.watch_registration_ok:
            self._render_registration_mode("main")
        else:
            self._render_registration_mode("registration")

    def _is_watch_ready_for_registration(self):
        status = self.watch_bridge.status()
        return bool(
            status.get("connected")
            or status.get("watch_app_ready")
            or status.get("rr_count", 0) >= 10
        )

    def open_headphone_registration(self, *args):
        self.refresh_audio_status()
        self._render_registration_mode("headphones")

    def open_watch_registration(self, *args):
        self.refresh_watch_status()
        self.watch_registration_ok = self._is_watch_ready_for_registration()
        if self.watch_registration_ok and self.audio_calibration_ok:
            self._render_registration_mode("main")
        else:
            self._render_registration_mode("watch_check")

    def back_to_registration(self, *args):
        self._complete_registration_step()

    def open_watch_install(self, *args):
        self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
        self.status_label.text = "Установка на часы"
        self.status_detail_label.text = (
            "Откроется установочный файл AegisNeuro Watch. В продакшне эта кнопка ведёт "
            "в официальный канал установки, где клиент подтверждает установку на часах."
        )
        try:
            import webbrowser

            webbrowser.open(WATCH_APK_URL)
        except Exception as exc:  # noqa: BLE001
            log.warning("Watch install URL open failed: %s", exc)

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

    def start_headphone_check(self, *args):
        audio_status = self.audio_bridge.status()
        if not audio_status["connected"]:
            self.audio_calibration_ok = False
            self.audio_left_ok = False
            self.audio_right_ok = False
            self._update_headphone_button_colors()
            self.audio_status_card.md_bg_color = [0.28, 0.16, 0.05, 1]
            self.audio_status_label.text = "Сначала подключите наушники"
            self.audio_status_detail_label.text = "Тест 4.7 Гц доступен только через стерео-наушники"
            return

        self.audio_calibration_ok = False
        self.audio_left_ok = False
        self.audio_right_ok = False
        self._update_headphone_button_colors()
        self._headphone_check_running = True
        self._headphone_check_played = True
        self.audio_engine.start_headphone_check(4.7, 9.0)
        self.audio_status_card.md_bg_color = [0.06, 0.14, 0.22, 1]
        self.audio_status_label.text = "Идёт тест наушников"
        self.audio_status_detail_label.text = "Слева: ровный тон. Справа: ровный тон. Потом оба уха: разность 4.7 Гц"
        Clock.schedule_once(self._finish_headphone_check, 9.5)

    def _finish_headphone_check(self, dt=None):
        self._headphone_check_running = False
        if not self.audio_calibration_ok:
            self.audio_status_card.md_bg_color = [0.28, 0.16, 0.05, 1]
            self.audio_status_label.text = "Подтвердите стерео"
            self.audio_status_detail_label.text = "Нажмите «ЛЕВЫЙ» и «ПРАВЫЙ», если тон был строго в каждом ухе отдельно"

    def _confirm_headphone_side(self, side):
        audio_status = self.audio_bridge.status()
        if not self._headphone_check_played:
            self.audio_calibration_ok = False
            self.audio_status_card.md_bg_color = [0.28, 0.16, 0.05, 1]
            self.audio_status_label.text = "Сначала запустите тест"
            self.audio_status_detail_label.text = "Сначала должен прозвучать левый канал, потом правый, потом 4.7 Гц"
            return

        if not audio_status["connected"]:
            self.audio_calibration_ok = False
            self.audio_left_ok = False
            self.audio_right_ok = False
            self._update_headphone_button_colors()
            self.audio_status_card.md_bg_color = [0.28, 0.16, 0.05, 1]
            self.audio_status_label.text = "Нужны наушники"
            self.audio_status_detail_label.text = "Подключите стерео-наушники и повторите тест"
            return

        if side == "left":
            self.audio_left_ok = True
        elif side == "right":
            self.audio_right_ok = True

        self.audio_calibration_ok = self.audio_left_ok and self.audio_right_ok
        self._audio_device_name = audio_status["device_name"]
        self._update_headphone_button_colors()

        if self.audio_calibration_ok:
            self.audio_status_card.md_bg_color = [0.08, 0.16, 0.1, 1]
            self.audio_status_label.text = "Стерео 4.7 Гц проверено"
            self.audio_status_detail_label.text = f"{audio_status['device_name']}: левый и правый канал подтверждены"
            Clock.schedule_once(lambda dt: self._complete_registration_step(), 0.8)
        else:
            missing = "правый" if self.audio_left_ok else "левый"
            self.audio_status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.audio_status_label.text = "Подтвердите второй канал"
            self.audio_status_detail_label.text = f"Подтверждён один канал. Теперь подтвердите {missing} наушник"

    def confirm_left_headphone(self, *args):
        self._confirm_headphone_side("left")

    def confirm_right_headphone(self, *args):
        self._confirm_headphone_side("right")

    def refresh_audio_status(self, dt=None):
        audio_status = self.audio_bridge.status()
        if self._headphone_check_running:
            return audio_status

        if audio_status["connected"]:
            if self._audio_device_name and self._audio_device_name != audio_status["device_name"]:
                self.audio_calibration_ok = False
                self.audio_left_ok = False
                self.audio_right_ok = False
                self._update_headphone_button_colors()
                self._headphone_check_played = False
            self._audio_device_name = audio_status["device_name"]
            self.audio_status_card.md_bg_color = [0.08, 0.16, 0.1, 1]
            if self.audio_calibration_ok:
                self.audio_status_label.text = "Стерео 4.7 Гц готово"
                self.audio_status_detail_label.text = audio_status["device_name"]
            else:
                self.audio_status_label.text = "Наушники подключены"
                self.audio_status_detail_label.text = "Запустите тест 4.7 Гц и подтвердите левый и правый наушник"
        else:
            self.audio_calibration_ok = False
            self.audio_left_ok = False
            self.audio_right_ok = False
            self._update_headphone_button_colors()
            self._audio_device_name = None
            self._headphone_check_played = False
            self.audio_status_card.md_bg_color = [0.28, 0.16, 0.05, 1]
            self.audio_status_label.text = "Нужны наушники"
            self.audio_status_detail_label.text = "Бинауральные частоты работают только в стерео-наушниках"
        if self.registration_mode == "registration":
            self._update_registration_summary()
        return audio_status

    def refresh_watch_status(self, dt=None):
        if self.is_scanning:
            return

        watch_status = self.watch_bridge.status()
        rr_count = watch_status["rr_count"]
        bpm = watch_status["heart_rate_bpm"]
        connected = watch_status["connected"]
        node_connected = watch_status.get("node_connected", False)
        node_names = ", ".join(watch_status.get("node_names") or [])
        watch_app_ready = watch_status.get("watch_app_ready", False)
        watch_app_names = ", ".join(watch_status.get("watch_app_node_names") or [])
        quality = watch_status["quality"]
        self._update_metric_display(watch_status)

        if rr_count >= 10:
            self.status_card.md_bg_color = [0.08, 0.16, 0.1, 1]
            self.status_label.text = "Galaxy Watch4 готов"
            bpm_text = f"HR: {bpm} bpm" if bpm else "HR: ожидаем"
            self.status_detail_label.text = f"{bpm_text}\nIBI/R-R: {rr_count} интервалов, качество: {quality}"
        elif connected:
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = "Aegis Watch передаёт HR"
            bpm_text = f"HR: {bpm} bpm" if bpm else "HR получаем"
            self.status_detail_label.text = f"{bpm_text}\nДля HRV нужно минимум 10 IBI, сейчас: {rr_count}"
        elif watch_app_ready:
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = "Aegis Watch найден"
            device_text = watch_app_names or "AegisNeuro Watch"
            self.status_detail_label.text = (
                f"{device_text}\nМодуль установлен. Запустите измерение на часах "
                "и разрешите доступ к сенсорам."
            )
        elif node_connected:
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = "Часы подключены, модуля нет"
            device_text = node_names or "Wear OS"
            self.status_detail_label.text = (
                f"{device_text}\nСвязь есть, но AegisNeuro Watch не установлен. "
                "Нажмите «УСТАНОВИТЬ НА ЧАСЫ»."
            )
        else:
            self.status_card.md_bg_color = [0.08, 0.12, 0.18, 1]
            self.status_label.text = "Ожидаем Galaxy Watch4"
            self.status_detail_label.text = "Сначала подключите часы в Galaxy Wearable или другое устройство-сенсор"

        if hasattr(self, "watch_install_btn"):
            install_available = bool(node_connected and not watch_app_ready and not connected)
            self.watch_install_btn.disabled = not install_available
            self.watch_install_btn.md_bg_color = (
                [0.55, 0.22, 0.12, 1] if install_available else [0.18, 0.22, 0.28, 1]
            )

        self.watch_registration_ok = self._is_watch_ready_for_registration()
        self._update_headphone_button_colors()
        if self.registration_mode == "registration":
            self._update_registration_summary()

    def start_scan(self, *args):
        if self.is_scanning:
            return

        rr_data = self.watch_bridge.latest_rr_intervals()
        watch_status = self.watch_bridge.status()
        audio_status = self.refresh_audio_status()
        self._update_metric_display(watch_status)

        if not audio_status["connected"]:
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = "Подключите наушники"
            self.status_detail_label.text = (
                "Для нейрорегуляции нужен стерео-аудиовыход: проводные, USB или Bluetooth-наушники."
            )
            return

        if not self.audio_calibration_ok:
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = "Проверьте стерео 4.7 Гц"
            self.status_detail_label.text = (
                "Нажмите «ТЕСТ 4.7 ГЦ», затем подтвердите отдельно «ЛЕВЫЙ» и «ПРАВЫЙ»."
            )
            return

        if not watch_status.get("node_connected", False) and not watch_status["connected"]:
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = "Часы не подключены"
            self.status_detail_label.text = "Проверьте Galaxy Watch4 в Galaxy Wearable и дождитесь Wear OS-соединения."
            return

        if not watch_status.get("watch_app_ready", False) and not watch_status["connected"]:
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = "Модуль Watch не найден"
            self.status_detail_label.text = (
                "Телефон видит часы, но не видит AegisNeuro Watch-компонент с capability aegisneuro_vitals."
            )
            return

        if len(rr_data) < 10:
            bpm = watch_status["heart_rate_bpm"]
            rr_count = watch_status["rr_count"]
            quality = watch_status["quality"]
            self.status_card.md_bg_color = [0.3, 0.2, 0.05, 1]
            self.status_label.text = "Galaxy Watch4"
            if bpm:
                self.status_detail_label.text = (
                    f"HR: {bpm} bpm\n"
                    f"IBI/R-R: {rr_count}/10 для HRV, качество: {quality}"
                )
            else:
                self.status_detail_label.text = "Ожидаем поток HR/IBI с часов. Камера и фонарик отключены."
            return

        self.scan_timer = 1
        self.is_scanning = True

        self.status_card.md_bg_color = [0.06, 0.14, 0.22, 1]
        self.status_label.text = "Идёт Watch-замер..."
        self.status_detail_label.text = "Анализируем данные Galaxy Watch4"

        self.action_btn.text = "ИДЁТ ЗАМЕР..."

    def on_scan_complete(self):
        self.is_scanning = False

        self.action_btn.disabled = False
        self.action_btn.md_bg_color = [0, 0.78, 0.35, 1]
        self.action_btn.text = "ПРОВЕРИТЬ WATCH"

        rr_data = self.watch_bridge.latest_rr_intervals()

        # Анализ через канонический StormPredictor.analyze()
        prediction = self.predictor.analyze(rr_data)

        if prediction["status"] == "INSUFFICIENT_DATA":
            self.status_card.md_bg_color = [0.35, 0.12, 0.12, 1]
            self.status_label.text = "⚠️ Замер не удался"
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
            self.status_label.text = f"⚠️ Угроза штурма ({prediction['storm_probability_pct']}%)"
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

    def _update_metric_display(self, watch_status=None):
        self.stress_value_label.text = str(int(self.current_stress))
        self.rmssd_value_label.text = str(int(self.current_rmssd))
        
        if watch_status is None:
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
            self.status_label.text = "Идёт Watch-замер..."
            self.status_detail_label.text = f"Осталось: {self.scan_timer} сек."
            if self.scan_timer == 0:
                self.on_scan_complete()
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
        """Activity создана. Сенсоры часов подключаются отдельным Wear OS модулем."""

    def on_resume(self):
        """После разблокировки камера не используется."""

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
        except Exception as exc:
            print(f"[Aegis-System] audio stop: {exc}")


if __name__ == "__main__":
    try:
        AegisNeuroMobileApp().run()
    finally:
        print("[Aegis-System] Закрытие приложения. Освобождение ресурсов...")
