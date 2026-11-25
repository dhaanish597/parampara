-- 0001_init.sql: Core Parampara schema (BUILD_PLAN 11.1)

create extension if not exists pgcrypto;
create extension if not exists vector;

create type org_kind as enum ('factory', 'training_centre', 'lab', 'platform');
create type member_role as enum ('owner', 'supervisor', 'master', 'trainee', 'lab_buyer');
create type skill_status as enum ('draft', 'in_review', 'approved', 'retired');
create type clip_kind as enum ('demo', 'session', 'frame', 'audio');
create type session_mode as enum ('full', 'hint', 'watch', 'exam');
create type session_status as enum ('active', 'completed', 'aborted');
create type consent_action as enum ('grant', 'revoke');
create type cred_status as enum ('active', 'revoked');
create type royalty_role as enum ('master', 'parent_master', 'trainee', 'reviewer', 'factory', 'platform');
create type payout_provider as enum ('razorpayx_test', 'simulated');
create type job_status as enum ('queued', 'running', 'done', 'failed');

create table orgs (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  city text not null default 'Indore',
  kind org_kind not null,
  is_demo boolean not null default false,
  created_at timestamptz not null default now()
);

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null,
  pseudonym text not null unique,
  preferred_lang text not null default 'hi',
  upi_vpa text,
  created_at timestamptz not null default now()
);

create table memberships (
  org_id uuid not null references orgs(id) on delete cascade,
  user_id uuid not null references profiles(id) on delete cascade,
  role member_role not null,
  primary key (org_id, user_id, role)
);

create table clips (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs(id),
  owner_user_id uuid not null references profiles(id),
  kind clip_kind not null,
  storage_path text not null,
  mime text not null,
  sha256 text,
  bytes bigint,
  duration_ms integer,
  width integer,
  height integer,
  fps real,
  blurred boolean not null default false,
  finalized_at timestamptz,
  created_at timestamptz not null default now()
);

create table skills (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs(id),
  slug text not null,
  current_version integer,
  created_by uuid not null references profiles(id),
  created_at timestamptz not null default now(),
  unique (org_id, slug)
);

create table skill_versions (
  id uuid primary key default gen_random_uuid(),
  skill_id uuid not null references skills(id) on delete cascade,
  version integer not null,
  status skill_status not null default 'draft',
  graph jsonb not null,
  author_user_id uuid not null references profiles(id),
  parent_version_id uuid references skill_versions(id),
  source_clip_id uuid references clips(id),
  approved_by uuid references profiles(id),
  approved_at timestamptz,
  graph_sha256 text,
  embedding vector(768),
  created_at timestamptz not null default now(),
  unique (skill_id, version)
);

