from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivy.clock import Clock
import math
import random

# Импортируем ядра из пакета aegis
from aegis.core import AegisRLBrain, StormPredictor


# Имитация работы с сенсорами смартфона (PPG/Фонарик)
class HardwareBridgeStub:
    def enable_flashlight(self):
        print("[Android/iOS API] Вспышка камеры активирована для замера PPG.")
    def disable_flashlight(self):
        print("[Android/iOS API] Вспышка камеры выключена.")

class PPGProcessorStub:
    def get_rr_intervals(self):
        return [random.randint(750, 950) for _ in range(20)]

class PulseOrbStub:
    def __init__(self):
        self.active = False


# ==============================================================================
# ГЛАВНЫЙ ЭКРАН МОБИЛЬНОГО ПРИЛОЖЕНИЯ AEGISNEURO
# ==============================================================================
class AegisNeuroMobileScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.ai_brain = AegisRLBrain()
        self.predictor = StormPredictor()

        self.hardware_bridge = HardwareBridgeStub()
        self.ppg_processor = PPGProcessorStub()
        self.pulse_orb = PulseOrbStub()

        self.current_stress = 310
        self.gender_profile = "male"
        self.scan_timer = 0

        self.build_ui()

    def build_ui(self):
        main_layout = MDBoxLayout(orientation='vertical', padding=20, spacing=15)

        self.title_label = MDLabel(
            text="AEGISNEURO OS v1.0",
            halign="center", font_style="H5",
            theme_text_color="Custom", text_color=[0, 1, 0.8, 1],
            size_hint_y=None, height=50
        )
        main_layout.add_widget(self.title_label)

        self.status_card = MDBoxLayout(
            orientation='vertical', padding=15,
            size_hint_y=None, height=120,
            md_bg_color=[0.1, 0.12, 0.16, 1]
        )
        self.status_label = MDLabel(
            text="Статус щита: ГОТОВ К СКАНИРОВАНИЮ",
            halign="center", theme_text_color="Custom", text_color=[1, 1, 1, 1]
        )
        self.status_card.add_widget(self.status_label)
        main_layout.add_widget(self.status_card)

        gender_layout = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        self.male_btn = MDRaisedButton(
            text="Мужской профиль", md_bg_color=[0, 0.6, 0.8, 1],
            on_release=self.set_male_profile
        )
        self.female_btn = MDFlatButton(
            text="Женский профиль", theme_text_color="Custom",
            text_color=[1, 1, 1, 0.6], on_release=self.set_female_profile
        )
        gender_layout.add_widget(self.male_btn)
        gender_layout.add_widget(self.female_btn)
        main_layout.add_widget(gender_layout)

        self.metrics_label = MDLabel(
            text="Индекс Стресса: -- у.е.\nПарасимпатика (RMSSD): -- ms",
            halign="center", font_style="Subtitle1",
            theme_text_color="Custom", text_color=[0.7, 0.7, 0.8, 1]
        )
        main_layout.add_widget(self.metrics_label)

        self.action_btn = MDRaisedButton(
            text="ЗАПУСТИТЬ СКАНИРОВАНИЕ СУТОЧНОГО ЩИТА",
            pos_hint={"center_x": 0.5}, md_bg_color=[0, 1, 0.4, 1],
            size_hint_x=0.9, height=60, on_release=self.start_scan
        )
        main_layout.add_widget(self.action_btn)

        self.add_widget(main_layout)
        Clock.schedule_interval(self.mobile_lifecycle_loop, 1.0)

    def start_scan(self, *args):
        self.hardware_bridge.enable_flashlight()
        self.scan_timer = 10
        self.status_card.md_bg_color = [0.1, 0.2, 0.3, 1]
        self.status_label.text = "СКАНИРОВАНИЕ БИО-ЩИТА: ПРИЛОЖИТЕ ПАЛЕЦ К КАМЕРЕ"
        self.pulse_orb.active = True

    def on_scan_complete(self):
        self.hardware_bridge.disable_flashlight()
        self.pulse_orb.active = False

        rr_data = self.ppg_processor.get_rr_intervals()
        # Канонический API: .analyze() вместо .analyze_morning_test()
        prediction = self.predictor.analyze(rr_data)

        if prediction.get("status") == "STORM_ALERT":
            self.show_alert_ui(prediction["storm_probability_pct"])
        elif prediction.get("status") == "WARNING":
            self.show_alert_ui(prediction["storm_probability_pct"])
        else:
            self.show_safe_ui()

    def show_alert_ui(self, probability):
        self.status_card.md_bg_color = [0.4, 0.1, 0.1, 1]
        self.status_label.text = f"⚠️ ВНИМАНИЕ: Скрытый пред-шторм!\nВероятность срыва: {probability}%. Включена защита."

    def show_safe_ui(self):
        self.status_card.md_bg_color = [0.1, 0.15, 0.12, 1]
        self.status_label.text = f"Щит AegisNeuro активен.\nОрганизм в полной безопасности ({self.gender_profile.upper()})."

    def set_male_profile(self, instance):
        self.gender_profile = "male"
        self.male_btn.md_bg_color = [0, 0.6, 0.8, 1]
        self.female_btn.theme_text_color = "Custom"
        self.female_btn.text_color = [1, 1, 1, 0.6]

    def set_female_profile(self, instance):
        self.gender_profile = "female"
        self.male_btn.md_bg_color = [0.2, 0.2, 0.2, 1]
        self.female_btn.theme_text_color = "Custom"
        self.female_btn.text_color = [1, 0.3, 0.6, 1]

    def mobile_lifecycle_loop(self, dt):
        if self.scan_timer > 0:
            self.scan_timer -= 1
            self.status_label.text = f"ИДЕТ ЗАМЕР ВОЛНЫ КРОВОТОКА... Осталось: {self.scan_timer} сек."
            if self.scan_timer == 0:
                self.on_scan_complete()
            return

        if self.current_stress > 65:
            self.current_stress -= random.randint(1, 2)

        mock_rmssd = int(20 + (500 / self.current_stress) * 5)

        self.metrics_label.text = f"Индекс Стресса: {self.current_stress} у.е.\nПарасимпатика (RMSSD): {mock_rmssd} ms"

        if self.current_stress > 250:
            self.show_alert_ui(78)
        else:
            self.show_safe_ui()


class AegisNeuroMobileApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        return AegisNeuroMobileScreen()


if __name__ == "__main__":
    AegisNeuroMobileApp().run()