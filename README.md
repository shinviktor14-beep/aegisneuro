# AegisNeuro

**Closed-loop neuroregulation system** with Q-learning brain, autonomic storm predictor, and real-time biofeedback.

## Architecture

```
aegis/
├── core/
│   ├── dsp.py            # R-R intervals, RMSSD, Baevsky stress index
│   ├── ppg.py            # Camera PPG peak detector
│   ├── rl_brain.py       # Q-learning (4 states × 18 frequencies)
│   ├── storm.py          # Autonomic storm predictor
│   ├── orchestrator.py   # Cognitive complaint → protocol selector
│   ├── muse.py           # Muse 2 EEG via BrainFlow
│   ├── marketplace.py    # Amazon affiliate upsell engine
│   ├── longevity.py      # Longevity scoring
│   └── audio/            # Spatial 8D audio engine
├── config.py             # Centralised constants & paths
└── __init__.py
```

Entry points:
- `main.py` — KivyMD mobile app
- `aegis_neuro_gui.py` — tkinter desktop app
- `aegis_neuro_system.py` — tkinter RL-integrated desktop app
- `aegis_neuro_mobile.py` — KivyMD mobile (legacy)

## Quick Start

```bash
# Desktop (tkinter)
pip install -r requirements.txt
python aegis_neuro_gui.py

# Mobile (KivyMD) — requires Buildozer
buildozer android debug
```

## Tests

```bash
pip install pytest numpy
pytest tests/ -v
```

## Environment Variables

| Variable | Description |
|---|---|
| `AEGIS_AMAZON_TAG` | Amazon Associates tag (no hardcoded default) |

## Safety

- All medical profile defaults are `False` — no assumptions about user conditions
- Q-table validated on load (shape check, NaN/Inf check, JSON corruption)
- Amazon affiliate tag loaded from environment, not hardcoded

## License

MIT