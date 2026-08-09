import json

SERVICE_NAME = "ai-content-service"


def liveness() -> dict[str, str]:
    return {"service": SERVICE_NAME, "status": "ok"}


def main() -> None:
    print(json.dumps(liveness(), sort_keys=True))
