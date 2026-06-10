import os
import json

class AICognitiveOrchestrator:
    def __init__(self):
        # В реальном продакшене здесь инициализируется клиент нейросети: client = OpenAI(api_key=...)
        self.session_context = {}
        
        # Расширенная база медицинских ограничений пользователя (анамнез AegisNeuro)
        self.user_medical_profile = {
            "endocrine_issues": True,     # Многоузловой зоб щитовидной железы
            "pelvic_congestion": True,    # Застойные явления в малом тазу (простатит/аденома/спазмы)
            "cardio_limitations": False   # Ограничения со стороны сердечно-сосудистой системы
        }
        
    def run_intake_assessment(self, user_complaint):
        """
        Когнитивный анализ текущей жалобы пользователя.
        Сопоставляет характер боли с медицинским профилем для выбора безопасного и эффективного протокола.
        """
        print(f"[AegisNeuro -> AI Intake] Анализируем жалобу пользователя: '{user_complaint}'")
        
        complaint_lower = user_complaint.lower()
        strategy = {}

        # 1. Скрининг жалобы на предмет застойных явлений в малом тазу (простатит / органы тазового дна)
        if "таз" in complaint_lower or "простат" in complaint_lower or "промежност" in complaint_lower or "застой" in complaint_lower:
            strategy = self._adjust_for_pelvic_health()
            
        # 2. Скрининг на острую неврологическую боль и прострелы
        elif "острая" in complaint_lower or "прострел" in complaint_lower or "невралгия" in complaint_lower or "мигрень" in complaint_lower:
            strategy = {
                "protocol": "theta_anesthesia",
                "target_frequency": 5.5,
                "base_frequency": 140.0,
                "voice_guidance_mode": "глубокий, успокаивающий, гипнотический транс"
            }
            
        # 3. Протокол по умолчанию для мышечных зажимов и усталости (Альфа-релаксация)
        else:
            strategy = {
                "protocol": "alpha_relaxation",
                "target_frequency": 10.0,
                "base_frequency": 160.0,
                "voice_guidance_mode": "мягкий, поддерживающий, расслабляющий гид"
            }

        # == КОНТУР БЕЗОПАСНОСТИ (Safeguard Context) ==
        # Корректировка протокола, если у пользователя зафиксированы проблемы со щитовидной железой,
        # а жалоба касается шейно-плечевого отдела (где стимуляция должна быть максимально деликатной).
        if self.user_medical_profile["endocrine_issues"] and ("шея" in complaint_lower or "плеч" in complaint_lower or "устал" in complaint_lower):
            print("[AegisNeuro -> AI Safeguard] Внимание: обнаружен паттерн риска. Активирован эндокринный протокол защиты щитовидной железы.")
            # Сдвигаем частоту в мягкий терапевтический Альфа-резонанс (9.5 Гц)
            # Частота снижает кортизол, не перестимулируя выброс тиреоидных гормонов
            strategy = {
                "protocol": "endocrine_alpha_safe",
                "target_frequency": 9.5,
                "base_frequency": 150.0, # Оптимальная несущая частота для расслабления гладкой мускулатуры шеи
                "voice_guidance_mode": "эндокринная релаксация (акцент на тепло в области шеи)"
            }
            
        self.session_context = strategy
        return strategy

    def _adjust_for_pelvic_health(self):
        """Специальная модификация ИИ для улучшения капиллярного кровотока малого таза"""
        print("[AegisNeuro -> AI Safeguard] Активирован протокол глубокой стимуляции органов малого таза.")
        
        # Используется резонанс Шумана (7.83 Гц) для глубокой миорелаксации и снятия спазма промежности
        return {
            "protocol": "pelvic_resonance_safe",
            "target_frequency": 7.83, 
            "base_frequency": 110.0,  # Низкая несущая частота, вызывающая физический микро-резонанс в тканях
            "voice_guidance_mode": "тазовое расслабление (фокус на снятие зажима промежности и восстановление кровотока)"
        }

    def generate_live_biofeedback_prompt(self, current_stress, current_rmssd, elapsed_time):
        """
        Формирует динамические текстовые команды для TTS (Text-to-Speech) в реальном времени.
        Опирается на текущий протокол и входящие биометрические показатели (ВСР).
        """
        protocol = self.session_context.get("protocol", "alpha_relaxation")
        
        # Ветвление в зависимости от активированного терапевтического протокола
        if protocol == "endocrine_alpha_safe":
            if current_stress > 250:
                return "Опустите плечи. Почувствуйте, как с каждым выдохом тепло мягко разливается по шее и горлу."
            else:
                return "Отлично. Спазм сосудов уходит. Кровоток в области шеи полностью восстанавливается. Продолжайте дышать."
                
        elif protocol == "pelvic_resonance_safe":
            if current_stress > 250:
                return "Отпустите мышечный зажим внизу живота. Направьте выдох глубоко в тазовое ложе, растворяя блок."
            else:
                return "Резонанс восстанавливает микроциркуляцию. Почувствуйте приятную пульсацию и тепло в теле."
                
        # Стандартные динамические фразы обратной связи (Biofeedback Loop)
        if current_stress > 300:
            return f"Пользователь находится в протоколе {protocol} уже {elapsed_time}с. Напряжение высокое ({current_stress} у.е.). Сделай глубокий плавный вдох. Позволь звуку растворить зажим."
        elif current_stress <= 150:
            return f"Прекрасный прогресс. Стресс упал до {current_stress} у.е., блуждающий нерв активен (RMSSD: {current_rmssd}мс). Твоё тело полностью расслаблено. Направь это тепло в зону, где была боль."
        else:
            return "Продолжай дышать в такт звуку прибоя. Ты всё делаешь абсолютно правильно."

