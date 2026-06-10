from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivy.clock import Clock
import math
import random

# ==============================================================================
# ЗАГЛУШКИ ДЛЯ ТЯЖЕЛЫХ ИИ-МОДУЛЕЙ (Если внешние файлы еще не подключены в сборку)
# ==============================================================================
class AegisRLBrain:
    def __init__(self):
        pass

class AegisStormPredictor:
    def __init__(self):
        pass
    def analyze_morning_test(self, rr_data):
        # Имитируем предиктивный анализ
        return {"status": "SAFE", "storm_probability_pct": 14}

# Имитация работы с сенсорами смартфона (PPG/Фонарик)
class HardwareBridgeStub:
    def enable_flashlight(self):
        print("[Android/iOS API] Вспышка камеры активирована для замера PPG.")
    def disable_flashlight(self):
        print("[Android/iOS API] Вспышка камеры выключена.")

class PPGProcessorStub:
    def get_rr_intervals(self):
        # Имитация массива RR-интервалов (мс) для ИИ
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
        
        # Инициализация ядер AegisNeuro
        self.ai_brain = AegisRLBrain()
        self.predictor = AegisStormPredictor()
        
        # Инициализация мостов к железу смартфона (Защита от падения в AttributeError)
        self.hardware_bridge = HardwareBridgeStub()
        self.ppg_processor = PPGProcessorStub()
        self.pulse_orb = PulseOrbStub()
        
        self.current_stress = 310
        self.gender_profile = "male"
        self.scan_timer = 0
        
        self.build_ui()

    def build_ui(self):
        # Главный вертикальный контейнер приложения
        main_layout = MDBoxLayout(orientation='vertical', padding=20, spacing=15)
        
        # 1. Шапка приложения
        self.title_label = MDLabel(
            text="AEGISNEURO OS v1.0",
            halign="center",
            font_style="H5",
            theme_text_color="Custom",
            text_color=[0, 1, 0.8, 1], # Неоново-бирюзовый
            size_hint_y=None,
            height=50
        )
        main_layout.add_widget(self.title_label)

        # 2. Виджет состояния / Мобильный Радар Шторма
        self.status_card = MDBoxLayout(
            orientation='vertical', 
            padding=15, 
            size_hint_y=None, 
            height=120,
            md_bg_color=[0.1, 0.12, 0.16, 1]
        )
        self.status_label = MDLabel(
            text="Статус щита: ГОТОВ К СКАНИРОВАНИЮ",
            halign="center",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1]
        )
        self.status_card.add_widget(self.status_label)
        main_layout.add_widget(self.status_card)

        # 3. Блок выбора биологического пола (Селектор профиля)
        gender_layout = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        
        self.male_btn = MDRaisedButton(
            text="Мужской профиль",
            md_bg_color=[0, 0.6, 0.8, 1],
            on_release=self.set_male_profile
        )
        self.female_btn = MDFlatButton(
            text="Женский профиль",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 0.6],
            on_release=self.set_female_profile
        )
        
        gender_layout.add_widget(self.male_btn)
        gender_layout.add_widget(self.female_btn)
        main_layout.add_widget(gender_layout)

        # 4. Телеметрия ВСР
        self.metrics_label = MDLabel(
            text="Индекс Стресса: -- у.е.\nПарасимпатика (RMSSD): -- ms",
            halign="center",
            font_style="Subtitle1",
            theme_text_color="Custom",
            text_color=[0.7, 0.7, 0.8, 1]
        )
        main_layout.add_widget(self.metrics_label)

        # 5. Главная кнопка управления сессией защиты
        self.action_btn = MDRaisedButton(
            text="ЗАПУСТИТЬ СКАНИРОВАНИЕ СУТОЧНОГО ЩИТА",
            pos_hint={"center_x": 0.5},
            md_bg_color=[0, 1, 0.4, 1], # Зеленый щит
            size_hint_x=0.9,
            height=60,
            on_release=self.start_scan
        )
        main_layout.add_widget(self.action_btn)

        self.add_widget(main_layout)
        
        # Запускаем мобильный цикл обновлений (1 раз в секунду)
        Clock.schedule_interval(self.mobile_lifecycle_loop, 1.0)

    def start_scan(self, *args):
        """Программная команда на включение замера через камеру смартфона"""
        self.hardware_bridge.enable_flashlight() 
        self.scan_timer = 10  # Демо-время замера изменено до 10 секунд для удобства тестирования
        self.status_card.md_bg_color = [0.1, 0.2, 0.3, 1]
        self.status_label.text = "СКАНИРОВАНИЕ БИО-ЩИТА: ПРИЛОЖИТЕ ПАЛЕЦ К КАМЕРЕ"
        self.pulse_orb.active = True 

    def on_scan_complete(self):
        """Вызывается по истечении таймера замера PPG"""
        self.hardware_bridge.disable_flashlight()
        self.pulse_orb.active = False
        
        rr_data = self.ppg_processor.get_rr_intervals()
        prediction = self.predictor.analyze_morning_test(rr_data)
    
        # Анализ результатов предиктора
        if self.current_stress > 250:
            self.show_alert_ui(84) # Передаем критический процент вероятности шторма
        else:
            self.show_safe_ui()

    def show_alert_ui(self, probability):
        self.status_card.md_bg_color = [0.4, 0.1, 0.1, 1] # Красный экран тревоги
        self.status_label.text = f"⚠️ ВНИМАНИЕ: Скрытый пред-шторм!\nВероятность срыва: {probability}%. Включена защита."

    def show_safe_ui(self):
        self.status_card.md_bg_color = [0.1, 0.15, 0.12, 1] # Зеленый щит активен
        self.status_label.text = f"Щит AegisNeuro активен.\nОрганизм в полной безопасности ({self.gender_profile.upper()})."

    def set_male_profile(self, instance):
        self.gender_profile = "male"
        self.male_btn.md_bg_color = [0, 0.6, 0.8, 1]
        self.female_btn.theme_text_color = "Custom"
        self.female_btn.text_color = [1, 1, 1, 0.6]
        print("[Mobile App] ИИ переключен на мужской профиль (Простата/Кардио).")

    def set_female_profile(self, instance):
        self.gender_profile = "female"
        self.male_btn.md_bg_color = [0.2, 0.2, 0.2, 1]
        self.female_btn.theme_text_color = "Custom"
        self.female_btn.text_color = [1, 0.3, 0.6, 1] # Розовый акцент для женщин
        print("[Mobile App] ИИ переключен на женский профиль (Эндокринный/Гинекология).")

    def mobile_lifecycle_loop(self, dt):
        """Мобильный жизненный цикл: опрос датчиков, ИИ-анализ, обновление экрана"""
        
        # Если идет активный замер PPG пальца на камере
        if self.scan_timer > 0:
            self.scan_timer -= 1
            self.status_label.text = f"ИДЕТ ЗАМЕР ВОЛНЫ КРОВОТОКА... Осталось: {self.scan_timer} сек."
            if self.scan_timer == 0:
                self.on_scan_complete()
            return

        # Имитируем плавное терапевтическое падение стресса во время работы приложения
        if self.current_stress > 65:
            self.current_stress -= random.randint(1, 2)
            
        mock_rmssd = int(20 + (500 / self.current_stress) * 5)

        # Вывод текущих метрик ВСР
        self.metrics_label.text = f"Индекс Стресса: {self.current_stress} у.е.\nПарасимпатика (RMSSD): {mock_rmssd} ms"

        # Автоматический предиктивный радар шторма (только вне режима сканирования)
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