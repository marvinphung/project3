from footballpulse_intelligence_service import liveness


def test_intelligence_service_is_importable_and_alive() -> None:
    assert liveness() == {"service": "intelligence-service", "status": "ok"}
