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
import os
import json
import numpy as np

# Импортируем наши ядра
from aegis_ppg_processor import AegisPPGProcessor
from aegis_audio_engine import AegisAudioEngine
from android_camera import AndroidCameraBridge


# ==============================================================================
# НАСТОЯЩИЙ ИИ-МОДУЛЬ ПОДКРЕПЛЕНИЯ (Q-Learning Core)
# ==============================================================================
class AegisRLBrain:
    def __init__(self, actions_list=None, alpha=0.2, gamma=0.9, epsilon=0.3):
        self.actions = actions_list if actions_list else list(np.arange(4.0, 12.5, 0.5))
        self.alpha = alpha   
        self.gamma = gamma   
        self.epsilon = epsilon 
        self.num_states = 4
        self.q_table = np.zeros((self.num_states, len(self.actions)))
        self.profile_path = "aegis_user_brain_profile.json"
        self.load_profile()

    def get_state_index(self, stress_index):
        if stress_index < 150: return 0
        elif stress_index <= 300: return 1
        elif stress_index <= 500: return 2
        else: return 3

    def choose_frequency(self, current_stress):
        state_idx = self.get_state_index(current_stress)
        if random.uniform(0, 1) < self.epsilon:
            action_idx = random.randint(0, len(self.actions) - 1)
            strategy = "Разведка ИИ (Поиск новых частот)"
        else:
            action_idx = np.argmax(self.q_table[state_idx])
            strategy = "Адаптивный личный резонанс"
        return self.actions[action_idx], action_idx, strategy

    def learn(self, old_stress, action_idx, new_stress, rmssd_growth):
        old_state = self.get_state_index(old_stress)
        new_state = self.get_state_index(new_stress)
        
        stress_delta = old_stress - new_stress
        reward = stress_delta + (rmssd_growth * 2)
        
        if stress_delta < 0:
            reward -= 50  

        old_q = self.q_table[old_state, action_idx]
        max_future_q = np.max(self.q_table[new_state])
        self.q_table[old_state, action_idx] = old_q + self.alpha * (reward + self.gamma * max_future_q - old_q)

    def save_profile(self):
        data = {"q_table": self.q_table.tolist(), "actions": self.actions}
        with open(self.profile_path, "w") as f:
            json.dump(data, f)

    def load_profile(self):
        if os.path.exists(self.profile_path):
            with open(self.profile_path, "r") as f:
                data = json.load(f)
                self.q_table = np.array(data["q_table"])


