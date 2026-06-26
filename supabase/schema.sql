-- ============================================================
-- 합격 리포트 — Supabase 스키마 (큐레이션 + 인쇄큐 + 스테이션)
-- 사용법: Supabase 대시보드 → SQL Editor → 전체 붙여넣고 RUN
-- 설계 출처: 클라우드_인쇄시스템_설계.md §3
-- ============================================================

-- ---------- 테이블 ----------

-- 큐레이션(핀/제외): 시험별 1행. data = 기존 admin_curation_v2 전체 구조(JSON)
create table if not exists curation (
  exam       text primary key,                 -- '공무원' | '경찰' | '소방'
  data       jsonb not null default '{}',
  updated_at timestamptz not null default now()
);

-- 인쇄 작업 큐
create table if not exists print_jobs (
  id         bigint generated always as identity primary key,
  exam       text not null,
  answers    jsonb not null,                   -- passNoteAnswers (8슬롯 / 경찰 answersByQ)
  cur        jsonb,                            -- (선택) 인쇄 시점 큐레이션 스냅샷
  ticket     int,                              -- 전체 공통 출력번호(표시용)
  device     text,                             -- 어느 스탠바이미(태블릿)가 보냈는지
  device_seq int,                              -- 그 기기에서 몇 번째 문서인지 (라벨 = device-device_seq, 예: C-3)
  seed       bigint,                            -- 결정적 렌더 시드(화면=종이=재인쇄 동일하게 후기선택 고정)
  status     text not null default 'pending',  -- pending|printing|done|error
  station    text,                             -- 어느 프린트 스테이션(에이전트)이 처리했는지
  error      text,
  created_at timestamptz not null default now(),
  claimed_at timestamptz,
  printed_at timestamptz
);
create index if not exists print_jobs_status_idx on print_jobs (status, created_at);

-- 스테이션 상태(heartbeat)
create table if not exists stations (
  id        text primary key,                  -- 'A' | 'B'
  last_seen timestamptz,
  busy_job  bigint
);

-- 출력번호 시퀀스 (전체 공통)
create sequence if not exists print_ticket_seq;

-- 기기별 순번 카운터 (리셋 없이 계속 증가 — 라벨 C-3 의 '3')
create table if not exists device_counters (
  device text primary key,                     -- 'A' | 'B' | 'C' ...
  n      int  not null default 0
);

-- ---------- RPC (함수) ----------

-- 결과 페이지(anon)가 인쇄 등록 → {ticket,device,seq,label} 반환. 테이블 직접 접근 없이 이걸로만.
--   label = device-seq (예: 'C-3') → 스탠바이미/picker/관리자 공통 식별자.
create or replace function enqueue_print(p_exam text, p_answers jsonb, p_cur jsonb, p_device text default null, p_seed bigint default null)
returns jsonb
language plpgsql security definer
as $$
declare
  t   int;
  s   int;
  dev text := coalesce(nullif(p_device, ''), '?');
begin
  t := nextval('print_ticket_seq');
  -- 기기별 순번 원자적 증가 (동시 출력에도 충돌 없음)
  insert into device_counters(device, n) values (dev, 1)
    on conflict (device) do update set n = device_counters.n + 1
    returning n into s;
  insert into print_jobs(exam, answers, cur, ticket, device, device_seq, seed)
    values (p_exam, p_answers, p_cur, t, dev, s, p_seed);
  return jsonb_build_object('ticket', t, 'device', dev, 'seq', s, 'label', dev || '-' || s);
end; $$;

-- 스테이션이 다음 작업을 원자적으로 선점 (2대가 같은 걸 못 가져감)
create or replace function claim_next_job(p_station text)
returns print_jobs
language plpgsql
as $$
declare job print_jobs;
begin
  -- 멈춘 작업 재큐: printing 60초 초과 → pending 복귀
  update print_jobs set status='pending', station=null, claimed_at=null
   where status='printing' and claimed_at < now() - interval '60 seconds';

  update print_jobs
     set status='printing', station=p_station, claimed_at=now()
   where id = (
     select id from print_jobs
      where status='pending'
      order by created_at
      for update skip locked          -- ← 핵심: 무충돌 작업큐
      limit 1
   )
  returning * into job;

  insert into stations(id,last_seen,busy_job) values (p_station, now(), job.id)
    on conflict (id) do update set last_seen=now(), busy_job=excluded.busy_job;

  return job;   -- NULL이면 대기 작업 없음
end; $$;

create or replace function complete_job(p_id bigint)
returns void language sql as $$
  update print_jobs set status='done', printed_at=now() where id=p_id;
$$;

create or replace function fail_job(p_id bigint, p_err text)
returns void language sql as $$
  update print_jobs set status='error', error=p_err where id=p_id;
$$;

-- 관리자 재인쇄: error/done → pending 복귀
create or replace function requeue_job(p_id bigint)
returns void language sql as $$
  update print_jobs set status='pending', station=null, claimed_at=null, error=null where id=p_id;
$$;

-- ---------- RLS (보안 정책) ----------

alter table curation   enable row level security;
alter table print_jobs enable row level security;
alter table stations   enable row level security;

-- 큐레이션: 공개 읽기 / 로그인(관리자)만 쓰기
drop policy if exists curation_read  on curation;
drop policy if exists curation_write on curation;
create policy curation_read  on curation for select to anon, authenticated using (true);
create policy curation_write on curation for all    to authenticated using (true) with check (true);

-- 인쇄 작업: 직접 테이블 접근은 '로그인(관리자 모니터)' 읽기만.
--   - anon 등록은 enqueue_print(security definer)로만
--   - 스테이션 claim/complete는 service_role 키(RLS 우회)로
drop policy if exists jobs_admin_read on print_jobs;
drop policy if exists stations_read   on stations;
create policy jobs_admin_read on print_jobs for select to authenticated using (true);
create policy stations_read   on stations  for select to authenticated using (true);

-- anon이 호출 가능한 함수만 grant
grant execute on function enqueue_print(text,jsonb,jsonb,text,bigint) to anon, authenticated;
grant execute on function requeue_job(bigint) to authenticated;
-- claim_next_job / complete_job / fail_job 은 service_role(스테이션)만 — anon/authenticated grant 안 함

-- ============================================================
-- 실행 후 할 일:
--  1) Authentication → Users → 관리자 이메일/비번 1개 수동 생성
--  2) Project Settings → API 에서 URL / anon key / service_role key 확보
--     - anon key  → live/supa.js (공개 OK)
--     - service_role key → 스테이션 PC print_agent.py 환경변수에만 (절대 깃/프런트 금지)
-- ============================================================
