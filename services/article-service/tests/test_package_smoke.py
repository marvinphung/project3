from footballpulse_article_service import liveness


def test_article_service_is_importable_and_alive() -> None:
    assert liveness() == {"service": "article-service", "status": "ok"}
