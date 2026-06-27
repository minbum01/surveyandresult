/* ──────────────────────────────────────────────────────────────
 * curation_sync.js — 관리자 큐레이션 ↔ 결과 페이지 실시간 연동
 *
 * 관리자 페이지(no01_폴백_매칭수.html)가 localStorage['admin_curation_v2']에
 * 저장하는 핀/제외 데이터를, 결과 페이지(result/persona/page1_right)가
 * 같은 출처(localhost)에서 읽어 즉시 반영한다.
 *
 * 사용법 (결과 페이지):
 *   1) <script src="curation_sync.js"></script> 를 인라인 스크립트보다 먼저 로드
 *   2) 영역별 후보 풀을 감싼다:
 *        const combo = Curation.comboFromAnswers(A);   // A = passNoteAnswers 배열(8)
 *        const passResult = pickPassage( Curation.applyPool('no.01', combo, ps) );
 *   3) 실시간 갱신:
 *        Curation.onChange(() => render(LOADED));       // 캐시 데이터로 재렌더
 * ────────────────────────────────────────────────────────────── */
(function (global) {
  'use strict';

  const STORE_KEY = 'admin_curation_v2';
  // 시험별 저장소 분리: 경찰은 별도 키, 공무원(기본)은 기존 키 그대로(영향 0).
  //   페이지에서 window.CURRENT_EXAM = '경찰' 설정 시 경찰 키 사용.
  function activeKey() {
    return (global.CURRENT_EXAM === '경찰') ? STORE_KEY + '_경찰' : STORE_KEY;
  }

  // 관리자 AREAS_DEFAULT와 동일 — store.areas가 없을 때의 matchKeys 폴백
  const AREAS_DEFAULT = {
    'no.01': { name: '동일경로 후기',  matchKeys: ['Q1', 'Q3', 'Q4'] },
    'no.02': { name: '패턴 인용구',    matchKeys: ['Q5', 'Q7', 'Q8'] },
    'no.06': { name: '같은 출발점',    matchKeys: ['Q1', 'Q4'] },
    'no.07': { name: '다잡은 한 마디', matchKeys: ['Q8'] },
    'no.08': { name: '첫 한 달 풍경',  matchKeys: ['Q1', 'Q3'] },
    'no.09': { name: '포기 직전',      matchKeys: ['Q1'] },
    'no.10': { name: '꾸준함 한 줄',   matchKeys: ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8'] },
  };

  let _remote = null;   // Supabase에서 불러온 큐레이션(메모리 캐시)

  function getStore() {
    try {
      // 1) 인쇄모드(헤드리스) 주입본  2) Supabase 캐시  3) localStorage(폴백/관리자 로컬)
      if (global.__PRINT_CUR__ != null) {
        const o = JSON.parse(global.__PRINT_CUR__ || '{}');
        return (o && typeof o === 'object') ? o : {};
      }
      if (!global.__CUR_LOCAL__ && _remote != null) return _remote;  // ?local 강제 시 서버캐시 건너뛰고 localStorage
      const o = JSON.parse(localStorage.getItem(activeKey()) || '{}');
      return (o && typeof o === 'object') ? o : {};
    } catch { return {}; }
  }

  const EXAM = () => global.CURRENT_EXAM || '공무원';

  // Supabase에서 이 시험의 큐레이션을 읽어 캐시 → 결과페이지 재렌더(curation:changed)
  async function loadRemote() {
    if (!global.supa) return false;
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), 5000);
    try {
      const { data, error } = await global.supa
        .from('curation').select('data').eq('exam', EXAM()).abortSignal(ac.signal).maybeSingle();
      clearTimeout(timer);
      if (error) { console.warn('[Curation] loadRemote', error.message); return false; }
      // 행이 없거나 빈 데이터면 null → getStore가 localStorage로 폴백(빈 서버가 로컬 핀을 가리지 않게)
      _remote = (data && data.data && typeof data.data === 'object' && Object.keys(data.data).length) ? data.data : null;
      try { global.dispatchEvent(new Event('curation:changed')); } catch (e) {}
      return true;
    } catch (e) { clearTimeout(timer); console.warn('[Curation] loadRemote', e); return false; }
  }

  // 큐레이션 전체를 Supabase에 저장(관리자). 로그인(authenticated) 필요.
  async function saveRemote(store) {
    if (!global.supa) return { ok: false, error: 'supa 없음' };
    try {
      const { error } = await global.supa
        .from('curation').upsert({ exam: EXAM(), data: store, updated_at: new Date().toISOString() });
      return error ? { ok: false, error: error.message } : { ok: true };
    } catch (e) { return { ok: false, error: String(e) }; }
  }

  function areaDef(area) {
    // no.10 은 빌드 기준 키를 강제(공무원=직렬 Q3 / 경찰=수험팁 직렬무관). store의 옛 키(전체 Q) 무시.
    if (area === 'no.10') {
      return (EXAM() === '경찰')
        ? { name: '경찰 수험 팁', matchKeys: [] }
        : { name: '내 직렬 팁', matchKeys: ['Q3'] };
    }
    const store = getStore();
    return (store.areas && store.areas[area]) || AREAS_DEFAULT[area] || { matchKeys: [] };
  }

  // 값 정규화 — Q7처럼 배열(복수선택)이면 정렬 후 콤마결합해 비교 가능하게
  function norm(v) {
    if (Array.isArray(v)) return [...v].filter(Boolean).sort().join(',');
    return v == null ? '' : String(v);
  }

  // passNoteAnswers 배열(8) → {Q1..Q8} (tagId 기준). Q7만 배열(복수)
  function comboFromAnswers(A) {
    const tag = (i) => (A && A[i] && A[i][0] && A[i][0].tagId) || '';
    const multi = (i) => ((A && A[i]) || []).map(x => x.tagId).filter(Boolean);
    return {
      Q1: tag(0), Q2: tag(1), Q3: tag(2), Q4: tag(3),
      Q5: tag(4), Q6: tag(5), Q7: multi(6), Q8: tag(7),
    };
  }

  function comboKey(area, combo) {
    const mk = areaDef(area).matchKeys || [];
    return mk.map(k => norm(combo[k])).join('|');
  }

  // (영역, 조합)에 핀된 후기 id 목록 — 핀 순서 유지
  function pinnedIdsFor(area, combo) {
    const mk = areaDef(area).matchKeys || [];
    const list = (getStore().pins || {})[area] || [];
    return list
      .filter(p => mk.every(k => norm(p.answers && p.answers[k]) === norm(combo[k])))
      .map(p => p.id);
  }

  // (영역, 조합)에서 제외된 후기 id 집합 — 전역 제외 + 해당 조합 로컬 제외
  function excludedIdsFor(area, combo) {
    const store = getStore();
    const ck = comboKey(area, combo);
    const local = (store.excludesCombo && store.excludesCombo[area] && store.excludesCombo[area][ck]) || [];
    const globalEx = store.excludesGlobal || [];
    return new Set([...globalEx, ...local]);
  }

  /* 후보 풀에 큐레이션 적용:
   *  - 제외된 후기는 항상 제거
   *  - 핀이 1개 이상이면 풀을 핀된 후기로만(핀 순서) 제한 → 큐레이션이 자동매칭을 이김
   *  - 핀이 없으면 제외만 반영하고 원래 풀 유지(자동매칭 그대로)
   * 풀 원소는 id 필드를 가진 후기 객체. 반환은 같은 형태의 배열. */
  // 영역별 노출 개수 — store.areas[area].show 우선, 없으면 기본값
  // no.06(같은 출발점)은 박스 1개만 (사용자 요청)
  const DEFAULT_SHOW = { 'no.06': 1 };
  function displayCount(area) {
    const def = areaDef(area);
    const n = def && def.show;
    return (Number.isInteger(n) && n > 0) ? n : (DEFAULT_SHOW[area] || 1);
  }

  // (영역, 조합)에 핀이 있으면 핀된 후기들 중 count개를 랜덤으로 반환.
  // 핀이 없으면 null → 호출부가 기존 자동(점수) 로직을 그대로 쓰도록.
  function pinnedRandom(area, combo, pool, count) {
    const ids = new Set(pinnedIdsFor(area, combo));
    if (!ids.size) return null;
    const cands = (Array.isArray(pool) ? pool : []).filter(p => ids.has(p.id));
    if (!cands.length) return null;
    // 시드 RNG(window.RND)가 있으면 그걸 써서 결정적으로 — 화면=종이=재인쇄 동일
    const rnd = (typeof window !== 'undefined' && window.RND) ? window.RND : Math.random;
    for (let i = cands.length - 1; i > 0; i--) {
      const j = Math.floor(rnd() * (i + 1));
      const t = cands[i]; cands[i] = cands[j]; cands[j] = t;
    }
    return cands.slice(0, count || 1);
  }

  function applyPool(area, combo, pool) {
    if (!Array.isArray(pool)) return pool;
    const excl = excludedIdsFor(area, combo);
    const filtered = excl.size ? pool.filter(p => !excl.has(p.id)) : pool;

    const pinnedIds = pinnedIdsFor(area, combo);
    if (!pinnedIds.length) return filtered;

    const byId = new Map(filtered.map(p => [p.id, p]));
    const picked = pinnedIds.map(id => byId.get(id)).filter(Boolean);
    return picked.length ? picked : filtered;
  }

  // 다른 탭(관리자)에서 큐레이션이 바뀌면 cb 호출 → 결과 페이지 즉시 재렌더
  function onChange(cb) {
    if (typeof cb !== 'function') return;
    global.addEventListener('storage', (e) => {
      if (e.key === activeKey()) {
        try { cb(); } catch (err) { console.error('[Curation] onChange', err); }
      }
    });
    // 같은 탭 내 변경(드물게 동일 출처 다른 코드) 대비용 커스텀 이벤트
    global.addEventListener('curation:changed', () => { try { cb(); } catch (e) {} });
  }

  global.Curation = {
    STORE_KEY,
    AREAS_DEFAULT,
    getStore,
    areaDef,
    comboFromAnswers,
    comboKey,
    pinnedIdsFor,
    excludedIdsFor,
    applyPool,
    displayCount,
    pinnedRandom,
    onChange,
    loadRemote,
    saveRemote,
  };
})(window);
