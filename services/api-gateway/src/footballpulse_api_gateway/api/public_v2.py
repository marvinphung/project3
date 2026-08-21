from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.engine import Engine


class V2EntitySummary(BaseModel):
    id: UUID
    entity_type: str
    canonical_name: str
    name: str = ""
    slug: str
    aliases: list[str] = Field(default_factory=list)
    mention_count_24h: int = 0
    article_count: int = 0
    last_seen_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_compat_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            c_name = data.get("canonical_name") or data.get("name") or ""
            data["canonical_name"] = c_name
            data["name"] = data.get("name") or c_name
            if "article_count" not in data or data["article_count"] == 0:
                data["article_count"] = data.get("mention_count_24h", 0)
        return data


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


class V2ArticleEntity(BaseModel):
    id: UUID
    entity_type: str
    name: str
    slug: str


class V2ArticleItem(BaseModel):
    id: UUID
    slug: str
    title_en: str
    title_vi: str
    excerpt_vi: str | None = None
    body_en: str
    body_vi: str
    story_id: str | None = None
    published_at: datetime
    entities: list[V2ArticleEntity] = Field(default_factory=list)


class V2ArticleListResponse(BaseModel):
    items: list[V2ArticleItem]
    limit: int
    offset: int
    total: int = 0


class V2ArticleSourceItem(BaseModel):
    source_id: str
    source_name: str
    source_url: str
    published_at: datetime | None = None
    reliability_tier: int = 1


class V2ArticleSourcesResponse(BaseModel):
    items: list[V2ArticleSourceItem]


