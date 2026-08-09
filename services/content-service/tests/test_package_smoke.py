from footballpulse_content_service import liveness


def test_content_service_is_importable_and_alive() -> None:
    assert liveness() == {"service": "content-service", "status": "ok"}
