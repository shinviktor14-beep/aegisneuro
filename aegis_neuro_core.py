import logging
import threading
import queue
import time
from bio_dsp import BioSignalProcessor
from bio_controller import BioFeedbackController
from advanced_audio import AdvancedNeuroAudioEngine
from ai_orchestrator import AICognitiveOrchestrator

log = logging.getLogger(__name__)

class AegisNeuroEngine:
    def __init__(self):
        log.info("Инициализация экосистемы AegisNeuro v1.0...")
        
        # Единая шина обмена данными (Data Broker)
        self.data_queue = queue.Queue()
        
        # Подключение всех слоев архитектуры AegisNeuro
        self.dsp = BioSignalProcessor()
        self.bio_controller = BioFeedbackController()
        self.audio_engine = AdvancedNeuroAudioEngine(base_freq=120.0)
        self.ai_cognitive = AICognitiveOrchestrator()
        
        self.is_running = False

    def hardware_ingestion_layer(self):
        """[Слой 1] Имитация потока Polar H10 (заменяется на polar_ble.py)"""
        log.info("Поток сбора биоданных активен.")
        while self.is_running:
            # Имитируем получение сырого R-R интервала от сердца в ms
            # В реальности данные будут лететь из BLE-нотификаций напрямую в DSP
            mock_rr = int(800 + random.randint(-50, 50)) if time.time() % 20 > 10 else int(750 + random.randint(-5, 5))
            
            self.data_queue.put({
                'metric': 'raw_rr',
                'value': mock_rr
            })
            time.sleep(0.8) # Скорость пульса ~75 уд/мин

    def closed_loop_control_layer(self):
        """[Слой 2] Закрытый контур обратной связи AegisNeuro"""
        log.info("Контур биорегуляции запущен.")
        chunk_size = 1024
        current_freq = 10.0 # Базовая Альфа
        
        # Приветственное слово от ИИ на старте
        self.audio_engine.speak_in_background(
            "Система Эйджис Нейро активирована. Начинаю сканирование вегетативного тонуса."
        )
        
        while self.is_running:
            try:
                packet = self.data_queue.get(timeout=0.05)
                if packet['metric'] == 'raw_rr':
                    # 1. Скармливаем интервал в математический блок DSP
                    self.dsp.add_rr_interval(packet['value'])
                    
                    # 2. Высчитываем маркеры стресса и боли
                    stress_idx = self.dsp.calculate_baevsky_stress_index()
                    rmssd = self.dsp.calculate_rmssd()
                    
                    # 3. ИИ принимает решение по корректировке частоты звука
                    new_freq, action_text = self.bio_controller.update_frequency(stress_idx)
                    current_freq = new_freq
                    
            except queue.Empty:
                pass

            # 4. Непрерывный синтез защитного звукового поля
            audio_chunk = self.audio_engine.generate_ambient_space_wave(
                target_brain_freq=current_freq, 
                chunk_size=chunk_size
            )
            self.stream_write_safe(audio_chunk)

    def stream_write_safe(self, chunk):
        try:
            self.audio_engine.stream.write(chunk)
        except Exception:
            log.debug("stream_write_safe: audio write failed", exc_info=True)

    def start_defense_session(self, duration=30):
        """Запуск защитной нейро-сессии AegisNeuro"""
        self.is_running = True
        
        self.t1 = threading.Thread(target=self.hardware_ingestion_layer, daemon=True)
        self.t2 = threading.Thread(target=self.closed_loop_control_layer, daemon=True)
        
        log.info("ДОБРО ПОЖАЛОВАТЬ В AEGISNEURO OS v1.0")
        
        self.t1.start()
        self.t2.start()
        
        time.sleep(duration)
        self.stop_session()

    def stop_session(self):
        log.info("Сессия AegisNeuro корректно завершена.")
        self.is_running = False
        self.audio_engine.speak_in_background("Сессия завершена. Ваш иммунный щит укреплен.")
        time.sleep(1.0)

if __name__ == "__main__":
    import random # только для мок-данных в тесте
    core = AegisNeuroEngine()
    core.start_defense_session(duration=15)