from footballpulse_crawler_service import liveness


def test_crawler_service_is_importable_and_alive() -> None:
    assert liveness() == {"service": "crawler-service", "status": "ok"}
