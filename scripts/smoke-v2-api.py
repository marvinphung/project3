from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend(
    [
        str(ROOT / 'services/api-gateway/src'),
        str(ROOT / 'packages/runtime-config/src'),
    ]
)

from footballpulse_api_gateway.runtime_v2 import build_app


def main() -> None:
    app = build_app(os.environ)
    client = TestClient(app)

    listing = client.get('/api/v2/articles?limit=5')
    if listing.status_code != 200:
        raise AssertionError(f'listing failed: {listing.status_code} {listing.text}')
    items = listing.json()['items']
    if not items:
        raise AssertionError('api v2 articles endpoint returned no items')
    slug = items[0]['slug']

    detail = client.get(f'/api/v2/articles/{slug}')
    if detail.status_code != 200:
        raise AssertionError(f'detail failed: {detail.status_code} {detail.text}')
    payload = detail.json()
    if payload['slug'] != slug:
        raise AssertionError('detail slug mismatch')

    print(f'v2 api smoke passed: slug={slug} title_vi={payload["title_vi"]}')


if __name__ == '__main__':
    main()
