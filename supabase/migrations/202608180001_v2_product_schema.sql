create type entity_type_v2 as enum ('PLAYER', 'CLUB', 'COACH', 'COMPETITION');

create table sources (
  id uuid primary key,
  name text not null,
  domain_name text not null unique,
  homepage_url text,
  reliability_tier smallint not null check (reliability_tier between 1 and 5),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table entities (
  id uuid primary key,
  entity_type entity_type_v2 not null,
  canonical_name text not null,
  slug text not null,
  aliases text[] not null default '{}',
  mention_count_24h integer not null default 0,
  last_seen_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (entity_type, slug)
);

create table source_articles (
  id uuid primary key,
  title text not null,
  url text not null,
  canonical_url text not null unique,
  source_name text not null,
  domain_name text not null,
  description text,
  image_url text,
  published_at timestamptz,
  crawled_at timestamptz not null default now(),
  content_hash text,
  slug text,
  body text,
  excerpt text,
  language text not null default 'en',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table entity_timeline_items (
  id uuid primary key,
  entity_id uuid not null references entities(id) on delete cascade,
  window_start timestamptz not null,
  window_end timestamptz not null,
  title text not null,
  summary text not null,
  article_count integer not null check (article_count > 0),
  key_entities_50 text[] not null default '{}',
  key_entities_80 text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (entity_id, window_start, window_end)
);

create table timeline_item_articles (
  timeline_item_id uuid not null references entity_timeline_items(id) on delete cascade,
  article_id uuid not null references source_articles(id) on delete cascade,
  position integer not null default 0,
  created_at timestamptz not null default now(),
  primary key (timeline_item_id, article_id)
);

create index entities_popularity_idx on entities (mention_count_24h desc, canonical_name asc);
create index entities_canonical_name_idx on entities (canonical_name);
create index entities_aliases_gin_idx on entities using gin (aliases);
create index source_articles_published_at_idx on source_articles (published_at desc);
create unique index source_articles_slug_unique_idx on source_articles (slug) where slug is not null;
create index source_articles_sort_idx on source_articles (coalesce(published_at, crawled_at) desc);
create index entity_timeline_items_entity_window_idx on entity_timeline_items (entity_id, window_start desc);
create index entity_timeline_items_window_start_idx on entity_timeline_items (window_start desc);
create index timeline_item_articles_article_idx on timeline_item_articles (article_id);

