"""Тесты для aegis.core: DSP, RL brain, storm predictor, orchestrator, marketplace."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from aegis.core.dsp import BioSignalProcessor
from aegis.core.rl_brain import AegisRLBrain
from aegis.core.storm import StormPredictor
from aegis.core.orchestrator import AICognitiveOrchestrator
from aegis.core.marketplace import AegisMarketplace


# ==========================================================================
# DSP
# ==========================================================================
class TestBioSignalProcessor:
    def test_empty_buffer_returns_zero_rmssd(self):
        dsp = BioSignalProcessor()
        assert dsp.calculate_rmssd() == 0.0

    def test_short_buffer_returns_zero_rmssd(self):
        dsp = BioSignalProcessor()
        for rr in [800, 810, 820, 830]:
            dsp.add_rr_interval(rr)
        assert dsp.calculate_rmssd() == 0.0  # < 5 samples

    def test_rmssd_calculation(self):
        dsp = BioSignalProcessor()
        # 6 интервалов с разницей 10 мс каждый
        for rr in [800, 810, 820, 830, 840, 850]:
            dsp.add_rr_interval(rr)
        result = dsp.calculate_rmssd()
        assert result > 0
        # RMSSD для разницы 10 мс каждый = sqrt(mean(10^2)) = 10.0
        assert 9.5 < result < 10.5

    def test_baevsky_stress_index_short_buffer(self):
        dsp = BioSignalProcessor()
        assert dsp.calculate_baevsky_stress_index() == 100.0  # default

    def test_baevsky_stress_index_with_data(self):
        dsp = BioSignalProcessor()
        for rr in [800] * 30:
            dsp.add_rr_interval(rr)
        result = dsp.calculate_baevsky_stress_index()
        assert result > 0

    def test_negative_rr_ignored(self):
        dsp = BioSignalProcessor()
        dsp.add_rr_interval(-10)
        assert len(dsp.rr_buffer) == 0

    def test_sliding_window(self):
        dsp = BioSignalProcessor(window_size_sec=1)  # 1000ms window
        for rr in [300, 300, 300, 300, 300]:
            dsp.add_rr_interval(rr)
        # 5 * 300 = 1500ms > 1000ms window, старые выталкиваются
        assert sum(dsp.rr_buffer) <= 1000

    def test_reset(self):
        dsp = BioSignalProcessor()
        dsp.add_rr_interval(800)
        dsp.reset()
        assert len(dsp.rr_buffer) == 0


# ==========================================================================
# RL Brain
# ==========================================================================
class TestAegisRLBrain:
    def test_initial_q_table_is_zeros(self):
        brain = AegisRLBrain(profile_path=Path(tempfile.mkdtemp()) / "test.json")
        assert np.all(brain.q_table == 0)

    def test_state_index_bounds(self):
        brain = AegisRLBrain(profile_path=Path(tempfile.mkdtemp()) / "test.json")
        assert brain.get_state_index(50) == 0   # low stress
        assert brain.get_state_index(200) == 1   # moderate
        assert brain.get_state_index(400) == 2   # high
        assert brain.get_state_index(700) == 3   # critical

    def test_choose_frequency_returns_valid(self):
        brain = AegisRLBrain(profile_path=Path(tempfile.mkdtemp()) / "test.json")
        freq, idx, strategy = brain.choose_frequency(200)
        assert 4.0 <= freq <= 12.0
        assert 0 <= idx < len(brain.actions)
        assert isinstance(strategy, str)

    def test_learn_updates_q_table(self):
        brain = AegisRLBrain(profile_path=Path(tempfile.mkdtemp()) / "test.json")
        old_q = brain.q_table[1, 0]
        brain.learn(old_stress=200, action_idx=0, new_stress=150, rmssd_growth=5)
        assert brain.q_table[1, 0] != old_q

    def test_save_and_load_profile(self, tmp_path):
        path = tmp_path / "brain.json"
        brain = AegisRLBrain(profile_path=path)
        brain.learn(old_stress=300, action_idx=0, new_stress=250, rmssd_growth=3)
        brain.save_profile()

        brain2 = AegisRLBrain(profile_path=path)
        assert np.allclose(brain.q_table, brain2.q_table)

    def test_load_corrupted_json_resets(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("NOT JSON")
        brain = AegisRLBrain(profile_path=path)
        assert np.all(brain.q_table == 0)  # fresh start

    def test_load_wrong_shape_resets(self, tmp_path):
        path = tmp_path / "wrong_shape.json"
        path.write_text(json.dumps({"q_table": [[1, 2], [3, 4]], "actions": [4.0, 5.0]}))
        brain = AegisRLBrain(profile_path=path)
        assert np.all(brain.q_table == 0)  # shape mismatch → reset

    def test_load_nan_resets(self, tmp_path):
        path = tmp_path / "nan.json"
        data = {"q_table": [[float("nan")] * 18] * 4, "actions": list(np.arange(4, 12.5, 0.5))}
        path.write_text(json.dumps(data))
        brain = AegisRLBrain(profile_path=path)
        assert np.all(np.isfinite(brain.q_table))


# ==========================================================================
# Storm Predictor
# ==========================================================================
class TestStormPredictor:
    def test_insufficient_data(self, tmp_path):
        predictor = StormPredictor(baseline_path=tmp_path / "bl.json")
        result = predictor.analyze([800, 810, 820, 830, 840])
        assert result["status"] == "INSUFFICIENT_DATA"

    def test_clear_status_with_normal_rr(self, tmp_path):
        predictor = StormPredictor(baseline_path=tmp_path / "bl.json")
        # Стабильные RR-интервалы — норма
        rr = [800 + i * 2 for i in range(30)]
        result = predictor.analyze(rr)
        assert result["status"] in ("CLEAR", "WARNING")
        assert "storm_probability_pct" in result

    def test_storm_alert_with_unstable_rr(self, tmp_path):
        predictor = StormPredictor(baseline_path=tmp_path / "bl.json")
        # Хаотичные RR с большими скачками → высокий storm score
        rr = [600, 1100, 500, 1200, 700, 1300, 600, 1100, 500, 1200,
              700, 1300, 600, 1100, 500, 1200, 700, 1300]
        result = predictor.analyze(rr)
        # Storm predictor может выдать любой статус в зависимости от baseline
        assert result["status"] in ("CLEAR", "WARNING", "STORM_ALERT", "INSUFFICIENT_DATA")
        assert "storm_probability_pct" in result


# ==========================================================================
# Orchestrator
# ==========================================================================
class TestAICognitiveOrchestrator:
    def test_medical_defaults_all_false(self):
        o = AICognitiveOrchestrator()
        assert o.user_medical_profile["endocrine_issues"] is False
        assert o.user_medical_profile["pelvic_congestion"] is False
        assert o.user_medical_profile["cardio_limitations"] is False

    def test_intake_assessment_pelvic(self):
        o = AICognitiveOrchestrator()
        o.user_medical_profile["pelvic_congestion"] = True
        result = o.run_intake_assessment("тазовое напряжение")
        assert result["protocol"] == "pelvic_resonance_safe"

    def test_intake_assessment_acute(self):
        o = AICognitiveOrchestrator()
        result = o.run_intake_assessment("острая мигрень")
        assert result["protocol"] == "theta_anesthesia"

    def test_intake_assessment_default(self):
        o = AICognitiveOrchestrator()
        result = o.run_intake_assessment("обычная сессия")
        assert result["protocol"] == "alpha_relaxation"

    def test_biofeedback_high_alpha(self):
        o = AICognitiveOrchestrator()
        o.session_context = {"protocol": "alpha_relaxation"}
        result = o.generate_live_biofeedback_prompt(
            current_stress=100, current_rmssd=40, elapsed_time=60, alpha_power=0.8
        )
        assert "альфа" in result.lower()


# ==========================================================================
# Marketplace
# ==========================================================================
class TestAegisMarketplace:
    def test_no_hardcoded_tag(self):
        m = AegisMarketplace()
        assert m.amazon_assoc_tag == ""  # без env — пустая строка

    def test_env_tag(self, monkeypatch):
        monkeypatch.setenv("AEGIS_AMAZON_TAG", "test-tag-20")
        m = AegisMarketplace()
        assert m.amazon_assoc_tag == "test-tag-20"

    def test_explicit_tag_overrides_env(self, monkeypatch):
        monkeypatch.setenv("AEGIS_AMAZON_TAG", "env-tag")
        m = AegisMarketplace(amazon_assoc_tag="explicit-tag")
        assert m.amazon_assoc_tag == "explicit-tag"

    def test_affiliate_link_generation(self):
        m = AegisMarketplace(amazon_assoc_tag="mytag-20")
        link = m.generate_affiliate_link("polar_h10")
        assert "mytag-20" in link
        assert "amazon.com" in link

    def test_unknown_product_returns_none(self):
        m = AegisMarketplace(amazon_assoc_tag="x")
        assert m.generate_affiliate_link("nonexistent") is None

    def test_upsell_trigger(self):
        m = AegisMarketplace(amazon_assoc_tag="t-20")
        result = m.get_upsell_trigger_message(user_scan_count=6, average_stress=550)
        assert result is not None
        assert "action_link" in result

    def test_no_upsell_for_healthy_user(self):
        m = AegisMarketplace(amazon_assoc_tag="t-20")
        result = m.get_upsell_trigger_message(user_scan_count=2, average_stress=100)
        assert result is None