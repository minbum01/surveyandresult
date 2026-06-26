# -*- coding: utf-8 -*-
"""
build_police_stats.py — 경찰 2면(강의 카드 + 전략) 데이터 집계.
  police_reviews_data.json → live/police_stats.json
  + 경찰_강사교재_검수목록.md (사람이 해커스 강사만 ✅ 남기는 검수 surface)

하드룰: 집계 숫자(N명)는 결과에 노출 X. police_stats.json 의 강사는 '순위'만, count 미포함.
강사 화이트리스트(해커스)는 사람 검수로 확정 — 아래 HACKERS_SEED 는 인수인계 §10-4 기준 시드.
"""
import json, os, collections, re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, 'police_reviews_data.json')
OUT  = os.path.join(HERE, 'live', 'police_stats.json')
MD   = os.path.join(HERE, '경찰_강사교재_검수목록.md')

# 과목 병합 (변형 → 대표)
SUBJ_CANON = {'형법':'형사법','형사소송법':'형사법','형소법':'형사법',
              '경찰행정법':'경찰학','경찰행정':'경찰학'}
# 강사 OCR/약칭 별칭 → 대표
ALIAS = {'갓대환':'김대환','김대한':'김대환','대환':'김대환',
         '박철환':'박철한','철한':'박철한','신동옥':'신동욱'}

# 경찰 노출 과목 (순서)
SUBJECTS = ['헌법','형사법','경찰학','범죄학','영어','한국사','체력','면접']

# ── 해커스 강사 시드 (인수인계 §10-4) — 사람 검수로 확정 ──
HACKERS_SEED = {
  '형사법': ['김대환'],
  '경찰학': ['조현'],
  '헌법':   ['신동욱'],
  '범죄학': ['노신'],
  '영어':   ['비비안'],
}
# 타사 — 절대 노출 금지 (인수인계 §10-4)
EXCLUDE = {'박철한','황남기','천재근'}

def canon_subj(s): return SUBJ_CANON.get(s, s)
def canon_name(n): return ALIAS.get(n, n)

def load():
    d = json.load(open(SRC, encoding='utf-8'))
    return d.get('passnotes') if isinstance(d, dict) else d

def aggregate(reviews):
    # (과목, 강사) → 언급 후기 수
    pair = collections.Counter()
    for p in reviews:
        seen = set()
        for it in (p.get('inst') or []):
            if not (isinstance(it, list) and len(it) >= 2): continue
            subj, name = canon_subj(it[0].strip()), canon_name(it[1].strip())
            if not subj or not name: continue
            key = (subj, name)
            if key in seen: continue   # 한 후기 내 중복 제거
            seen.add(key); pair[key] += 1
    return pair

# ── 전략 문장 풀 (passage 에서 '다시 준비한다면' 류) ──
STRAT_KW = ['다시 준비','다시 한다면','돌아간다면','꼭 하','추천','했더라면','후회','했어야','중요한 건','조언']
CAT_KW = {
  '공부법': ['회독','기출','단권화','암기','정리','복습','인강','커리'],
  '체력':   ['체력','운동','윗몸','악력','달리기'],
  '시간관리':['시간','계획','루틴','순공','하루','새벽'],
  '멘탈':   ['멘탈','마음','불안','슬럼프','꾸준','포기'],
}
def split_sents(t):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', t or '') if 20 <= len(s.strip()) <= 120]
def cat_of(s):
    for c, kws in CAT_KW.items():
        if any(k in s for k in kws): return c
    return '공부법'
def strategy_pool(reviews, n=40):
    out = []
    for p in reviews:
        for s in split_sents(p.get('passage') or ''):
            if any(k in s for k in STRAT_KW):
                out.append({'text': s, 'cat': cat_of(s), 'title': (p.get('title') or '').strip()})
    # 길이 다양성 위해 앞에서 n개
    return out[:n]

def courses(pair, hackers):
    """과목별 해커스 강사만, 언급순 (순위만 — count 미노출)"""
    out = {}
    for subj in SUBJECTS:
        wl = set(hackers.get(subj, []))
        ranked = [name for (s, name), c in pair.most_common() if s == subj and name in wl and name not in EXCLUDE]
        if ranked:
            out[subj] = ranked
    return out

def read_md_whitelist():
    """검수목록 MD가 있으면 사람이 마크한 ✅(해커스)/❌(타사) 를 읽어 반영.
       없으면 (None, None) → 시드 사용."""
    if not os.path.exists(MD): return None, None
    wl = collections.defaultdict(list); ex = set(EXCLUDE); subj = None
    for line in open(MD, encoding='utf-8'):
        m = re.match(r'^##\s+(.+)', line)
        if m: subj = m.group(1).strip(); continue
        m = re.match(r'^-\s*([✅❌❓])\s*([^\s<]+)', line)
        if m and subj:
            mark, name = m.group(1), m.group(2)
            if mark == '✅': wl[subj].append(name)
            elif mark == '❌': ex.add(name)
    return dict(wl), ex

def write_md(pair):
    """전 과목 강사 전체 목록 — 사람이 ❌타사/✅해커스 마크하는 검수 surface. 이미 있으면 보존."""
    if os.path.exists(MD):
        return  # 사람이 편집한 검수 결과 보존 (덮어쓰기 금지)
    lines = ['# 경찰 강사·교재 검수목록 (해커스만 남기기)', '',
             '> 원칙: **해커스 강사만 ✅, 타사 ❌.** 막대/카드엔 순위만(언급수 비노출).',
             '> 시드(해커스): 형사법 김대환·경찰학 조현·헌법 신동욱·범죄학 노신·영어 비비안.',
             '> ⛔ 타사 확정 제외: 박철한·황남기(헌법), 천재근(면접).', '',
             '아래에서 각 강사 앞에 `✅`(해커스) 또는 `❌`(타사) 표시 → build_police_stats.py 재실행 시 반영.', '']
    for subj in SUBJECTS:
        rows = [(name, c) for (s, name), c in pair.most_common() if s == subj]
        if not rows: continue
        lines.append(f'## {subj}')
        for name, c in rows[:12]:
            seed = '✅' if name in HACKERS_SEED.get(subj, []) else ('❌' if name in EXCLUDE else '❓')
            lines.append(f'- {seed} {name}  <!-- 언급 {c} -->')
        lines.append('')
    open(MD, 'w', encoding='utf-8').write('\n'.join(lines))

def main():
    reviews = load()
    pair = aggregate(reviews)
    write_md(pair)                                  # 최초 1회만 생성(있으면 보존)
    wl, ex = read_md_whitelist()                    # 사람 검수 결과 우선
    global EXCLUDE
    hackers = wl if wl else HACKERS_SEED
    if ex: EXCLUDE = ex
    src = '검수목록(사람)' if wl else '시드(인수인계 §10-4)'
    stats = {
        'exam': '경찰',
        'courses': courses(pair, hackers),               # 전체(해커스)
        'courses_경채': courses(pair, hackers),          # 경채도 동일 + 범죄학 강조(렌더에서)
        'strategy': strategy_pool(reviews),
        'note': '집계 숫자 비노출. 강사는 해커스 화이트리스트만.',
    }
    json.dump(stats, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print('저장:', OUT, '| 화이트리스트 출처:', src)
    print('  과목별 해커스 강사:', {k: v for k, v in stats['courses'].items()})
    print('  전략 문장 풀:', len(stats['strategy']))
    print('검수목록:', MD, '(사람이 ? 강사 O/X 확정 후 재실행하면 반영)')

if __name__ == '__main__':
    main()
