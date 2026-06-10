# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: AegisNeuro

A closed-loop neuro-regulation system. Reads biometric signals (heart-rate variability from Polar H10 chest strap, or finger-on-camera PPG), derives stress markers (RMSSD, Baevsky Stress Index), and drives a Q-learning "brain" that selects a binaural-beat frequency (4–12.5 Hz) to push the user from sympathetic (stress) into parasympathetic (recovery) states. Outputs stereo audio with TTS guidance.

## Running the code

There is **no `requirements.txt`, no test suite, no build system, and no single canonical entry point**. Pick the entry point that matches the hardware you want to simulate:

| File | Interface | What it does |
|---|---|---|
| `main.py` | KivyMD (Android-style mobile UI) | Full mobile app: camera PPG, RL brain, storm predictor, Kivy audio engine. **Imports the real `aegis_rl_brain`, `aegis_ppg_processor`, `aegis_audio_engine`, `aegis_storm_predictor`** (not inlined stubs). |
| `aegis_neuro_gui.py` | tkinter desktop | Desktop GUI with Muse 2 EEG integration via BrainFlow. **Inlines its own `AegisRLBrain`** — does not import from `aegis_rl_brain.py`. |
| `aegis_neuro_system.py` | tkinter desktop | Variant of the desktop GUI; inlines `AegisRLBrain`. Older file — `aegis_neuro_gui.py` is the more current one. |
| `aegis_neuro_mobile.py` | KivyMD | Earlier mobile prototype; uses **stub classes** for RL/predictor/PPG. Superseded by `main.py`. |
| `aegis_neuro_core.py` | headless (threads + queue) | Console-only closed-loop demo with mock R-R data. No GUI, no camera. |
| `main_orchestrator.py` | headless | Console demo using `NeuroAudioEngine` (oldest audio impl). No RL. |
| `test_camera_ppg.py` | cv2 window | OpenCV utility — proves a webcam can see finger PPG. Not part of the app. |

Most module files also have a `if __name__ == "__main__":` block that runs a self-contained demo when the file is executed directly (e.g., `python bio_dsp.py`, `python aegis_rl_brain.py`, `python aegis_storm_predictor.py`, `python audio_engine.py`).

### Dependencies

Install on demand based on which entry point you use:
- `numpy` — everywhere
- `pyaudio`, `pyttsx3` — desktop audio + voice (e.g., `advanced_audio.py`, `audio_engine.py`)
- `kivy`, `kivymd` — `main.py`, `aegis_neuro_mobile.py`
- `bleak` — `polar_ble.py` (real Polar H10 BLE stream)
- `brainflow` — `aegis_neuro_gui.py`, `aegis_neuro_system.py` (real Muse 2 EEG)
- `opencv-python`, `matplotlib` — `test_camera_ppg.py`
- `jnius` (Android only) — used inside `AndroidHardwareBridge` in `main.py` for torch/flashlight control

There is no venv, no lockfile. Modules degrade gracefully when optional deps are missing (e.g., `BRAINFLOW_AVAILABLE = False` path in `aegis_neuro_gui.py`).

## Architecture (data flow)

```
┌─────────────────┐    R-R ms     ┌──────────────┐   stress/RMSSD   ┌──────────────────┐
│ Hardware layer  │ ────────────► │  DSP / Math  │ ───────────────► │  AI Decision     │
│ polar_ble.py    │               │  bio_dsp.py  │                  │  aegis_rl_brain  │
│ aegis_ppg_proc  │               │              │                  │  ai_orchestrator │
└─────────────────┘               └──────────────┘                  │  aegis_storm_    │
                                                                     │   predictor      │
                                                                     └────────┬─────────┘
                                                                              │ freq (Hz)
                                                                              ▼
                                                                     ┌──────────────────┐
                                                                     │ Audio Output     │
                                                                     │ aegis_audio_eng  │
                                                                     │ advanced_audio   │
                                                                     │ aegis_spatial_   │
                                                                     │   audio          │
                                                                     └──────────────────┘
```

### Layer responsibilities

**Hardware ingestion** — `polar_ble.py` (async BLE parser of Polar H10 heart-rate characteristic `00002a37-...`; decodes R-R in 1/1024 s units) and `aegis_ppg_processor.py` (peak detection on the red-channel mean of camera frames; produces R-R intervals in ms).

**DSP** — `bio_dsp.py`:
- `calculate_rmssd()` — root-mean-square of successive R-R differences (parasympathetic tone).
- `calculate_baevsky_stress_index()` — formula `AMo / (2 * Mo * MxDMn)`; norm 50–150, stress > 300.
- Uses a sliding time-windowed buffer (default 120 s), not sample-counted.

**Storm prediction** — `aegis_storm_predictor.py` and `aegis_storm_predictor.py` (two near-identical copies; `main.py` uses an inlined version with adapted thresholds for 15-second scans). Looks at RMSSD drop vs. personal baseline, current stress vs. baseline × 1.5/1.8, and chunk-wise RMSSD alternation coefficient. Returns `CLEAR` / `WARNING` / `STORM_ALERT`.

**RL brain** — `aegis_rl_brain.py` (and **three inlined copies** in `main.py`, `aegis_neuro_gui.py`, `aegis_neuro_system.py` — see "gotchas" below):
- State: 4 stress zones (<150, 150–300, 300–500, >500).
- Actions: 18 frequencies from 4.0 to 12.0 Hz step 0.5.
- Bellman update with reward `stress_delta + 2*rmssd_growth - 50 if stress increased`.
- ε-greedy (ε=0.3), α=0.2, γ=0.9.
- Q-table persists to `aegis_user_brain_profile.json` in the CWD.

