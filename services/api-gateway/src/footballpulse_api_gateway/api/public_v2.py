from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine


class V2EntitySummary(BaseModel):
    id: UUID
    entity_type: str
    canonical_name: str
    slug: str
    aliases: list[str] = Field(default_factory=list)
    mention_count_24h: int = 0
    last_seen_at: datetime | None = None


class V2TopEntitiesResponse(BaseModel):
    items: list[V2EntitySummary]
    limit: int
    window: str


class V2EntitySearchResponse(BaseModel):
    items: list[V2EntitySummary]


class V2SourceArticle(BaseModel):
    id: UUID
    title: str
    url: str
    canonical_url: str
    source_name: str
    domain_name: str
    description: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None


class V2EntityTimelineItem(BaseModel):
    id: UUID
    entity_id: UUID
    window_start: datetime
    window_end: datetime
    title: str
    summary: str
    article_count: int
    key_entities_50: list[str] = Field(default_factory=list)
    key_entities_80: list[str] = Field(default_factory=list)
    source_articles: list[V2SourceArticle] = Field(default_factory=list)


class V2EntityTimelineResponse(BaseModel):
    entity_id: UUID
    entity: V2EntitySummary | None = None
    items: list[V2EntityTimelineItem]


class V2EntityListResponse(BaseModel):
    items: list[V2EntitySummary]
    limit: int
    offset: int
    total: int


