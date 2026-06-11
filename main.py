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
from aegis.core import AegisRLBrain, StormPredictor
from aegis.update_checker import check_for_update
from aegis_ppg_processor import AegisPPGProcessor
from aegis_audio_engine import AegisAudioEngine
from android_camera import AndroidCameraBridge

APP_VERSION = "1.0.0"


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
            text="Готов к замеру",
            halign="center",
            font_style="H6",
            theme_text_color="Custom",
            text_color=[0.85, 0.92, 0.96, 1],
            size_hint_y=None,
        )
        self.status_label.bind(
            texture_size=self.status_label.setter('size')
        )
        self.status_label.bind(
            height=lambda *a: self.status_card.setter('minimum_height')(self.status_card, self.status_card.minimum_height)
        )

        self.status_detail_label = MDLabel(
            text="Приложите палец к камере и нажмите кнопку ниже",
            halign="center",
            font_style="Body1",
            theme_text_color="Custom",
            text_color=[0.55, 0.65, 0.70, 1],
            size_hint_y=None,
        )
        self.status_detail_label.bind(
            texture_size=self.status_detail_label.setter('size')
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
        )
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
        )
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

        metrics_row.add_widget(stress_col)
        metrics_row.add_widget(rmssd_col)
        self.metrics_card.add_widget(metrics_row)
        content.add_widget(self.metrics_card)

        # ── 5. Кнопка действия (с отступом снизу) ──
        action_container = MDBoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(72),
            padding=[dp(8), dp(8), dp(8), dp(8)],
        )

        self.action_btn = MDRaisedButton(
            text="ЗАПУСТИТЬ ЗАМЕР",
            pos_hint={"center_x": 0.5},
            md_bg_color=[0, 0.78, 0.35, 1],
            size_hint_x=1.0,
            size_hint_y=None,
            height=dp(52),
            on_release=self.start_scan,
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
        Clock.schedule_interval(self._tick_ppg, 1.0 / 30.0)
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
        if not self.camera_bridge.is_ready():
            self.status_card.md_bg_color = [0.35, 0.12, 0.12, 1]
            self.status_label.text = "⚠️ Камера не готова"
            self.status_detail_label.text = f"{self.camera_bridge.get_status_text()}\nПодождите или перезапустите приложение"
            return

        self.ppg_processor.red_values.clear()
        self.ppg_processor.timestamps.clear()
        self.hardware_bridge.set_flashlight(turn_on=True)
        self.scan_timer = 15
        self.is_scanning = True

        self.status_card.md_bg_color = [0.06, 0.14, 0.22, 1]
        self.status_label.text = "Идёт замер..."
        self.status_detail_label.text = "Удерживайте палец неподвижно на камере"

        self.action_btn.disabled = True
        self.action_btn.md_bg_color = [0.3, 0.3, 0.3, 1]
        self.action_btn.text = "ИДЁТ ЗАМЕР..."

    def on_scan_complete(self):
        self.hardware_bridge.set_flashlight(turn_on=False)
        self.is_scanning = False

        self.action_btn.disabled = False
        self.action_btn.md_bg_color = [0, 0.78, 0.35, 1]
        self.action_btn.text = "ЗАПУСТИТЬ ЗАМЕР"

        rr_data = self.ppg_processor.get_rr_intervals()

        # Анализ через канонический StormPredictor.analyze()
        prediction = self.predictor.analyze(rr_data)

        if prediction["status"] == "INSUFFICIENT_DATA":
            self.status_card.md_bg_color = [0.35, 0.12, 0.12, 1]
            self.status_label.text = "⚠️ Замер не удался"
            self.status_detail_label.text = "Недостаточно данных. Повторите замер."
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

    def _update_metric_display(self):
        self.stress_value_label.text = str(int(self.current_stress))
        self.rmssd_value_label.text = str(int(self.current_rmssd))
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
        """Вызывается когда Activity создана — безопасно открывать камеру."""
        screen = self.root
        if screen is not None and hasattr(screen, 'camera_bridge'):
            screen.camera_bridge.start_capture()

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
