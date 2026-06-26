-- ============================================================
-- 마이그레이션: 기기별 순번(라벨 C-3) + 결정적 렌더 시드(seed) 추가
--   - print_jobs.device_seq : 그 기기에서 몇 번째 문서인지
--   - print_jobs.seed       : 후기 선택을 고정하는 시드(화면=종이=재인쇄 동일)
--   - device_counters       : 기기별 카운터(리셋 없이 계속 증가)
--   - enqueue_print         : int → jsonb{ticket,device,seq,label} 반환 + p_seed 인자
-- 사용법: Supabase 대시보드 → SQL Editor → 전체 붙여넣고 RUN
-- (schema.sql 을 처음부터 다시 돌리는 경우엔 이 파일 불필요 — 이미 반영돼 있음)
-- ============================================================

-- 1) 컬럼 추가
alter table print_jobs add column if not exists device_seq int;
alter table print_jobs add column if not exists seed       bigint;

-- 2) 기기별 카운터 테이블
create table if not exists device_counters (
  device text primary key,                     -- 'A' | 'B' | 'C' ...
  n      int  not null default 0
);

-- 3) enqueue_print 교체 (반환 타입 변경 → CREATE OR REPLACE 불가, DROP 먼저)
drop function if exists enqueue_print(text, jsonb, jsonb, text);
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

-- 4) anon/authenticated 재grant (DROP 했으므로 새 시그니처로 다시)
grant execute on function enqueue_print(text, jsonb, jsonb, text, bigint) to anon, authenticated;

-- 확인:
--   select enqueue_print('공무원', '[]'::jsonb, null, 'C', 12345);   -- → {"label":"C-1", ...}
--   select * from device_counters;
