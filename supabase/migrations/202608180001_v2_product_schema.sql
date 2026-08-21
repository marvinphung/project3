do $$
begin
  create type entity_type_v2 as enum ('PLAYER', 'CLUB', 'COACH', 'COMPETITION');
exception
  when duplicate_object then null;
end $$;

create table if not exists sources (
  id uuid primary key,
  name text not null,
  domain_name text not null unique,
  homepage_url text,
  reliability_tier smallint not null check (reliability_tier between 1 and 5),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists entities (
  id uuid primary key,
  entity_type entity_type_v2 not null,
  name text not null,
  canonical_name text not null,
  slug text not null,
  aliases text[] not null default '{}',
  mention_count_24h integer not null default 0,
  last_seen_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table entities add column if not exists name text;
alter table entities add column if not exists canonical_name text;
alter table entities add column if not exists aliases text[] not null default '{}';
alter table entities add column if not exists mention_count_24h integer not null default 0;
alter table entities add column if not exists last_seen_at timestamptz;

update entities
set name = coalesce(name, canonical_name, slug)
where name is null;

update entities
set canonical_name = coalesce(canonical_name, name, slug)
where canonical_name is null;

alter table entities alter column name set not null;
alter table entities alter column canonical_name set not null;

create table if not exists source_articles (
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

create table if not exists entity_timeline_items (
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

create table if not exists timeline_item_articles (
  timeline_item_id uuid not null references entity_timeline_items(id) on delete cascade,
  article_id uuid not null references source_articles(id) on delete cascade,
  position integer not null default 0,
  created_at timestamptz not null default now(),
  primary key (timeline_item_id, article_id)
);

create unique index if not exists entities_entity_type_slug_unique_idx on entities (entity_type, slug);
create index if not exists entities_popularity_idx on entities (mention_count_24h desc, canonical_name asc);
create index if not exists entities_canonical_name_idx on entities (canonical_name);
create index if not exists entities_aliases_gin_idx on entities using gin (aliases);
create index if not exists source_articles_published_at_idx on source_articles (published_at desc);
create unique index if not exists source_articles_canonical_url_unique_idx on source_articles (canonical_url);
create unique index if not exists source_articles_slug_unique_idx on source_articles (slug) where slug is not null;
create index if not exists source_articles_sort_idx on source_articles (coalesce(published_at, crawled_at) desc);
create unique index if not exists entity_timeline_items_entity_window_unique_idx on entity_timeline_items (entity_id, window_start, window_end);
create index if not exists entity_timeline_items_entity_window_idx on entity_timeline_items (entity_id, window_start desc);
create index if not exists entity_timeline_items_window_start_idx on entity_timeline_items (window_start desc);
create index if not exists timeline_item_articles_article_idx on timeline_item_articles (article_id);
