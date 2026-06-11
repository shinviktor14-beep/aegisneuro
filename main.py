# Имя файла: main.py
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivy.clock import Clock
from kivy.utils import platform

import math
import random

# Импортируем ядра из пакета aegis
from aegis.core import AegisRLBrain, StormPredictor
from aegis_ppg_processor import AegisPPGProcessor
from aegis_audio_engine import AegisAudioEngine
from android_camera import AndroidCameraBridge


# ==============================================================================
# МОСТ ДЛЯ УПРАВЛЕНИЯ АППАРАТУРОЙ (фонарик, будущее: BLE)
# ==============================================================================
class AndroidHardwareBridge:
    """Тонкая прослойка над AndroidCameraBridge.set_flash().
    На десктопе — печатает в лог (для отладки UI)."""

    def __init__(self, camera_bridge: AndroidCameraBridge):
        self.camera_bridge = camera_bridge

    def set_flashlight(self, turn_on: bool = True) -> None:
        try:
            self.camera_bridge.set_flash(bool(turn_on))
        except Exception as exc:  # noqa: BLE001
            print(f"[Aegis-Hardware] set_flashlight: {exc}")


# ==============================================================================
# МОНОЛИТНЫЙ ИНТЕРФЕЙС И КОНТУР БИОЛОГИЧЕСКОЙ ОБРАТНОЙ СВЯЗИ
# ==============================================================================
class AegisNeuroMobileScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.ai_brain = AegisRLBrain()
        self.ppg_processor = AegisPPGProcessor()
        self.audio_engine = AegisAudioEngine()
        self.camera_bridge = AndroidCameraBridge()
        self.camera_bridge.request_permission()
        self.camera_bridge.start_capture()
        self.hardware_bridge = AndroidHardwareBridge(self.camera_bridge)
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

        self.audio_engine.start_tone()
        self.build_ui()

    def build_ui(self):
        main_layout = MDBoxLayout(orientation='vertical', padding=20, spacing=15)

        self.title_label = MDLabel(
            text="AEGISNEURO OS v1.0", halign="center", font_style="H5",
            theme_text_color="Custom", text_color=[0, 1, 0.8, 1], size_hint_y=None, height=40
        )
        main_layout.add_widget(self.title_label)

        self.camera_status_card = MDBoxLayout(
            orientation='vertical', padding=15,
            size_hint_y=None, height=80, md_bg_color=[0.06, 0.08, 0.12, 1]
        )
        self.camera_status_label = MDLabel(
            text=(
                "[Camera2] Ожидание кадров с камеры…\n"
                "Приложите палец к объективу и нажмите «ЗАПУСТИТЬ ЗАМЕР»."
            ),
            halign="center", theme_text_color="Custom", text_color=[0.7, 0.85, 0.95, 1],
        )
        self.camera_status_card.add_widget(self.camera_status_label)
        main_layout.add_widget(self.camera_status_card)

        self.status_card = MDBoxLayout(
            orientation='vertical', padding=15, size_hint_y=None, height=120, md_bg_color=[0.1, 0.12, 0.16, 1]
        )
        self.status_label = MDLabel(
            text="Камера и аудио-контур готовы.\nПриложите палец и начните замер.", halign="center",
            theme_text_color="Custom", text_color=[1, 1, 1, 1]
        )
        self.status_card.add_widget(self.status_label)
        main_layout.add_widget(self.status_card)

        gender_layout = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=45, spacing=10)
        self.male_btn = MDRaisedButton(text="Мужской профиль", md_bg_color=[0, 0.6, 0.8, 1], on_release=self.set_male_profile)
        try:
            self.female_btn = MDFlatButton(text="Женский профиль", theme_text_color="Custom", text_color=[1, 1, 1, 0.6], on_release=self.set_female_profile)
        except Exception:
            self.female_btn = MDRaisedButton(text="Женский профиль", theme_text_color="Custom", text_color=[1, 1, 1, 0.6], on_release=self.set_female_profile)
        gender_layout.add_widget(self.male_btn)
        gender_layout.add_widget(self.female_btn)
        main_layout.add_widget(gender_layout)

        self.metrics_label = MDLabel(
            text="Индекс Стресса: -- у.е.\nПарасимпатика (RMSSD): -- ms", halign="center",
            font_style="Subtitle1", theme_text_color="Custom", text_color=[0.7, 0.7, 0.8, 1]
        )
        main_layout.add_widget(self.metrics_label)

        self.action_btn = MDRaisedButton(
            text="ЗАПУСТИТЬ НАСТОЯЩИЙ PPG ЗАМЕР", pos_hint={"center_x": 0.5},
            md_bg_color=[0, 1, 0.4, 1], size_hint_x=0.9, height=55,
            on_release=self.start_scan
        )
        main_layout.add_widget(self.action_btn)

        self.add_widget(main_layout)
        Clock.schedule_interval(self.mobile_lifecycle_loop, 1.0)
        Clock.schedule_interval(self._tick_ppg, 1.0 / 30.0)

    def _tick_ppg(self, dt):
        """30 раз в секунду: забираем у камеры последнее «среднее красное» и скармливаем в PPG."""
        try:
            mean_red = self.camera_bridge.get_mean_red()
        except Exception:
            return
        if mean_red <= 0.0:
            return
        try:
            self.ppg_processor.process_frame(mean_red)
        except Exception as exc:
            print(f"[Aegis-PPG tick] {exc}")

    def start_scan(self, *args):
        self.ppg_processor.red_values.clear()
        self.ppg_processor.timestamps.clear()
        self.hardware_bridge.set_flashlight(turn_on=True)
        self.scan_timer = 15
        self.is_scanning = True
        self.status_card.md_bg_color = [0.1, 0.18, 0.25, 1]
        self.status_label.text = "СБОР КАРДИО-СИГНАЛА ИЗ КАПИЛЛЯРОВ...\nПожалуйста, удерживайте палец неподвижно."

    def on_scan_complete(self):
        self.hardware_bridge.set_flashlight(turn_on=False)
        self.is_scanning = False

        rr_data = self.ppg_processor.get_rr_intervals()

        # Анализ через канонический StormPredictor.analyze()
        prediction = self.predictor.analyze(rr_data)

        if prediction["status"] == "INSUFFICIENT_DATA":
            self.status_card.md_bg_color = [0.35, 0.15, 0.15, 1]
            self.status_label.text = f"⚠️ ЗАМЕР СОРВАН.\n{prediction['triggers'][0]}. Повторите замер."
            return

        self.current_rmssd = prediction["metrics"]["rmssd"]
        self.current_stress = prediction["metrics"]["stress_index"]

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
            self.status_card.md_bg_color = [0.4, 0.12, 0.12, 1]
            anomaly_text = prediction["triggers"][0] if prediction["triggers"] else "Хаос ЦНС"
            self.status_label.text = f"⚠️ УГРОЗА ШТОРМА ({prediction['storm_probability_pct']}% / Окно: 2ч)\n{anomaly_text}.\nИИ подает: {self.active_frequency} Гц"
        elif prediction["status"] == "WARNING":
            self.status_card.md_bg_color = [0.35, 0.22, 0.05, 1]
            self.status_label.text = f" Напряжение систем ({prediction['storm_probability_pct']}%)\nРекомендуется сессия релаксации.\nЧастота ИИ: {self.active_frequency} Гц"
        else:
            self.status_card.md_bg_color = [0.1, 0.18, 0.12, 1]
            self.status_label.text = f"Щит активен. Вегетативный баланс в норме.\nИИ транслирует частоту: {self.active_frequency} Гц"

        self.old_stress = self.current_stress
        self.old_rmssd = self.current_rmssd

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
            self.status_label.text = f"ИДЕТ СКАНИРОВАНИЕ... Осталось: {self.scan_timer} сек."
            if self.scan_timer == 0:
                self.on_scan_complete()
            return

        self.metrics_label.text = f"Индекс Стресса: {int(self.current_stress)} у.е.\nПарасимпатика (RMSSD): {int(self.current_rmssd)} ms"


class AegisNeuroMobileApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        return AegisNeuroMobileScreen()

    def on_stop(self):
        screen = self.root
        if screen is None:
            return
        try:
            if getattr(screen, "camera_bridge", None) is not None:
                screen.camera_bridge.stop_capture()
        except Exception as exc:
            print(f"[Aegis-System] camera stop: {exc}")
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