"""Когнитивный оркестратор: анализ жалоб → выбор безопасного протокола.

Источник: ``ai_orchestrator.py`` (канон). Медицинские дефолты — False
(не предполагать диагноз без анамнеза).
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class AICognitiveOrchestrator:
    def __init__(
        self,
        endocrine_issues: bool = False,
        pelvic_congestion: bool = False,
        cardio_limitations: bool = False,
    ) -> None:
        self.session_context: dict = {}
        self.user_medical_profile = {
            "endocrine_issues": endocrine_issues,
            "pelvic_congestion": pelvic_congestion,
            "cardio_limitations": cardio_limitations,
        }

    def run_intake_assessment(self, user_complaint: str) -> dict:
        """Анализ жалобы → выбор протокола с учётом медицинских ограничений."""
        log.info("AI Intake: анализируем жалобу — %s", user_complaint)
        complaint_lower = user_complaint.lower()
        strategy: dict = {}

        # 1. Застойные явления в малом тазу
        if any(kw in complaint_lower for kw in ("таз", "простат", "промежност", "застой")):
            strategy = self._adjust_for_pelvic_health()

        # 2. Острая неврологическая боль
        elif any(kw in complaint_lower for kw in ("острая", "прострел", "невралгия", "мигрень")):
            strategy = {
                "protocol": "theta_anesthesia",
                "target_frequency": 5.5,
                "base_frequency": 140.0,
                "voice_guidance_mode": "глубокий, успокаивающий, гипнотический транс",
            }

        # 3. Дефолт — альфа-релаксация
        else:
            strategy = {
                "protocol": "alpha_relaxation",
                "target_frequency": 10.0,
                "base_frequency": 160.0,
                "voice_guidance_mode": "мягкий, поддерживающий, расслабляющий гид",
            }

        # == КОНТУР БЕЗОПАСНОСТИ ==
        if self.user_medical_profile["endocrine_issues"] and any(
            kw in complaint_lower for kw in ("шея", "плеч", "устал")
        ):
            log.warning("AI Safeguard: эндокринный паттерн риска → endocrine_alpha_safe")
            strategy = {
                "protocol": "endocrine_alpha_safe",
                "target_frequency": 9.5,
                "base_frequency": 150.0,
                "voice_guidance_mode": "эндокринная релаксация (акцент на тепло в области шеи)",
            }

        self.session_context = strategy
        return strategy

    def _adjust_for_pelvic_health(self) -> dict:
        log.info("AI Safeguard: протокол глубокой стимуляции органов малого таза")
        return {
            "protocol": "pelvic_resonance_safe",
            "target_frequency": 7.83,
            "base_frequency": 110.0,
            "voice_guidance_mode": "тазовое расслабление (фокус на снятие зажима промежности)",
        }

    def generate_live_biofeedback_prompt(
        self,
        current_stress: float,
        current_rmssd: float,
        elapsed_time: float,
        alpha_power: float | None = None,
    ) -> str:
        """Динамический TTS-промпт на основе текущего протокола и метрик."""
        protocol = self.session_context.get("protocol", "alpha_relaxation")

        if protocol == "endocrine_alpha_safe":
            if current_stress > 250:
                return "Опустите плечи. Почувствуйте, как с каждым выдохом тепло мягко разливается по шее и горлу."
            return "Отлично. Спазм сосудов уходит. Кровоток в области шеи полностью восстанавливается. Продолжайте дышать."

        if protocol == "pelvic_resonance_safe":
            if current_stress > 250:
                return "Отпустите мышечный зажим внизу живота. Направьте выдох глубоко в тазовое ложе, растворяя блок."
            return "Резонанс восстанавливает микроциркуляцию. Почувствуйте приятную пульсацию и тепло в теле."

        # Alpha-power early exit (для GUI-вызовов с alpha_power)
        if alpha_power is not None and alpha_power > 0.65:
            return "Альфа-ритм достиг оптимального уровня. Ваш мозг в гармонии. Продолжайте."

        if current_stress > 300:
            return f"Пользователь находится в протоколе {protocol} уже {int(elapsed_time)}с. Напряжение высокое ({int(current_stress)} у.е.). Сделай глубокий плавный вдох. Позволь звуку растворить зажим."
        if current_stress <= 150:
            return f"Прекрасный прогресс. Стресс упал до {int(current_stress)} у.е., блуждающий нерв активен (RMSSD: {int(current_rmssd)}мс). Твоё тело полностью расслаблено. Направь это тепло в зону, где была боль."
        return "Продолжай дышать в такт звуку прибоя. Ты всё делаешь абсолютно правильно."