def create_public_v2_app(engine: Engine) -> FastAPI:
    app = FastAPI(title="FootballPulse Public API v2", version="2.0.0")

    @app.get("/api/v2/entities/top", response_model=V2TopEntitiesResponse)
    async def get_top_entities(
        window: str = Query("24h"),
        limit: int = Query(10, ge=1, le=100),
    ) -> V2TopEntitiesResponse:
        statement = sa.text(
            """
            select id, entity_type::text as entity_type, canonical_name, slug,
                   aliases, mention_count_24h, last_seen_at
            from entities
            order by mention_count_24h desc, canonical_name asc
            limit :limit
            """
        )
        with engine.connect() as connection:
            rows = connection.execute(statement, {"limit": limit}).mappings().all()
            items = [V2EntitySummary.model_validate(dict(row)) for row in rows]
        return V2TopEntitiesResponse(items=items, limit=limit, window=window)

    @app.get("/api/v2/entities/search", response_model=V2EntitySearchResponse)
    async def search_entities(
        q: str = Query(..., min_length=1),
    ) -> V2EntitySearchResponse:
        search_pattern = f"%{q.strip()}%"
        exact_query = q.strip()
        statement = sa.text(
            """
            select id, entity_type::text as entity_type, canonical_name, slug,
                   aliases, mention_count_24h, last_seen_at
            from entities
            where canonical_name ilike :pattern
               or slug ilike :pattern
               or :exact = any(aliases)
               or exists (
                   select 1 from unnest(aliases) a where a ilike :pattern
               )
            order by mention_count_24h desc, canonical_name asc
            limit 20
            """
        )
        with engine.connect() as connection:
            rows = connection.execute(
                statement,
                {"pattern": search_pattern, "exact": exact_query},
            ).mappings().all()
            items = [V2EntitySummary.model_validate(dict(row)) for row in rows]
        return V2EntitySearchResponse(items=items)

    @app.get("/api/v2/entities/{entity_id}/timeline", response_model=V2EntityTimelineResponse)
    async def get_entity_timeline(
        entity_id: UUID,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> V2EntityTimelineResponse:
        entity_query = sa.text(
            """
            select id, entity_type::text as entity_type, canonical_name, slug,
                   aliases, mention_count_24h, last_seen_at
            from entities
            where id = :entity_id
            """
        )
        timeline_query = sa.text(
            """
            select id, entity_id, window_start, window_end, title, summary,
                   article_count, key_entities_50, key_entities_80
            from entity_timeline_items
            where entity_id = :entity_id
            order by window_start desc
            limit :limit offset :offset
            """
        )
        articles_query = sa.text(
            """
            select tia.timeline_item_id, sa.id, sa.title, sa.url, sa.canonical_url,
                   sa.source_name, sa.domain_name, sa.description, sa.image_url, sa.published_at
            from timeline_item_articles tia
            join source_articles sa on sa.id = tia.article_id
            where tia.timeline_item_id in :item_ids
            order by tia.position asc
            """
        )

        with engine.connect() as connection:
            entity_row = connection.execute(entity_query, {"entity_id": entity_id}).mappings().one_or_none()
            entity_info = V2EntitySummary.model_validate(dict(entity_row)) if entity_row else None

            timeline_rows = connection.execute(
                timeline_query,
                {"entity_id": entity_id, "limit": limit, "offset": offset},
            ).mappings().all()

            item_ids = [row["id"] for row in timeline_rows]
            articles_by_item: dict[UUID, list[V2SourceArticle]] = {iid: [] for iid in item_ids}

            if item_ids:
                art_rows = connection.execute(
                    articles_query,
                    {"item_ids": tuple(item_ids)},
                ).mappings().all()
                for a_row in art_rows:
                    item_id = a_row["timeline_item_id"]
                    articles_by_item[item_id].append(
                        V2SourceArticle(
                            id=a_row["id"],
                            title=a_row["title"],
                            url=a_row["url"],
                            canonical_url=a_row["canonical_url"],
                            source_name=a_row["source_name"],
                            domain_name=a_row["domain_name"],
                            description=a_row["description"],
                            image_url=a_row["image_url"],
                            published_at=a_row["published_at"],
                        )
                    )

            timeline_items = [
                V2EntityTimelineItem(
                    id=row["id"],
                    entity_id=row["entity_id"],
                    window_start=row["window_start"],
                    window_end=row["window_end"],
                    title=row["title"],
                    summary=row["summary"],
                    article_count=row["article_count"],
                    key_entities_50=row["key_entities_50"] or [],
                    key_entities_80=row["key_entities_80"] or [],
                    source_articles=articles_by_item.get(row["id"], []),
                )
                for row in timeline_rows
            ]

        return V2EntityTimelineResponse(
            entity_id=entity_id,
            entity=entity_info,
            items=timeline_items,
        )

    @app.get("/api/v2/entities/{entity_id}", response_model=V2EntitySummary)
    async def get_entity_by_id(entity_id: UUID) -> V2EntitySummary:
        statement = sa.text(
            """
            select id, entity_type::text as entity_type, canonical_name, slug,
                   aliases, mention_count_24h, last_seen_at
            from entities
            where id = :entity_id
            """
        )
        with engine.connect() as connection:
            row = connection.execute(statement, {"entity_id": entity_id}).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="entity not found")
        return V2EntitySummary.model_validate(dict(row))

    @app.get("/api/v2/entities", response_model=V2EntityListResponse)
    async def list_entities(
        type: str | None = Query(None),
        q: str | None = Query(None),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> V2EntityListResponse:
        conditions = ["1=1"]
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if type:
            conditions.append("entity_type::text = upper(:type)")
            params["type"] = type
        if q and q.strip():
            conditions.append(
                "(canonical_name ilike :pattern or :exact = any(aliases) or exists (select 1 from unnest(aliases) a where a ilike :pattern))"
            )
            params["pattern"] = f"%{q.strip()}%"
            params["exact"] = q.strip()

        where_clause = " and ".join(conditions)
        statement = sa.text(
            f"""
            select id, entity_type::text as entity_type, canonical_name, slug,
                   aliases, mention_count_24h, last_seen_at
            from entities
            where {where_clause}
            order by mention_count_24h desc, canonical_name asc
            limit :limit offset :offset
            """
        )
        count_statement = sa.text(f"select count(*) from entities where {where_clause}")
        with engine.connect() as connection:
            rows = connection.execute(statement, params).mappings().all()
            total = connection.execute(count_statement, params).scalar_one()
            items = [V2EntitySummary.model_validate(dict(row)) for row in rows]

        return V2EntityListResponse(items=items, limit=limit, offset=offset, total=total)

    return app

