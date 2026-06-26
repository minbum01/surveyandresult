-- ============================================================
-- 마이그레이션: 인쇄 모니터 실시간(Realtime) 활성화
-- 사용법: Supabase 대시보드 → SQL Editor → New query → 전체 붙여넣고 RUN
-- 목적: print_admin.html 이 폴링 대신 즉시 갱신되도록
--       print_jobs / stations 변경을 실시간으로 푸시받게 함.
-- (schema.sql 의 RLS 정책이 그대로 적용 — 로그인 관리자만 이벤트 수신)
-- ============================================================

-- Supabase 기본 realtime publication 에 두 테이블 추가.
-- (이미 들어있으면 'already member' 오류가 날 수 있는데, 그땐 그 줄은 건너뛰면 됨)
alter publication supabase_realtime add table print_jobs;
alter publication supabase_realtime add table stations;

-- 확인: 아래 쿼리에 print_jobs, stations 가 보이면 성공
-- select tablename from pg_publication_tables where pubname = 'supabase_realtime';
