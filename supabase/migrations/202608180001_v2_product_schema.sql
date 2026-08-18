create type entity_type_v2 as enum ('PLAYER', 'CLUB', 'COACH', 'COMPETITION');
create type story_status_v2 as enum ('DEVELOPING', 'CONFIRMED', 'STALE', 'CLOSED');
create type confirmation_level_v2 as enum ('SINGLE_SOURCE', 'MULTI_SOURCE', 'OFFICIAL', 'CONFLICTED');
create type publication_status_v2 as enum ('PUBLISHED', 'REJECTED');

create table sources (
  id uuid primary key,
  name text not null,
  domain_name text not null unique,
  homepage_url text,
  reliability_tier smallint not null check (reliability_tier between 1 and 5),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table articles (
  id uuid primary key,
  source_id uuid not null references sources(id),
  url text not null,
  canonical_url text not null unique,
  domain_name text not null,
  title text not null,
  description text,
  image_url text,
  published_at timestamptz,
  crawled_at timestamptz not null,
  language text not null default 'en',
  content_hash text not null,
  summary_en text,
  summary_vi text,
  event_type text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table entities (
  id uuid primary key,
  entity_type entity_type_v2 not null,
  name text not null,
  slug text not null,
  image_url text,
  description text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (entity_type, slug)
);

create table entity_aliases (
  id uuid primary key,
  entity_id uuid not null references entities(id) on delete cascade,
  alias text not null,
  normalized_alias text not null unique,
  created_at timestamptz not null default now()
);

create table stories (
  id uuid primary key,
  title_en text not null,
  title_vi text not null,
  summary_en text,
  summary_vi text,
  event_type text not null,
  status story_status_v2 not null default 'DEVELOPING',
  confirmation confirmation_level_v2 not null default 'SINGLE_SOURCE',
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table story_entities (
  story_id uuid not null references stories(id) on delete cascade,
  entity_id uuid not null references entities(id) on delete cascade,
  role text,
  created_at timestamptz not null default now(),
  primary key (story_id, entity_id)
);

create table story_sources (
  story_id uuid not null references stories(id) on delete cascade,
  article_id uuid not null references articles(id) on delete cascade,
  source_id uuid not null references sources(id),
  is_primary boolean not null default false,
  added_at timestamptz not null default now(),
  primary key (story_id, article_id)
);

create table claims (
  id uuid primary key,
  story_id uuid not null references stories(id) on delete cascade,
  article_id uuid not null references articles(id) on delete cascade,
  subject_entity_id uuid references entities(id),
  predicate text not null,
  object_entity_id uuid references entities(id),
  object_text text,
  object_value jsonb not null default '{}'::jsonb,
  statement_en text not null,
  statement_vi text,
  certainty text not null,
  evidence_quote text not null,
  evidence_start integer,
  evidence_end integer,
  created_at timestamptz not null default now()
);

create table timeline_entries (
  id uuid primary key,
  story_id uuid not null references stories(id) on delete cascade,
  happened_at timestamptz not null,
  title_en text,
  title_vi text,
  summary_en text not null,
  summary_vi text not null,
  confirmation confirmation_level_v2 not null,
  source_count integer not null default 1 check (source_count > 0),
  article_ids uuid[] not null default '{}',
  claim_ids uuid[] not null default '{}',
  created_at timestamptz not null default now()
);

create table publications (
  id uuid primary key,
  story_id uuid references stories(id) on delete set null,
  slug text not null unique,
  title_en text not null,
  title_vi text not null,
  excerpt_vi text,
  body_en text not null,
  body_vi text not null,
  cover_image_url text,
  status publication_status_v2 not null default 'PUBLISHED',
  published_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index articles_published_at_idx on articles (published_at desc);
create index articles_source_published_idx on articles (source_id, published_at desc);
create index articles_event_type_idx on articles (event_type);
create index entities_name_search_idx on entities using gin (to_tsvector('simple', name));
create index entity_aliases_entity_idx on entity_aliases (entity_id);
create index stories_last_seen_idx on stories (last_seen_at desc);
create index stories_event_type_idx on stories (event_type);
create index stories_status_idx on stories (status);
create index story_entities_entity_idx on story_entities (entity_id);
create index story_sources_article_idx on story_sources (article_id);
create index story_sources_source_idx on story_sources (source_id);
create index claims_story_idx on claims (story_id);
create index claims_article_idx on claims (article_id);
create index claims_subject_idx on claims (subject_entity_id);
create index claims_object_idx on claims (object_entity_id);
create index timeline_entries_story_time_idx on timeline_entries (story_id, happened_at desc);
create index timeline_entries_happened_at_idx on timeline_entries (happened_at desc);
create index publications_published_at_idx on publications (published_at desc);
create index publications_story_idx on publications (story_id);