def _build_article_item(row: Any, entities: list[V2ArticleEntity]) -> V2ArticleItem:
    aid = row["id"]
    title = row["title"] or "Untitled"
    raw_slug = row.get("slug")
    slug = raw_slug if raw_slug else str(aid)
    pub_at = row["published_at"] or row["crawled_at"]
    body = row.get("body") or row.get("description") or title
    excerpt = row.get("excerpt") or row.get("description") or (body[:240] if body else None)
    return V2ArticleItem(
        id=aid,
        slug=slug,
        title_en=title,
        title_vi=title,
        excerpt_vi=excerpt,
        body_en=body,
        body_vi=body,
        story_id=None,
        published_at=pub_at,
        entities=entities,
    )


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
        ).bindparams(sa.bindparam("item_ids", expanding=True))

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

    @app.get("/api/v2/articles", response_model=V2ArticleListResponse)
    async def list_articles(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        sort: str = Query("newest"),
        q: str | None = Query(None),
        entity_type: str | None = Query(None),
        entity_slug: str | None = Query(None),
        story_id: str | None = Query(None),
    ) -> V2ArticleListResponse:
        conditions = ["1=1"]
        params: dict[str, object] = {"limit": limit, "offset": offset}

        if q and q.strip():
            conditions.append(
                "(sa.title ilike :q_pattern or (sa.description is not null and sa.description ilike :q_pattern) or (sa.body is not null and sa.body ilike :q_pattern))"
            )
            params["q_pattern"] = f"%{q.strip()}%"

        if entity_slug or entity_type:
            entity_conds = []
            if entity_slug and entity_slug.strip():
                entity_conds.append("e.slug = :entity_slug")
                params["entity_slug"] = entity_slug.strip().lower()
            if entity_type and entity_type.strip():
                entity_conds.append("e.entity_type::text = upper(:entity_type)")
                params["entity_type"] = entity_type.strip()
            e_where = " and ".join(entity_conds)
            conditions.append(
                f"""
                exists (
                    select 1 from timeline_item_articles tia_f
                    join entity_timeline_items eti_f on eti_f.id = tia_f.timeline_item_id
                    join entities e on e.id = eti_f.entity_id
                    where tia_f.article_id = sa.id and {e_where}
                )
                """
            )

        order_dir = "desc" if sort != "oldest" else "asc"
        where_clause = " and ".join(conditions)

        articles_query = sa.text(
            f"""
            select sa.id, sa.title, sa.url, sa.canonical_url, sa.source_name, sa.domain_name,
                   sa.description, sa.image_url, sa.published_at, sa.crawled_at,
                   sa.slug, sa.body, sa.excerpt, sa.language
            from source_articles sa
            where {where_clause}
            order by coalesce(sa.published_at, sa.crawled_at) {order_dir}, sa.id {order_dir}
            limit :limit offset :offset
            """
        )
        count_query = sa.text(f"select count(*) from source_articles sa where {where_clause}")

        with engine.connect() as connection:
            article_rows = connection.execute(articles_query, params).mappings().all()
            total = connection.execute(count_query, params).scalar_one()

            article_ids = [row["id"] for row in article_rows]
            entities_by_article: dict[UUID, list[V2ArticleEntity]] = {aid: [] for aid in article_ids}

            if article_ids:
                entities_query = sa.text(
                    """
                    select distinct tia.article_id, e.id as entity_id, e.entity_type::text as entity_type,
                           e.canonical_name as name, e.slug
                    from timeline_item_articles tia
                    join entity_timeline_items eti on eti.id = tia.timeline_item_id
                    join entities e on e.id = eti.entity_id
                    where tia.article_id in :article_ids
                    order by name asc
                    """
                ).bindparams(sa.bindparam("article_ids", expanding=True))
                e_rows = connection.execute(
                    entities_query,
                    {"article_ids": tuple(article_ids)},
                ).mappings().all()

                seen = set()
                for er in e_rows:
                    aid = er["article_id"]
                    eid = er["entity_id"]
                    key = (aid, eid)
                    if key not in seen:
                        seen.add(key)
                        entities_by_article[aid].append(
                            V2ArticleEntity(
                                id=eid,
                                entity_type=er["entity_type"],
                                name=er["name"],
                                slug=er["slug"],
                            )
                        )

            items = [_build_article_item(row, entities_by_article.get(row["id"], [])) for row in article_rows]

        return V2ArticleListResponse(items=items, limit=limit, offset=offset, total=total)

    @app.get("/api/v2/articles/{id_or_slug}", response_model=V2ArticleItem)
    async def get_article_by_id_or_slug(id_or_slug: str) -> V2ArticleItem:
        target_uuid = None
        try:
            target_uuid = UUID(id_or_slug)
        except ValueError:
            target_uuid = None

        if target_uuid:
            lookup_query = sa.text(
                """
                select sa.id, sa.title, sa.url, sa.canonical_url, sa.source_name, sa.domain_name,
                       sa.description, sa.image_url, sa.published_at, sa.crawled_at,
                       sa.slug, sa.body, sa.excerpt, sa.language
                from source_articles sa
                where sa.id = :id or sa.slug = :slug
                limit 1
                """
            )
            params: dict[str, object] = {"id": target_uuid, "slug": id_or_slug}
        else:
            lookup_query = sa.text(
                """
                select sa.id, sa.title, sa.url, sa.canonical_url, sa.source_name, sa.domain_name,
                       sa.description, sa.image_url, sa.published_at, sa.crawled_at,
                       sa.slug, sa.body, sa.excerpt, sa.language
                from source_articles sa
                where sa.slug = :slug
                limit 1
                """
            )
            params = {"slug": id_or_slug}

        with engine.connect() as connection:
            row = connection.execute(lookup_query, params).mappings().one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="article not found")

            art_id = row["id"]
            entities_query = sa.text(
                """
                select distinct e.id as entity_id, e.entity_type::text as entity_type,
                       e.canonical_name as name, e.slug
                from timeline_item_articles tia
                join entity_timeline_items eti on eti.id = tia.timeline_item_id
                join entities e on e.id = eti.entity_id
                where tia.article_id = :article_id
                order by name asc
                """
            )
            e_rows = connection.execute(entities_query, {"article_id": art_id}).mappings().all()
            entities = [
                V2ArticleEntity(
                    id=er["entity_id"],
                    entity_type=er["entity_type"],
                    name=er["name"],
                    slug=er["slug"],
                )
                for er in e_rows
            ]

        return _build_article_item(row, entities)

    @app.get("/api/v2/articles/{id_or_slug}/sources", response_model=V2ArticleSourcesResponse)
    async def get_article_sources(id_or_slug: str) -> V2ArticleSourcesResponse:
        target_uuid = None
        try:
            target_uuid = UUID(id_or_slug)
        except ValueError:
            target_uuid = None

        if target_uuid:
            lookup_query = sa.text(
                """
                select sa.id, sa.title, sa.url, sa.canonical_url, sa.source_name,
                       sa.published_at, sa.crawled_at
                from source_articles sa
                where sa.id = :id or sa.slug = :slug
                limit 1
                """
            )
            params: dict[str, object] = {"id": target_uuid, "slug": id_or_slug}
        else:
            lookup_query = sa.text(
                """
                select sa.id, sa.title, sa.url, sa.canonical_url, sa.source_name,
                       sa.published_at, sa.crawled_at
                from source_articles sa
                where sa.slug = :slug
                limit 1
                """
            )
            params = {"slug": id_or_slug}

        with engine.connect() as connection:
            row = connection.execute(lookup_query, params).mappings().one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="article not found")

            source_url = row["url"] or row["canonical_url"]
            items = [
                V2ArticleSourceItem(
                    source_id=str(row["id"]),
                    source_name=row["source_name"] or "Unknown",
                    source_url=source_url,
                    published_at=row["published_at"] or row["crawled_at"],
                    reliability_tier=1,
                )
            ]

        return V2ArticleSourcesResponse(items=items)

    return app

