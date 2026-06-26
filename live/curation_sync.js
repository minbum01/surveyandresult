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

  function getStore() {
    try {
      // 인쇄모드(헤드리스)에서는 주입된 큐레이션을 사용 (localStorage 공유 불가)
      const raw = (global.__PRINT_CUR__ != null)
        ? global.__PRINT_CUR__
        : localStorage.getItem(STORE_KEY);
      const o = JSON.parse(raw || '{}');
      return (o && typeof o === 'object') ? o : {};
    } catch { return {}; }
  }

  function areaDef(area) {
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
    for (let i = cands.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
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
      if (e.key === STORE_KEY) {
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
  };
})(window);
