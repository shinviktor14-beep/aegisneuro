"""Тесты буфера данных Galaxy Watch / Wear OS."""

from aegis.core.watch import WatchDataBuffer


def test_ingest_accepts_heart_rate_and_ibi_intervals():
    buffer = WatchDataBuffer()

    accepted = buffer.ingest(
        {
            "source": "galaxy_watch4",
            "heart_rate_bpm": 72,
            "ibi_ms": [820, 830, 810, 840],
            "quality": "good",
        }
    )

    assert accepted == 4
    assert buffer.latest_rr_intervals() == [820, 830, 810, 840]
    assert buffer.summary()["heart_rate_bpm"] == 72
    assert buffer.summary()["connected"] is True


def test_ingest_rejects_out_of_range_values():
    buffer = WatchDataBuffer()

    accepted = buffer.ingest(
        {
            "heart_rate_bpm": 500,
            "rr_intervals_ms": [250, 800, 2100, "bad", 900],
        }
    )

    assert accepted == 2
    assert buffer.latest_rr_intervals() == [800, 900]
    assert buffer.summary()["heart_rate_bpm"] is None
    assert buffer.summary()["rejected_samples"] == 4


def test_hr_without_ibi_is_not_enough_for_hrv():
    buffer = WatchDataBuffer()

    accepted = buffer.ingest({"heart_rate_bpm": 68})

    assert accepted == 0
    assert buffer.summary()["heart_rate_bpm"] == 68
    assert buffer.has_enough_hrv_data() is False


def test_buffer_keeps_sliding_rr_window():
    buffer = WatchDataBuffer(max_rr_intervals=3)

    buffer.ingest({"ibi_ms": [800, 810, 820, 830, 840]})

    assert buffer.latest_rr_intervals() == [820, 830, 840]