# ==============================================================================
# МОДЕРНИЗИРОВАННЫЙ СКАРЛ-ПРЕДИКТОР ПОД ЭКСПРЕСС-ОКНО (Твой файл с адаптацией)
# ==============================================================================
class AegisStormPredictor:
    def __init__(self):
        self.baseline_path = "aegis_historical_baseline.json"
        self.baseline = {
            "avg_rmssd": 35.0,      
            "avg_stress_idx": 120.0 
        }
        self.load_baseline()

    def load_baseline(self):
        if os.path.exists(self.baseline_path):
            with open(self.baseline_path, "r") as f:
                self.baseline = json.load(f)
            print("[Aegis-Predictor] Исторический базовый профиль ВСР загружен.")

    def update_baseline_live(self, new_rmssd, new_stress):
        """Плавная адаптация нейро-базы под стареющие/меняющиеся параметры тела"""
        # Вес нового замера 10%, вес старой памяти 90%
        self.baseline["avg_rmssd"] = float(self.baseline["avg_rmssd"] * 0.9 + new_rmssd * 0.1)
        self.baseline["avg_stress_idx"] = float(self.baseline["avg_stress_idx"] * 0.9 + new_stress * 0.1)
        with open(self.baseline_path, "w") as f:
            json.dump(self.baseline, f)
        print("[Aegis-Predictor] Живой нейро-баланс пользователя пересчитан и сохранен.")

    def analyze_morning_test(self, rr_intervals):
        # Адаптировано: для 15-секундного экспресс-сигнала снижаем ценз до 10 интервалов
        if len(rr_intervals) < 10:
            return {"status": "INSUFFICIENT_DATA", "probability_pct": 0, "triggers": ["Недостаточно пульсовых волн"]}

        rr_diff = np.diff(rr_intervals)
        current_rmssd = np.sqrt(np.mean(rr_diff ** 2))
        
        amo = self._calculate_amplitude_of_mode(rr_intervals)
        mx_dmn = (np.max(rr_intervals) - np.min(rr_intervals)) / 1000.0 
        if mx_dmn == 0: mx_dmn = 0.05
        current_stress_idx = (amo) / (2 * mx_dmn * (np.median(rr_intervals)/1000.0))

        # Деление короткого массива на 3 микро-чанка для вычисления альтернаций
        chunks = np.array_split(rr_intervals, 3)
        chunk_rmssds = []
        for ch in chunks:
            if len(ch) > 1:
                chunk_rmssds.append(np.sqrt(np.mean(np.diff(ch) ** 2)))
        
        rmssd_alternation_coef = np.std(chunk_rmssds) / np.mean(chunk_rmssds) if len(chunk_rmssds) > 0 else 0

        storm_score = 0
        reasons = []

        rmssd_drop_pct = ((self.baseline["avg_rmssd"] - current_rmssd) / self.baseline["avg_rmssd"]) * 100
        if rmssd_drop_pct > 20: # Порог адаптирован до 20%
            storm_score += 40
            reasons.append(f"Падение тонуса Vagus на {int(rmssd_drop_pct)}% ниже нормы")

        if current_stress_idx > self.baseline["avg_stress_idx"] * 1.5:
            storm_score += 30
            reasons.append("Скрытая гиперсимпатикотония (тревога ЦНС)")

        if rmssd_alternation_coef > 0.12:
            storm_score += 30
            reasons.append("Хаотические микро-альтернации капиллярной волны")

        storm_probability = min(max(storm_score, 0), 100)

        status = "CLEAR"
        if storm_probability >= 70:
            status = "STORM_ALERT"
        elif 40 <= storm_probability < 70:
            status = "WARNING"

        # Если система стабильна, подмешиваем новые точки в адаптивный профиль
        if status == "CLEAR":
            self.update_baseline_live(current_rmssd, current_stress_idx)

        return {
            "status": status,
            "storm_probability_pct": storm_probability,
            "metrics": {
                "rmssd": round(current_rmssd, 1),
                "stress_index": int(current_stress_idx),
                "alternation_index": round(rmssd_alternation_coef, 3)
            },
            "triggers": reasons,
            "prediction_window": "2-3 часа"
        }

    def _calculate_amplitude_of_mode(self, rr_intervals):
        counts, bins = np.histogram(rr_intervals, bins=10) # 10 корзин оптимальнее для экспресс-замера
        max_idx = np.argmax(counts)
        return (counts[max_idx] / len(rr_intervals)) * 100


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
        # Camera2-мост — на Android читает кадры, на десктопе no-op.
        self.camera_bridge = AndroidCameraBridge()
        self.camera_bridge.request_permission()
        self.camera_bridge.start_capture()
        self.hardware_bridge = AndroidHardwareBridge(self.camera_bridge)
        self.predictor = AegisStormPredictor()  # Инициализируем глубокий предиктор

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

        # Вместо kivy.uix.camera — текстовая заглушка с состоянием камеры
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
        # На случай если в KivyMD 1.1.1 нет MDFlatButton — заменяем на MDRaisedButton
        try:
            self.female_btn = MDFlatButton(text="Женский профиль", theme_text_color="Custom", text_color=[1, 1, 1, 0.6], on_release=self.set_female_profile)
        except Exception:  # noqa: BLE001
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
        # 30 Гц pull PPG-кадров с AndroidCameraBridge
        Clock.schedule_interval(self._tick_ppg, 1.0 / 30.0)

    def _tick_ppg(self, dt):
        """30 раз в секунду: забираем у камеры последнее «среднее красное» и скармливаем в PPG."""
        try:
            mean_red = self.camera_bridge.get_mean_red()
        except Exception:  # noqa: BLE001
            return
        if mean_red <= 0.0:
            return
        try:
            self.ppg_processor.process_frame(mean_red)
        except Exception as exc:  # noqa: BLE001
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
        
        # Запускаем твой адаптированный Баевский/Скаргль-анализ
        prediction = self.predictor.analyze_morning_test(rr_data)
        
        if prediction["status"] == "INSUFFICIENT_DATA":
            self.status_card.md_bg_color = [0.35, 0.15, 0.15, 1]
            self.status_label.text = f"⚠️ ЗАМЕР СОРВАН.\n{prediction['triggers'][0]}. Повторите замер."
            return

        # Извлекаем честные посчитанные метрики из предиктора
        self.current_rmssd = prediction["metrics"]["rmssd"]
        self.current_stress = prediction["metrics"]["stress_index"]

        # ОБУЧЕНИЕ ИИ НА КОРРЕКТНЫХ ДАННЫХ
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

        # Выводим на экран глубокую предиктивную аналитику
        if prediction["status"] == "STORM_ALERT":
            self.status_card.md_bg_color = [0.4, 0.12, 0.12, 1]
            # Вытягиваем первый критический триггер для пользователя
            anomaly_text = prediction["triggers"][0] if prediction["triggers"] else "Хаос ЦНС"
            self.status_label.text = f"⚠️ УГРОЗА ШТОРМА ({prediction['storm_probability_pct']}% / Окно: 2ч)\n{anomaly_text}.\nИИ подает: {self.active_frequency} Гц"
        elif prediction["status"] == "WARNING":
            self.status_card.md_bg_color = [0.35, 0.22, 0.05, 1] # Оранжевый варнинг
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
        # Корректно освобождаем камеру и аудио при выходе из приложения.
        screen = self.root
        if screen is None:
            return
        try:
            if getattr(screen, "camera_bridge", None) is not None:
                screen.camera_bridge.stop_capture()
        except Exception as exc:  # noqa: BLE001
            print(f"[Aegis-System] camera stop: {exc}")
        try:
            if getattr(screen, "audio_engine", None) is not None:
                screen.audio_engine.stop_tone()
        except Exception as exc:  # noqa: BLE001
            print(f"[Aegis-System] audio stop: {exc}")


if __name__ == "__main__":
    try:
        AegisNeuroMobileApp().run()
    finally:
        print("[Aegis-System] Закрытие приложения. Освобождение ресурсов...")