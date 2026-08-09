from footballpulse_ai_content_service import liveness


def test_ai_content_service_is_importable_and_alive() -> None:
    assert liveness() == {"service": "ai-content-service", "status": "ok"}