create table compile_runs (
  id uuid primary key default gen_random_uuid(),
  skill_id uuid not null references skills(id),
  source_clip_id uuid not null references clips(id),
  status text not null default 'queued',
  revision integer not null default 0,
  draft_graph jsonb,
  lint_issues jsonb not null default '[]',
  critic_issues jsonb not null default '[]',
  langgraph_thread_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table sessions (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references orgs(id),
  skill_version_id uuid not null references skill_versions(id),
  trainee_user_id uuid not null references profiles(id),
  mode session_mode not null,
  status session_status not null default 'active',
  calibration jsonb,
  summary jsonb,
  clip_id uuid references clips(id),
  live_model text not null,
  started_at timestamptz not null default now(),
  ended_at timestamptz
);

create table step_events (
  id bigserial primary key,
  session_id uuid not null references sessions(id) on delete cascade,
  step_id text,
  type text not null,
  t_ms integer not null,
  payload jsonb not null default '{}',
  frame_sha256 text,
  created_at timestamptz not null default now()
);
create index on step_events (session_id, t_ms);

create table mastery (
  user_id uuid not null references profiles(id),
  skill_version_id uuid not null references skill_versions(id),
  step_id text not null,
  p_learned real not null,
  observations integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (user_id, skill_version_id, step_id)
);

create table credentials (
  id uuid primary key default gen_random_uuid(),
  subject_user_id uuid not null references profiles(id),
  skill_version_id uuid not null references skill_versions(id),
  vc jsonb not null,
  status cred_status not null default 'active',
  evidence_root text not null,
  cosigned_by uuid not null references profiles(id),
  issued_at timestamptz not null default now()
);

create table consent_chain_head (
  id integer primary key default 1 check (id = 1),
  last_seq bigint not null default 0,
  last_hash text not null default repeat('0', 64)
);
insert into consent_chain_head default values;

create table consent_records (
  id uuid primary key default gen_random_uuid(),
  seq bigint not null unique,
  subject_user_id uuid not null references profiles(id),
  action consent_action not null,
  clip_id uuid references clips(id),
  session_id uuid references sessions(id),
  scopes text[] not null,
  purpose text not null,
  expires_at timestamptz,
  notice_version text not null,
  comprehension_passed boolean not null,
  prev_hash text not null,
  hash text not null unique,
  created_at timestamptz not null
);

create table datasets (
  id uuid primary key default gen_random_uuid(),
  skill_version_id uuid not null references skill_versions(id),
  scope text not null,
  name text not null,
  episode_count integer not null,
  hours real not null,
  export_path text not null,
  data_card_md text not null,
  created_at timestamptz not null default now()
);

create table dataset_episodes (
  dataset_id uuid not null references datasets(id) on delete cascade,
  episode_index integer not null,
  session_id uuid not null references sessions(id),
  contributor_user_id uuid not null references profiles(id),
  role text not null check (role in ('master', 'trainee')),
  consent_record_id uuid not null references consent_records(id),
  meta jsonb not null,
  primary key (dataset_id, episode_index)
);

create table licences (
  id uuid primary key default gen_random_uuid(),
  dataset_id uuid not null references datasets(id),
  buyer_org_id uuid not null references orgs(id),
  price_paise bigint not null check (price_paise > 0),
  terms jsonb not null,
  watermark_id text not null unique,
  created_by uuid not null references profiles(id),
  created_at timestamptz not null default now()
);

create table royalty_events (
  id uuid primary key default gen_random_uuid(),
  licence_id uuid not null references licences(id),
  role royalty_role not null,
  beneficiary_user_id uuid references profiles(id),
  beneficiary_org_id uuid references orgs(id),
  amount_paise bigint not null check (amount_paise >= 0),
  basis jsonb not null,
  created_at timestamptz not null default now(),
  check (beneficiary_user_id is not null or beneficiary_org_id is not null)
);

create table payouts (
  id uuid primary key default gen_random_uuid(),
  royalty_event_id uuid not null references royalty_events(id),
  provider payout_provider not null,
  provider_ref text not null,
  status text not null,
  raw jsonb,
  created_at timestamptz not null default now()
);

create table idempotency_keys (
  key text not null,
  route text not null,
  user_id uuid not null references profiles(id),
  request_sha256 text not null,
  response jsonb not null,
  created_at timestamptz not null default now(),
  primary key (key, route, user_id)
);

create table jobs (
  id uuid primary key default gen_random_uuid(),
  kind text not null,
  payload jsonb not null,
  status job_status not null default 'queued',
  attempts integer not null default 0,
  last_error text,
  run_after timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on jobs (status, run_after);

create table model_calls (
  id bigserial primary key,
  agent text not null,
  model text not null,
  purpose text not null,
  input_tokens integer,
  output_tokens integer,
  latency_ms integer,
  cost_usd numeric(12, 6),
  ok boolean not null,
  error text,
  session_id uuid,
  compile_run_id uuid,
  dataset_id uuid,
  langfuse_trace_id text,
  created_at timestamptz not null default now()
);

create table trace_events (
  id bigserial primary key,
  session_id uuid,
  compile_run_id uuid,
  dataset_id uuid,
  agent text not null,
  kind text not null,
  summary text not null,
  model text,
  latency_ms integer,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);
create index on trace_events (session_id, id);
create index on trace_events (compile_run_id, id);
