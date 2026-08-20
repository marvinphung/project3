from __future__ import annotations

import json
from pathlib import Path

from footballpulse_event_contracts import (
    ArticleCleanedEvent,
    ArticleDiscoveredEvent,
    NewsCrawledEvent,
    event_json_schema,
)

ROOT = Path(__file__).parents[1]
EVENTS = {
    "article.cleaned": ArticleCleanedEvent,
    "article.discovered": ArticleDiscoveredEvent,
    "news.crawled": NewsCrawledEvent,
}


def main() -> None:
    for event_name, model in EVENTS.items():
        destination = ROOT / "contracts" / "events" / event_name / "v1.schema.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(event_json_schema(model), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