**Audio** — three implementations, choose by use case:
- `audio_engine.py` — minimal sine-based binaural beat (16-bit PCM), no ambient. The oldest.
- `aegis_audio_engine.py` — float32 stereo with live `set_frequency()` hot-swap, runs in a daemon thread. **Used by `main.py`.**
- `advanced_audio.py` — adds sub-bass + ambient "breathing" + Russian TTS via `pyttsx3` with auto-volume ducking. Used by `aegis_neuro_core.py`.
- `aegis_spatial_audio.py` — HRTF-style 3D rotation (ILD + ITD) of the binaural signal around the head.

**Orchestrators** — `aegis_neuro_core.py` (closed-loop with `queue.Queue` between ingest and decision threads) and `main_orchestrator.py` (older, no RL).

**Side modules** — `longevity_analytics.py`, `aegis_longevity_brain.py` (multi-day trend analysis); `aegis_marketplace.py` (Amazon affiliate upsell logic keyed on stress level + scan count).

## Files persisted at runtime (in CWD)

- `aegis_user_brain_profile.json` — RL Q-table (created on first session, reused forever).
- `aegis_historical_baseline.json` — personal HRV baseline used by storm predictor (adapted with EMA 0.1 of new samples when status is CLEAR).

Do not commit these; they are user-specific. There is no `.gitignore`.

## Code conventions

- All comments, print messages, docstrings, UI strings, and variable names mixing Cyrillic are in **Russian** (and a few in Uzbek). This is intentional — do not translate. New code in this repo should keep Russian for user-facing strings.
- Tkinter GUIs use dark theme `#11141a` / `#181c26` / `#0d1117` with neon accents `#00ffcc`, `#38bdf8`, `#55ff55`, `#ff3333`.
- KivyMD mobile UIs use `theme_cls.theme_style = "Dark"` + `primary_palette = "Teal"`.
- "Stress index" always refers to the Baevsky Stress Index (no other definition exists in the codebase).
- Frequency bands referenced by name: Theta (4–7 Hz, "anesthesia"), Alpha (8–12 Hz, "relaxation"), Schumann resonance (7.83 Hz, "deep meditation").
- The single global `random` module is used widely — there is no seeded RNG; demos are non-reproducible.

## Known gotchas

1. **`AegisRLBrain` is duplicated in 4 places**: `aegis_rl_brain.py` is the canonical/standalone version, but `main.py`, `aegis_neuro_gui.py`, and `aegis_neuro_system.py` each define their own local `AegisRLBrain` class. Changes to one will not propagate to the others. When adding RL behavior, decide which entry point you're targeting and edit the right copy (or refactor toward the standalone one).
2. **`aegis_storm_predictor.py` exists both as a standalone file and inlined inside `main.py`** with different thresholds (`<10` intervals instead of `<100`, `bins=10` instead of `bins=20`, `>0.12` alternation instead of `>0.15`). The inlined copy in `main.py` is what actually runs in the mobile app.
3. **Audio output requires a working audio device.** `pyaudio.open(...)` will hard-fail on systems without one (e.g., headless CI, some WSL setups). `main.py` audio and `test_camera_ppg.py` both need a real camera/mic stack.
4. **Hardcoded CWD paths.** The RL brain and storm predictor read/write JSON files with bare filenames, so the CWD at launch matters. Run from `D:\AegisNeuro` (this repo root) or the JSONs will be created wherever Python was invoked.
5. **`aegis_neuro_gui.py` line 191** has a malformed `self.root.geometry("600(x)770")` followed by a correct `"600x770"`. The first is dead code but is what shows up in tracebacks if it ever gets evaluated — leave it alone unless refactoring.
6. **No tests.** There is no pytest, no unittest, no CI. The `if __name__ == "__main__":` blocks in each module are the only verification mechanism.
7. **Stub vs. real modules in `aegis_neuro_mobile.py`.** The classes named `AegisRLBrain`, `AegisStormPredictor`, `HardwareBridgeStub`, `PPGProcessorStub`, `PulseOrbStub` are inline placeholders; they return dummy data. If the mobile app behaves too cleanly, it may be running these stubs instead of the real code in `main.py`.
8. **An in-progress `aegis/` package refactor sits next to the live code.** `aegis/__init__.py`, `aegis/config.py`, `aegis/pipeline.py`, and `aegis/core/{dsp,ppg,rl_brain,storm,longevity,marketplace}.py` plus `aegis/core/audio/{engine,spatial,voice}.py` form a second, modular implementation with the same responsibilities as the top-level loose modules. **As of this writing, `main.py` and the other entry points still import from the loose top-level modules (`aegis_rl_brain`, `aegis_ppg_processor`, `aegis_audio_engine`, `aegis_storm_predictor`) — the `aegis/` package is not yet wired up to any entry point, except internally (`aegis/pipeline.py` imports its own submodules).** The refactor changes persistence paths: the package reads/writes `data/brain_profile.json`, `data/historical_baseline.json`, and `data/longevity_history.json` (paths defined in `aegis/config.py`), while the live code still uses bare filenames in CWD (`aegis_user_brain_profile.json`, `aegis_historical_baseline.json`). Do not assume the two implementations stay in sync.
