-- 0002_rls.sql: Row-level security and append-only consent guard (BUILD_PLAN 11.2)

create or replace function public.is_member(target_org uuid, allowed_roles member_role[])
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from public.memberships m
    where m.org_id = target_org
      and m.user_id = auth.uid()
      and (array_length(allowed_roles, 1) is null or m.role = any(allowed_roles))
  );
$$;

-- Append-only enforcement on consent_records (blocks UPDATE/DELETE/TRUNCATE even for service_role)
create or replace function public.forbid_consent_mutation()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  raise exception 'consent_records is append-only; updates, deletes, and truncates are forbidden';
end;
$$;

create trigger trg_consent_records_no_update
  before update or delete on public.consent_records
  for each row execute function public.forbid_consent_mutation();

create trigger trg_consent_records_no_truncate
  before truncate on public.consent_records
  for each statement execute function public.forbid_consent_mutation();

revoke insert, update, delete, truncate on public.consent_records from public, anon, authenticated;
revoke update, delete, truncate on public.consent_records from service_role;

-- Enable RLS on every table
alter table orgs enable row level security;
alter table profiles enable row level security;
alter table memberships enable row level security;
alter table clips enable row level security;
alter table skills enable row level security;
alter table skill_versions enable row level security;
alter table compile_runs enable row level security;
alter table sessions enable row level security;
alter table step_events enable row level security;
alter table mastery enable row level security;
alter table credentials enable row level security;
alter table consent_chain_head enable row level security;
alter table consent_records enable row level security;
alter table datasets enable row level security;
alter table dataset_episodes enable row level security;
alter table licences enable row level security;
alter table royalty_events enable row level security;
alter table payouts enable row level security;
alter table idempotency_keys enable row level security;
alter table jobs enable row level security;
alter table model_calls enable row level security;
alter table trace_events enable row level security;

create policy orgs_select on orgs for select
  using (public.is_member(id, array[]::member_role[]));

create policy profiles_select on profiles for select
  using (id = auth.uid());

create policy memberships_select on memberships for select
  using (user_id = auth.uid() or public.is_member(org_id, array['owner','supervisor']::member_role[]));

create policy clips_select on clips for select
  using (
    owner_user_id = auth.uid()
    or public.is_member(org_id, array['owner','supervisor']::member_role[])
  );

create policy skills_select on skills for select
  using (public.is_member(org_id, array[]::member_role[]));

create policy skill_versions_select on skill_versions for select
  using (
    exists (
      select 1 from skills s
      where s.id = skill_versions.skill_id
        and public.is_member(s.org_id, array[]::member_role[])
    )
  );

create policy compile_runs_select on compile_runs for select
  using (
    exists (
      select 1 from skills s
      where s.id = compile_runs.skill_id
        and public.is_member(s.org_id, array[]::member_role[])
    )
  );

create policy sessions_select on sessions for select
  using (
    trainee_user_id = auth.uid()
    or public.is_member(org_id, array['owner','supervisor']::member_role[])
  );

create policy step_events_select on step_events for select
  using (
    exists (
      select 1 from sessions s
      where s.id = step_events.session_id
        and (
          s.trainee_user_id = auth.uid()
          or public.is_member(s.org_id, array['owner','supervisor']::member_role[])
        )
    )
  );

create policy mastery_select on mastery for select
  using (
    user_id = auth.uid()
    or exists (
      select 1 from skill_versions sv
      join skills s on s.id = sv.skill_id
      where sv.id = mastery.skill_version_id
        and public.is_member(s.org_id, array['owner','supervisor']::member_role[])
    )
  );

create policy credentials_select on credentials for select
  using (
    subject_user_id = auth.uid()
    or exists (
      select 1 from skill_versions sv
      join skills s on s.id = sv.skill_id
      where sv.id = credentials.skill_version_id
        and public.is_member(s.org_id, array['owner','supervisor']::member_role[])
    )
  );

create policy consent_records_select on consent_records for select
  using (subject_user_id = auth.uid());

create policy datasets_select on datasets for select
  using (
    exists (
      select 1 from skill_versions sv
      join skills s on s.id = sv.skill_id
      where sv.id = datasets.skill_version_id
        and public.is_member(s.org_id, array['owner','supervisor']::member_role[])
    )
    or exists (
      select 1 from licences l
      where l.dataset_id = datasets.id
        and public.is_member(l.buyer_org_id, array['lab_buyer','owner','supervisor']::member_role[])
    )
  );

create policy dataset_episodes_select on dataset_episodes for select
  using (
    exists (
      select 1 from datasets d
      join skill_versions sv on sv.id = d.skill_version_id
      join skills s on s.id = sv.skill_id
      where d.id = dataset_episodes.dataset_id
        and public.is_member(s.org_id, array['owner','supervisor']::member_role[])
    )
    or exists (
      select 1 from licences l
      where l.dataset_id = dataset_episodes.dataset_id
        and public.is_member(l.buyer_org_id, array['lab_buyer','owner','supervisor']::member_role[])
    )
  );

create policy licences_select on licences for select
  using (
    public.is_member(buyer_org_id, array['lab_buyer','owner','supervisor']::member_role[])
  );

create policy royalty_events_select on royalty_events for select
  using (
    beneficiary_user_id = auth.uid()
    or (
      beneficiary_org_id is not null
      and public.is_member(beneficiary_org_id, array['owner']::member_role[])
    )
  );

create policy payouts_select on payouts for select
  using (
    exists (
      select 1 from royalty_events re
      where re.id = payouts.royalty_event_id
        and (
          re.beneficiary_user_id = auth.uid()
          or (
            re.beneficiary_org_id is not null
            and public.is_member(re.beneficiary_org_id, array['owner']::member_role[])
          )
        )
    )
  );
