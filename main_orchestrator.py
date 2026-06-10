import threading
import queue
import time
from bio_controller import BioFeedbackController
from audio_engine import NeuroAudioEngine

class NeuroLearnOrchestrator:
    def __init__(self):
        # Очередь для передачи сырых биоданных в аналитический блок
        self.raw_data_queue = queue.Queue()
        
        # Инициализируем наши модули
        self.bio_controller = BioFeedbackController()
        self.audio_engine = NeuroAudioEngine(base_freq=150.0)
        
        self.is_running = False

    def hardware_ingestion_worker(self):
        """
        ПОТОК 1: Сбор данных. 
        Сейчас он имитирует Polar H10, а когда приедет пояс — 
        сюда встанет реальный BLE-клиент.
        """
        print("[Hardware] Поток сбора биоданных запущен.")
        while self.is_running:
            # Получаем имитационные данные стресса из нашего контроллера
            mock_stress_index = self.bio_controller.get_mock_polar_data()
            
            # Кладем данные в очередь на обработку
            self.raw_data_queue.put({
                'timestamp': time.time(),
                'metric': 'stress_index',
                'value': mock_stress_index
            })
            
            # Polar H10 шлет данные R-R интервалов постоянно, 
            # но индекс стресса мы пересчитываем раз в 1-2 секунды
            time.sleep(1.0)

    def brain_feedback_loop_worker(self):
        """
        ПОТОК 2: Аналитика и Логика ИИ.
        Забирает данные из очереди, принимает решение и управляет звуком.
        """
        print("[AI Engine] Поток закрытого контура обратной связи запущен.")
        chunk_size = 1024
        current_target_freq = 12.0 # Стартуем с легкого Альфа
        
        while self.is_running:
            try:
                # Проверяем, появились ли новые данные от датчиков (ждем максимум 100мс)
                data_packet = self.raw_data_queue.get(timeout=0.1)
                
                if data_packet['metric'] == 'stress_index':
                    stress = data_packet['value']
                    
                    # ИИ-контроллер анализирует стресс и выносит вердикт
                    new_freq, action_text = self.bio_controller.update_frequency(stress)
                    
                    if new_freq != current_target_freq:
                        current_target_freq = new_freq
                        print(f"\n[ИИ Модуляция] Стресс: {stress} у.е. -> {action_text}")
            
            except queue.Empty:
                # Если новых данных в эту секунду нет, просто продолжаем генерировать текущую частоту
                pass

            # Генерируем аудио-чанк для наушников
            # Звук должен генерироваться непрерывно, без задержек
            audio_data = self.audio_engine.generate_binaural_chunk(
                target_brain_freq=current_target_freq, 
                chunk_size=chunk_size
            )
            self.audio_engine.stream.write(audio_data)

    def start_session(self, duration_sec=20):
        """Запуск всей сессии биорегуляции"""
        self.is_running = True
        
        # Запускаем асинхронные потоки
        self.t1 = threading.Thread(target=self.hardware_ingestion_worker, daemon=True)
        self.t2 = threading.Thread(target=self.brain_feedback_loop_worker, daemon=True)
        
        print("=== СИСТЕМА НЕЙРОРЕГУЛЯЦИИ ЗАПУЩЕНА ===")
        self.t1.start()
        self.t2.start()
        
        # Держим главный поток активным, пока идет сессия
        time.sleep(duration_sec)
        self.stop_session()

    def stop_session(self):
        print("\n=== ОСТАНОВКА СЕССИИ ===")
        self.is_running = False
        time.sleep(0.5) # Даем потокам время корректно завершиться
        self.audio_engine.stop()

if __name__ == "__main__":
    orchestrator = NeuroLearnOrchestrator()
    orchestrator.start_session(duration_sec=25)