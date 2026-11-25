-- 0003_views.sql: Factory Command Centre views (BUILD_PLAN 11.3 & 24)
-- No per-worker speed or ranking; learning status and step hotspots only.

create or replace view v_skill_matrix
with (security_invoker = true) as
select
  s.org_id,
  m.user_id,
  sv.id as skill_version_id,
  case
    when exists (
      select 1 from credentials c
      where c.subject_user_id = m.user_id
        and c.skill_version_id = sv.id
        and c.status = 'active'
    ) then 'certified'
    when (
      select count(*) from mastery ma
      where ma.user_id = m.user_id and ma.skill_version_id = sv.id
    ) >= greatest(1, jsonb_array_length(coalesce(sv.graph->'steps', '[]'::jsonb)))
    and (
      select min(ma.p_learned) from mastery ma
      where ma.user_id = m.user_id and ma.skill_version_id = sv.id
    ) >= 0.8 then 'exam_ready'
    when exists (
      select 1 from sessions ses
      where ses.trainee_user_id = m.user_id and ses.skill_version_id = sv.id
    ) then 'learning'
    else 'not_started'
  end as status
from skills s
join skill_versions sv on sv.skill_id = s.id and sv.status = 'approved'
join memberships m on m.org_id = s.org_id and m.role = 'trainee';

create or replace view v_time_to_competency
with (security_invoker = true) as
select
  s.org_id,
  c.subject_user_id as user_id,
  c.skill_version_id,
  min(ses.started_at) as first_session_at,
  c.issued_at as certified_at,
  extract(epoch from (c.issued_at - min(ses.started_at))) / 3600.0 as hours,
  count(ses.id)::integer as sessions_count
from credentials c
join skill_versions sv on sv.id = c.skill_version_id
join skills s on s.id = sv.skill_id
join sessions ses
  on ses.trainee_user_id = c.subject_user_id
 and ses.skill_version_id = c.skill_version_id
 and ses.started_at <= c.issued_at
where c.status = 'active'
group by s.org_id, c.subject_user_id, c.skill_version_id, c.issued_at;

create or replace view v_step_hotspots
with (security_invoker = true) as
select
  ses.org_id,
  ses.skill_version_id,
  e.step_id,
  count(distinct ses.id)::integer as runs,
  count(*) filter (where e.type in ('risk', 'failed'))::integer as error_events,
  case
    when count(distinct ses.id) = 0 then 0.0
    else (count(distinct case when e.type in ('risk', 'failed') then ses.id end))::real
         / count(distinct ses.id)::real
  end as error_rate
from sessions ses
join step_events e on e.session_id = ses.id
where e.step_id is not null
group by ses.org_id, ses.skill_version_id, e.step_id;

create or replace view v_earnings
with (security_invoker = true) as
select
  re.beneficiary_user_id as user_id,
  coalesce(sum(re.amount_paise), 0)::bigint as total_paise,
  max(p.created_at) as last_paid_at,
  count(re.id)::integer as events
from royalty_events re
left join payouts p on p.royalty_event_id = re.id and p.status = 'processed'
where re.beneficiary_user_id is not null
group by re.beneficiary_user_id;

revoke all on v_skill_matrix, v_time_to_competency, v_step_hotspots, v_earnings from public, anon, authenticated;
