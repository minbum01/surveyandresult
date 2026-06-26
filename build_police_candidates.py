# -*- coding: utf-8 -*-
"""
build_police_candidates.py — 경찰: 조합(전형×성별)별 상위 N 후보를 표시정보까지 담아 내보낸다.
  '확인 페이지'(police_curate_confirm.html)가 이 JSON을 읽어 사람이 ✅확정/❌제외 한다.

매칭/점수 로직은 auto_curate_police.py·police_result.html과 동일.
경찰은 상황(Q1) 태그가 거의 없어 **전형(Q3)×성별(Q4)** 축으로 선정.
출력: live/police_curate_candidates.json
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, 'police_reviews_data.json')
OUT  = os.path.join(HERE, 'live', 'police_curate_candidates.json')
TOPN = 20

# ── 경찰 TAG_EXPANSION (police_result.html 388행 권위본) ──
TAG_EXPANSION = {
  '전업수험생': ['전업수험생'], '직장병행': ['직장병행','직장휴직'],
  '재학수험생': ['재학수험생','학업병행','통학병행','휴학','복학수험생'],
  '육아병행': ['육아병행'], '퇴직수험생': ['퇴직','퇴사후도전','현직퇴사후재도전'],
  '아르바이트병행': ['아르바이트','아르바이트병행'],
  '6개월미만': ['수험기간6개월미만'], '6개월~1년': ['수험기간6개월~1년'],
  '1년~2년': ['수험기간1년이상'], '2년이상': ['수험기간2년이상'],
  '일반공채': ['일반공채','일반공채(남)','일반공채(여)','공채'],
  '경찰간부': ['경찰간부','간부후보','경행','경행경채'],
  '101경비단': ['101경비단'], '경채': ['경채','해양경찰','해경'],
  '남성': ['남성'], '여성': ['여성'],
  '5시간미만': ['6시간공부','효율공부'], '5~8시간': ['8시간공부','순공시간확보'],
  '8~10시간': ['10시간공부','순공시간확보'], '10시간이상': ['10시간이상공부','12시간공부','13시간공부'],
  '인강병행': ['인강수강','풀커리수강','강사고정'], '기출반복': ['기출중시','기출분석','기출활용'],
  '회독반복': ['반복회독','다회독','급제약점중심회독'], '독학위주': ['단권화','OX학습','기출중시'],
  '스터디병행': ['스터디활용','면접스터디'],
  '체력시험': ['체력준비','체력학원','체력약점','체력역전','체력중요인식'],
  '영어약자': ['이해+암기병행','자투리시간활용'], '형사법': ['최신판례중시','형사법약점','OX학습'],
  '면접': ['면접준비','면접스터디','면접학원','면접중요인식'],
  '멘탈관리': ['멘탈관리','불안극복','루틴유지'], '슬럼프극복': ['슬럼프극복','동기부여','꾸준함'],
}

Q3 = ['일반공채','경찰간부','101경비단','경채']   # 전형
Q4 = ['남성','여성']                              # 성별

JOB_LABEL = {'일반공채':'일반공채','경찰간부':'경찰간부','101경비단':'101경비단','경채':'경채'}
PERIODS = ['6개월미만','6개월~1년','1년~2년','2년이상']
PERIOD_SHORT = {'6개월미만':'6개월','6개월~1년':'1년이내','1년~2년':'1~2년','2년이상':'2년이상'}

def has_expanded(ts, tag):
    if not tag: return True
    for t in TAG_EXPANSION.get(tag, [tag]):
        if t in ts: return True
    return False

def job_match(p, q3):
    if not q3: return True
    ts = set(p.get('tags') or [])
    for t in TAG_EXPANSION.get(q3, [q3]):
        if t in ts or p.get('job') == t: return True
    return False

KW_EMO = ['처음에','막막','걱정','불안','그래도','결국','해냈','됐','됩니다','버텼','꾸준','놓지','포기하지','다잡','마음','다짐','용기','희망','확신','다행','감사','조금씩','버티','버텨','한 발']
KW_METHOD = ['공부법','루틴','회독','기출','단권화','계획','시간표','순서','전략','방법','이렇게','인강','강의','복습','오답','정리','암기','문제풀이','진도','커리','스케줄','하루에','시간을','체력','순공','판례','형사법','경찰학','단어','면접']

# 단기합격(경찰 기간 태그) 우선 가점 — 하드필터 아님
SHORT_TAGS = {'수험기간6개월미만', '수험기간6개월~1년'}
def short_bonus(p):
    ts = set(p.get('tags') or [])
    return 5 if (ts & SHORT_TAGS) else 0

def score_emo(p):
    t = p.get('passage') or ''
    s = sum(1 for k in KW_EMO if k in t)
    if 180 <= len(t) <= 350: s += 3
    if p.get('quotes'): s += 1
    return s + short_bonus(p)

KW_OVERCOME = ['힘들','어려','극복','슬럼프','약점','부족','보완','메우','버텼','버티','결국','그래서','덕분','포기하지','한계','고비','체력','역전']
def score_method(p):
    t = p.get('passage') or ''
    m = sum(1 for k in KW_METHOD if k in t)
    o = sum(1 for k in KW_OVERCOME if k in t)
    s = m + o
    if m >= 3 and o >= 1: s += 4        # 공부법+극복서사 둘 다 = 실전형
    if 150 <= len(t) <= 380: s += 2
    if p.get('quotes'): s += 1
    return s + short_bonus(p)

# ── 인용/문장 키워드 (police_result.html renderNoXX 와 동일) ──
Q8_QUOTE_KW = {
  '체력시험': ['체력','운동','달리기','윗몸','팔굽혀','악력','순발력','체력학원','체단','체력시험'],
  '영어약자': ['영어','단어','독해','문법','어휘','영문','구문','영단어'],
  '형사법':   ['형사법','형법','형소','형사소송','판례','법조문','두문자','암기'],
  '면접':     ['면접','인성검사','스피치','시사','자기소개','집단토론','면접스터디'],
  '멘탈관리': ['멘탈','마음','심리','불안','걱정','평정','다잡','마인드','흔들리','안정','자신감','감정','컨디션'],
  '슬럼프극복':['슬럼프','번아웃','무기력','포기','위기','극복','버티','버텼','버텨','견디','한계','다잡','다시','일어서'],
}
Q8_LIST = list(Q8_QUOTE_KW.keys())   # 걱정 6종
FM_KW = ['첫 달','첫달','처음에는','처음 시작','처음으로','시작했을 때','초반에','시작 무렵','처음 한 달']
SLUMP_KW = ['포기하지','포기하려','버텼','버텨','버티','그래도','다잡','마음을 다','놓지','다시 책','다시 시작','한계']

def quotes_of(p):
    return [q for q in (p.get('quotes') or []) if q][:3]

# ── 영역별 셀렉터: (qualifies, score, highlight_quotes) 반환 ──
def sel_passage(score_fn):
    """no.01/06: 태그·전형 매칭 풀에서 점수 (combo의 키로 필터는 main에서)"""
    def f(p, combo):
        return True, score_fn(p), quotes_of(p)   # 필터는 main의 cand_tag 가 수행
    return f

def sel_no07(p, combo):   # 걱정(Q8) — 해당 걱정 키워드 든 인용
    kw = Q8_QUOTE_KW.get(combo['Q8'], [])
    hit_q = [q for q in (p.get('quotes') or []) if q and any(k in q for k in kw)]
    if not hit_q: return False, 0, []
    best = max(sum(1 for k in kw if k in q) for q in hit_q)
    s = best * 2
    others = [q for q in (p.get('quotes') or []) if q and q not in hit_q]
    hl = (hit_q + others)[:3]
    if any(50 <= len(q) <= 130 for q in hit_q): s += 3
    return True, s, hl

def sel_no08(p, combo):   # 전형(Q3) — passage 에 첫달 키워드 (content 없어 passage)
    if not job_match(p, combo['Q3']): return False, 0, []
    t = p.get('passage') or ''
    hits = sum(1 for k in FM_KW if k in t)
    if hits == 0: return False, 0, []
    s = hits * 2 + (2 if 130 <= len(t) <= 350 else 0)
    if '첫 달' in t or '첫달' in t: s += 3
    return True, s, quotes_of(p)

def sel_no09(p, combo):   # 전형(Q3) — 슬럼프 키워드 인용
    if not job_match(p, combo['Q3']): return False, 0, []
    hit_q = [q for q in (p.get('quotes') or []) if q and any(k in q for k in SLUMP_KW)]
    if not hit_q: return False, 0, []
    best = max(sum(1 for k in SLUMP_KW if k in q) for q in hit_q)
    s = best * 2 + (3 if any(50 <= len(q) <= 130 for q in hit_q) else 0)
    others = [q for q in (p.get('quotes') or []) if q and q not in hit_q]
    return True, s, (hit_q + others)[:3]

# 영역 정의: keys(matchKeys)·combos·selector·label
# no.10 경찰 수험 팁 — 직렬/전형 무관, 경찰 과목·공부법 문장 (단일 조합)
SUBJ10 = ['형사법','형법','형소','경찰학','헌법','범죄학','영어','한국사']
ADVICE10 = ['회독','기출','단권화','정리','이해','암기','강의','인강','복습','문제풀이','반복','개념','오답','공부법','판례']
def sel_no10(p, combo):
    pg = p.get('passage') or ''
    best = 0; tips = []
    for s in re.split(r'(?<=[.!?])\s+|\n+', pg):
        s = s.strip()
        if not (22 <= len(s) <= 110): continue
        if not any(k in s for k in SUBJ10): continue
        adv = sum(1 for k in ADVICE10 if k in s)
        if not adv: continue
        sc = adv + 3
        tips.append((sc, s)); best = max(best, sc)
    if not best: return (False, 0, [])
    tips.sort(key=lambda x: -x[0])
    bonus = 5 if (set(p.get('tags') or []) & SHORT_TAGS) else 0
    return (True, best + bonus, [s for _, s in tips[:2]])

AREAS = {
  'no.01': {'keys': ['Q3','Q4'], 'combos': [{'Q3': b, 'Q4': c} for b in Q3 for c in Q4],
            'sel': sel_passage(score_emo),    'label': '동일전형 대표후기(감정형)'},
  'no.06': {'keys': ['Q3','Q4'], 'combos': [{'Q3': b, 'Q4': c} for b in Q3 for c in Q4],
            'sel': sel_passage(score_method), 'label': '같은 전형으로 붙은 분들(실전형)'},
  'no.07': {'keys': ['Q8'], 'combos': [{'Q8': q} for q in Q8_LIST],
            'sel': sel_no07, 'label': '그 고민, 이렇게 넘었습니다(걱정+포기서사)'},
  'no.10': {'keys': [], 'combos': [{}],
            'sel': sel_no10, 'label': '경찰 합격생이 말해주는 수험 팁'},
}

def profile(p):
    ts = set(p.get('tags') or [])
    job = next((JOB_LABEL[x] for x in Q3 if job_match(p, x)), '')
    gen = next((x for x in Q4 if x in ts), '')
    per = next((PERIOD_SHORT[x] for x in PERIODS if has_expanded(ts, x)), '')
    return ' · '.join(x for x in [job, gen, (per + ' 합격') if per else ''] if x)

def match_tags(p, combo):
    ts = set(p.get('tags') or [])
    out = []
    for k, v in combo.items():
        ok = job_match(p, v) if k == 'Q3' else has_expanded(ts, v)
        out.append({'tag': v, 'matched': ok})
    return out

# no.01/06 은 태그·전형으로 풀 제한 후 selector 점수. 그 외(no.07~09)는 selector 가 필터·점수 다 함.
def passage_pool(reviews, keys, combo):
    out = []
    for p in reviews:
        if not p.get('passage'): continue
        ts = set(p.get('tags') or [])
        if all((job_match(p, combo[k]) if k == 'Q3' else has_expanded(ts, combo[k])) for k in keys):
            out.append(p)
    return out

def main():
    d = json.load(open(SRC, encoding='utf-8'))
    reviews = d.get('passnotes') if isinstance(d, dict) else d
    result = {'exam': '경찰', 'topN': TOPN, 'areas': {}}
    for area, cfg in AREAS.items():
        keys, sel = cfg['keys'], cfg['sel']
        is_passage = area in ('no.01', 'no.06')
        combos_out = []
        for combo in cfg['combos']:
            scored = []
            pool = passage_pool(reviews, keys, combo) if is_passage else reviews
            for p in pool:
                ok, s, hl = sel(p, combo)
                if ok: scored.append((s, p, hl))
            scored.sort(key=lambda x: -x[0])
            top = scored[:TOPN]
            if not top: continue
            items = [{'id': p['id'], 'title': (p.get('title') or '').strip(),
                      'profile': profile(p), 'passage': (p.get('passage') or '').strip(),
                      'quotes': hl, 'url': p.get('url') or '',
                      'year': p.get('year') or '', 'short': bool(set(p.get('tags') or []) & SHORT_TAGS),
                      'tags': match_tags(p, combo), 'score': s} for s, p, hl in top]
            combos_out.append({'combo': combo, 'items': items})
        result['areas'][area] = {'keys': keys, 'label': cfg['label'], 'combos': combos_out}
        print(f"{area}: 후보 있는 조합 {len(combos_out)}개 / 총 {len(cfg['combos'])}")
    json.dump(result, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print('저장:', OUT)

if __name__ == '__main__':
    main()
