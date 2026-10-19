-- Distributed-systems schema for the OmniSignal mini-project.
--
-- This schema is intentionally separate from supabase/migrations/: it holds
-- coordinator/worker/run coordination state for the distributed execution
-- layer, not financial research or user data. It runs against a local
-- Postgres instance in Docker Compose / Kubernetes, never against the
-- production Supabase project.

create table coordinators (
    id text primary key,
    host text not null,
    port integer not null,
    role text not null default 'unknown',
    epoch bigint not null default 0,
    lamport_timestamp bigint not null default 0,
    last_beacon_sent_at timestamptz,
    last_beacon_from_leader_at timestamptz,
    registered_at timestamptz not null default now(),
    runtime_kind text not null default 'unknown',
    runtime_ref text
);

create table leadership_state (
    singleton boolean primary key default true check (singleton),
    epoch bigint not null default 0,
    leader_id text,
    updated_at timestamptz not null default now()
);

insert into leadership_state (singleton, epoch, leader_id) values (true, 0, null);

create table workers (
    id text primary key,
    worker_group text not null,
    host text not null,
    port integer not null,
    status text not null default 'unavailable',
    last_heartbeat_at timestamptz,
    last_heartbeat_receiver_id text,
    last_sequence bigint not null default 0,
    active_attempts integer not null default 0,
    registered_at timestamptz not null default now(),
    runtime_kind text not null default 'unknown',
    runtime_ref text
);

create index workers_group_idx on workers (worker_group);

create table research_runs (
    id uuid primary key,
    ticker text not null,
    state text not null default 'created',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    leader_epoch bigint not null,
    generation bigint not null default 1,
    capabilities jsonb not null default '[]'::jsonb,
    result jsonb
);

create index research_runs_state_idx on research_runs (state);
create index research_runs_ticker_idx on research_runs (ticker);

create table worker_attempts (
    id uuid primary key,
    run_id uuid not null references research_runs (id) on delete cascade,
    worker_group text not null,
    worker_id text,
    capability text not null,
    status text not null default 'pending',
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    latency_ms double precision,
    evidence jsonb not null default '[]'::jsonb,
    error jsonb
);

create index worker_attempts_run_idx on worker_attempts (run_id);

create table protocol_events (
    id bigserial primary key,
    process_id text not null,
    process_role text not null,
    event_type text not null,
    lamport_timestamp bigint not null,
    wall_clock timestamptz not null default now(),
    run_id uuid,
    request_id uuid,
    detail jsonb not null default '{}'::jsonb
);

create index protocol_events_wall_clock_idx on protocol_events (wall_clock desc);
create index protocol_events_process_idx on protocol_events (process_id);
create index protocol_events_run_idx on protocol_events (run_id);

create table operator_actions (
    id bigserial primary key,
    actor text not null,
    action text not null,
    target text not null,
    accepted boolean not null,
    result text not null,
    detail jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index operator_actions_created_idx on operator_actions (created_at desc);
