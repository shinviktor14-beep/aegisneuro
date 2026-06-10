"""AegisSession: склеивает камеру, DSP, RL-агент и аудио в один цикл.

Использование из UI::

    session = AegisSession()
    session.start_audio()
    result = session.ingest_frame(mean_red)        # каждый кадр
    ...
    scan = session.complete_scan(rr_intervals)     # по завершении замера
    session.apply_to_audio(scan["frequency"])      # вручную или автоматически
    session.shutdown()
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis import config
from aegis.core.audio import AegisAudioEngine, VoiceGuide
from aegis.core.dsp import BioSignalProcessor
from aegis.core.longevity import LongevityTrendAnalyzer
from aegis.core.marketplace import AegisMarketplace
from aegis.core.ppg import AegisPPGProcessor
from aegis.core.rl_brain import AegisRLBrain
from aegis.core.storm import StormPredictor


@dataclass
class ScanResult:
    """То, что UI получает на руки по завершении одного замера."""

    frequency: float
    strategy: str
    rmssd: float
    stress_index: float
    storm: dict
    upsell: dict | None = None
    health: str = "OK"
    message: str = ""


@dataclass
class AegisSession:
    dsp: BioSignalProcessor = field(default_factory=BioSignalProcessor)
    ppg: AegisPPGProcessor = field(default_factory=AegisPPGProcessor)
    brain: AegisRLBrain = field(default_factory=AegisRLBrain)
    storm: StormPredictor = field(default_factory=StormPredictor)
    longevity: LongevityTrendAnalyzer = field(default_factory=LongevityTrendAnalyzer)
    marketplace: AegisMarketplace = field(default_factory=AegisMarketplace)

    audio: AegisAudioEngine = field(default_factory=AegisAudioEngine)
    voice: VoiceGuide = field(
        default_factory=lambda: VoiceGuide(music_volume_ref=[config.CARRIER_FREQ_HZ])
    )

    # Текущее состояние сессии
    current_stress: float = 120.0
    current_rmssd: float = 35.0
    old_stress: float = 120.0
    old_rmssd: float = 35.0
    current_action_idx: int = 0
    active_frequency: float = 8.0
    scan_count: int = 0
    gender_profile: str = "male"

    # ------------------------------------------------------------------ audio
    def start_audio(self) -> None:
        self.audio.start()

    def stop_audio(self) -> None:
        self.audio.stop()

    def apply_frequency(self, hz: float) -> None:
        self.active_frequency = float(hz)
        self.audio.set_frequency(hz)

    def speak(self, text: str) -> None:
        self.voice.speak(text)

    # ------------------------------------------------------------------ ingest
    def ingest_frame(self, mean_red: float) -> str:
        """Один кадр с камеры. Возвращает статус сигнала (OK/WAITING/...)."""
        self.ppg.process_frame(mean_red)
        return self.ppg.check_signal_quality()

    def complete_scan(self, rr_intervals: list[int] | None = None) -> ScanResult:
        """Завершить замер PPG, обучить RL, выбрать частоту, вернуть результат."""
        if rr_intervals is None:
            rr_intervals = self.ppg.get_rr_intervals()

        storm_result = self.storm.analyze(rr_intervals)
        status = storm_result["status"]

        if status == "INSUFFICIENT_DATA":
            return ScanResult(
                frequency=self.active_frequency,
                strategy="—",
                rmssd=0.0,
                stress_index=0.0,
                storm=storm_result,
                health="INSUFFICIENT_DATA",
                message=storm_result["triggers"][0],
            )

        self.current_rmssd = storm_result["metrics"]["rmssd"]
        self.current_stress = storm_result["metrics"]["stress_index"]

        rmssd_growth = self.current_rmssd - self.old_rmssd
        self.brain.learn(
            old_stress=self.old_stress,
            action_idx=self.current_action_idx,
            new_stress=self.current_stress,
            rmssd_growth=rmssd_growth,
        )
        self.brain.save_profile()

        new_freq, self.current_action_idx, strategy = self.brain.choose_frequency(
            self.current_stress
        )
        self.apply_frequency(new_freq)
        self.old_stress = self.current_stress
        self.old_rmssd = self.current_rmssd
        self.scan_count += 1

        if status == "STORM_ALERT":
            health = "STORM_ALERT"
            message = (
                f"⚠️ УГРОЗА ШТОРМА ({storm_result['storm_probability_pct']}% / Окно: 2ч)\n"
                f"{storm_result['triggers'][0] if storm_result['triggers'] else 'Хаос ЦНС'}.\n"
                f"ИИ подает: {new_freq} Гц"
            )
        elif status == "WARNING":
            health = "WARNING"
            message = (
                f"Напряжение систем ({storm_result['storm_probability_pct']}%)\n"
                f"Рекомендуется сессия релаксации.\n"
                f"Частота ИИ: {new_freq} Гц"
            )
        else:
            health = "OK"
            message = (
                f"Щит активен. Вегетативный баланс в норме.\n"
                f"ИИ транслирует частоту: {new_freq} Гц"
            )

        upsell = self.marketplace.get_upsell_trigger_message(
            user_scan_count=self.scan_count,
            average_stress=self.current_stress,
        )

        return ScanResult(
            frequency=new_freq,
            strategy=strategy,
            rmssd=self.current_rmssd,
            stress_index=self.current_stress,
            storm=storm_result,
            upsell=upsell,
            health=health,
            message=message,
        )

    def reset_scan(self) -> None:
        self.ppg.reset()
        self.dsp.reset()

    def shutdown(self) -> None:
        self.stop_audio()
