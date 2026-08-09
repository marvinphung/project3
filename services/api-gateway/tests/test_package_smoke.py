from footballpulse_api_gateway import liveness


def test_api_gateway_is_importable_and_alive() -> None:
    assert liveness() == {"service": "api-gateway", "status": "ok"}
