-- ============================================================
-- 마이그레이션: 인쇄큐에 '어느 스탠바이미(device)' 추적 추가
-- 사용법: Supabase 대시보드 → SQL Editor → New query → 전체 붙여넣고 RUN
-- (이미 schema.sql 을 RUN 한 프로젝트에 '추가로' 적용하는 변경분)
-- ============================================================

-- 1) print_jobs 에 device 컬럼 (어느 태블릿이 보냈는지)
alter table print_jobs add column if not exists device text;

-- 2) enqueue_print 에 p_device 인자 추가 (기존 3인자 함수는 제거)
drop function if exists enqueue_print(text, jsonb, jsonb);
create or replace function enqueue_print(p_exam text, p_answers jsonb, p_cur jsonb, p_device text default null)
returns int
language plpgsql security definer
as $$
declare t int;
begin
  t := nextval('print_ticket_seq');
  insert into print_jobs(exam, answers, cur, ticket, device)
    values (p_exam, p_answers, p_cur, t, p_device);
  return t;
end; $$;

-- 3) anon(결과페이지)·authenticated(관리자) 호출 허용
grant execute on function enqueue_print(text, jsonb, jsonb, text) to anon, authenticated;

-- 확인: 아래가 출력번호(정수) 1개를 반환하면 성공 (테스트행 1건 생성됨 → 모니터에서 삭제/완료 처리 가능)
-- select enqueue_print('공무원', '[]'::jsonb, null, '테스트탭');
