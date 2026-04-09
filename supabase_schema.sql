create table if not exists tf_leads (
  id text primary key,
  name text not null,
  email text not null,
  whatsapp text,
  source text,
  created_at timestamptz not null default now()
);

create index if not exists tf_leads_email_idx on tf_leads (email);
create index if not exists tf_leads_created_at_idx on tf_leads (created_at desc);

create table if not exists tf_automation_tasks (
  id text primary key,
  name text not null,
  status text not null,
  activity text,
  created_at timestamptz not null default now()
);

create index if not exists tf_automation_tasks_created_at_idx on tf_automation_tasks (created_at desc);

create table if not exists tf_topics (
  id text primary key,
  title text not null,
  link text,
  source text,
  created_at timestamptz not null default now(),
  used boolean not null default false,
  used_at timestamptz,
  post_id text
);

create index if not exists tf_topics_used_idx on tf_topics (used);
create index if not exists tf_topics_created_at_idx on tf_topics (created_at desc);

create table if not exists tf_posts (
  id text primary key,
  title text not null,
  slug text not null unique,
  status text not null,
  provider text,
  niche text,
  created_at timestamptz not null default now(),
  published_at timestamptz,
  content_html text not null,
  social_assets_raw text
);

create index if not exists tf_posts_status_idx on tf_posts (status);
create index if not exists tf_posts_published_at_idx on tf_posts (published_at desc);

create table if not exists tf_pageviews (
  path text primary key,
  count bigint not null default 0
);

create table if not exists tf_pageviews_daily (
  date date not null,
  path text not null,
  count bigint not null default 0,
  primary key (date, path)
);

create table if not exists tf_referrers (
  referrer text primary key,
  count bigint not null default 0
);
