alter table coordinators add column last_seen_at timestamptz;

update coordinators set last_seen_at = registered_at where last_seen_at is null;
