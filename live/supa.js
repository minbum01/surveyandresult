/* ──────────────────────────────────────────────────────────────
 * supa.js — Supabase 클라이언트 설정 (공통)
 *
 * 사용: 각 페이지 <head> 에 supabase-js CDN 먼저, 그다음 이 파일.
 *   <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
 *   <script src="supa.js"></script>
 *
 * ⚠️ 배포 전 아래 두 값을 채울 것:
 *   Supabase 대시보드 → Project Settings → API
 *   - Project URL  → SUPABASE_URL
 *   - anon public  → SUPABASE_ANON   (공개 가능. service_role 키는 절대 여기 금지!)
 * ────────────────────────────────────────────────────────────── */
(function (global) {
  'use strict';

  const SUPABASE_URL  = 'https://YOUR-PROJECT.supabase.co';   // TODO: 채우기
  const SUPABASE_ANON = 'YOUR-ANON-PUBLIC-KEY';               // TODO: 채우기 (anon, 공개 OK)

  const READY = !SUPABASE_URL.includes('YOUR-PROJECT')
             && !SUPABASE_ANON.includes('YOUR-ANON');

  if (READY && global.supabase && typeof global.supabase.createClient === 'function') {
    global.supa = global.supabase.createClient(SUPABASE_URL, SUPABASE_ANON);
  } else {
    // 키 미설정 또는 CDN 미로드 → 로컬 개발(localStorage 폴백)에서도 안 깨지게 null
    global.supa = null;
    if (!READY) console.info('[supa] Supabase 키 미설정 — 로컬 모드(localStorage)로 동작');
  }

  // 페이지/시험 종류 (각 페이지에서 필요 시 덮어쓰기)
  //   공무원: result.html → '공무원' / 경찰: police_result.html → '경찰'
  global.CURRENT_EXAM = global.CURRENT_EXAM || '공무원';
})(window);