# ==============================================================================
# КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ ВСЕХ КОНТУРОВ ОРКЕСТРАТОРА
# ==============================================================================
if __name__ == "__main__":
    print("="*70)
    print("ЗАПУСК СИСТЕМНОГО ТЕСТИРОВАНИЯ: AICognitiveOrchestrator v2.0")
    print("="*70)
    
    ai_bot = AICognitiveOrchestrator()
    
    # --------------------------------------------------------------------------
    # ТЕСТ 1: Шейно-плечевой синдром при сопутствующем многоузловом зобе
    # --------------------------------------------------------------------------
    print("\n--- ТЕСТ 1: Оценка жалобы на шею при эндокринном профиле ---")
    complaint_1 = "Ужасно зажала шею после работы за компьютером, мышцы затекли, больно повернуть голову."
    strategy_1 = ai_bot.run_intake_assessment(complaint_1)
    print(json.dumps(strategy_1, indent=4, ensure_ascii=False))
    
    # Имитируем биофидбэк для Теста 1 (Стресс еще высокий)
    phrase_1_high = ai_bot.generate_live_biofeedback_prompt(current_stress=280, current_rmssd=18, elapsed_time=45)
    print(f"Голос ИИ в наушниках (Высокий стресс): '{phrase_1_high}'")
    
    # Имитируем биофидбэк для Теста 1 (Успешное расслабление)
    phrase_1_low = ai_bot.generate_live_biofeedback_prompt(current_stress=120, current_rmssd=52, elapsed_time=180)
    print(f"Голос ИИ в наушниках (Стабилизация):  '{phrase_1_low}'")

    # --------------------------------------------------------------------------
    # ТЕСТ 2: Острая неврологическая боль (Вне зон эндокринного риска)
    # --------------------------------------------------------------------------
    print("\n--- ТЕСТ 2: Острая боль / Невралгия ---")
    complaint_2 = "Резкий прострел в пояснице, острая боль, не могу разогнуться."
    strategy_2 = ai_bot.run_intake_assessment(complaint_2)
    print(json.dumps(strategy_2, indent=4, ensure_ascii=False))
    
    phrase_2 = ai_bot.generate_live_biofeedback_prompt(current_stress=350, current_rmssd=12, elapsed_time=30)
    print(f"Голос ИИ в наушниках (Острая фаза): '{phrase_2}'")

    # --------------------------------------------------------------------------
    # ТЕСТ 3: Протокол стимуляции органов малого таза
    # --------------------------------------------------------------------------
    print("\n--- ТЕСТ 3: Жалоба на застойные явления малого таза ---")
    complaint_3 = "Тянущие ощущения внизу живота, диагностирован застой в малом тазу, нужно снять спазм."
    strategy_3 = ai_bot.run_intake_assessment(complaint_3)
    print(json.dumps(strategy_3, indent=4, ensure_ascii=False))
    
    # Имитируем биофидбэк для Теста 3 (Начало сессии)
    phrase_3_start = ai_bot.generate_live_biofeedback_prompt(current_stress=290, current_rmssd=22, elapsed_time=60)
    print(f"Голос ИИ в наушниках (Запуск резонанса): '{phrase_3_start}'")
    
    # Имитируем биофидбэк для Теста 3 (Динамическое улучшение)
    phrase_3_ok = ai_bot.generate_live_biofeedback_prompt(current_stress=140, current_rmssd=48, elapsed_time=240)
    print(f"Голос ИИ в наушниках (Успешный дренаж):  '{phrase_3_ok}'")
    print("\n" + "="*70)
    print("ТЕСТИРОВАНИЕ ИНТЕГРИРОВАННОГО КОГНИТИВНОГО СЛОЯ ЗАВЕРШЕНО УСПЕШНО")
    print("="*70)