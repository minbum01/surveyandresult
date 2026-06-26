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

  const SUPABASE_URL  = 'https://zxjhgcumweqaxcemoiga.supabase.co';
  const SUPABASE_ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp4amhnY3Vtd2VxYXhjZW1vaWdhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI0MTExNjksImV4cCI6MjA5Nzk4NzE2OX0.vRETMCzDvd0HONqz9rlDXFqrF_ZQP_kp-wURphltsQo';

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

  // ── 기기(스탠바이미) 식별 ──
  // 각 태블릿을 1회 `...?d=탭A` 로 열면 localStorage에 저장 → 이후 모든 페이지·인쇄에 따라붙음.
  try {
    const _d = new URLSearchParams(location.search).get('d');
    if (_d) localStorage.setItem('device_id', _d);
  } catch (e) {}
  global.DEVICE_ID = (function () {
    try { return localStorage.getItem('device_id') || ''; } catch (e) { return ''; }
  })();

  // ── 인쇄 큐 등록 (결과페이지 공용) ──
  // 결과 도달 후 '출력' 클릭 → Supabase print_jobs 큐에 등록 → 메인컴 print_agent가 받아 인쇄.
  // 반환: { ticket, device, seq, label }  (label = 'C-3' 형식, 기기-기기별순번). 실패 시 throw.
  global.enqueuePrint = async function (exam, answers, cur, seed) {
    if (!global.supa) throw new Error('Supabase 미연결(supa.js 키 확인)');
    const { data, error } = await global.supa.rpc('enqueue_print', {
      p_exam: exam, p_answers: answers, p_cur: cur, p_device: global.DEVICE_ID || null,
      p_seed: (seed == null ? null : Number(seed))
    });
    if (error) throw new Error(error.message);
    // 구버전 함수(int 반환) 호환: 숫자면 객체로 감싼다.
    if (data != null && typeof data === 'object') return data;
    return { ticket: data, device: global.DEVICE_ID || '', seq: null, label: '#' + data };
  };
})(window);
