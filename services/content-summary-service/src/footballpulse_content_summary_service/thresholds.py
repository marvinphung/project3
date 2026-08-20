from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable


def compute_entity_thresholds(
    article_entities_list: list[Iterable[str]],
) -> tuple[list[str], list[str]]:
    """
    Computes key canonical entities appearing in >=50% and >=80% of distinct articles.
    
    Each article contributes at most once per canonical entity.
    Returns: (entities_50, entities_80) sorted by frequency (descending) then name.
    """
    total_articles = len(article_entities_list)
    if total_articles == 0:
        return [], []

    counts: Counter[str] = Counter()
    for entities in article_entities_list:
        distinct_entities_in_article = {e.strip() for e in entities if e and e.strip()}
        for entity_name in distinct_entities_in_article:
            counts[entity_name] += 1

    # Nguong >= 50% va >= 80% cua tong so distinct articles
    threshold_50 = 0.5 * total_articles
    threshold_80 = 0.8 * total_articles

    entities_50 = [
        name for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= threshold_50
    ]

    entities_80 = [
        name for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= threshold_80
    ]

    return entities_50, entities_80
