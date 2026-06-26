# -*- coding: utf-8 -*-
"""
build_curate_candidates.py — 조합별 상위 N 후보를 표시정보까지 담아 내보낸다.
  '확인 페이지'(curate_confirm.html)가 이 JSON을 읽어 사람이 ✅확정/❌제외 한다.

매칭/점수 로직은 auto_curate.py·result.html과 동일(태그일치 필터 + 품질점수 정렬).
출력: live/curate_candidates.json
  { exam, areas:{ "no.01":{keys, combos:[ {combo:{Q1,Q3,Q4}, items:[ {id,title,profile,quote,tags,score} x N ] } ] } } }
"""
import json, os, collections, re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, 'live', 'reviews_data.json')
OUT  = os.path.join(HERE, 'live', 'curate_candidates.json')
TOPN = 50   # 검수 풀 크기(자동제외 후 ~30개 핀) — 500명 다양화용

TAG_EXPANSION = {
  '전업수험생': ['20대초반','군복무수험생','재시생','전업수험생','전역수험생','전직렬전환','초시생'],
  '직장병행': ['고졸수험생','재직수험생','직장병행'],
  '재학수험생': ['복학수험생','서울4년제','재학수험생','지거국','지방4년제','통학수험생','학업병행','휴학수험생'],
  '육아병행': ['40대','결혼준비','기혼','맘시생','워킹맘','육아병행','임신수험생','출산직후면접'],
  '퇴직수험생': ['50대','경력단절','경력직','계약직경력','물류경력','사업경험','생산직경력','서비스직경력','주6일직장','콜센터경력','퇴직수험생'],
  '아르바이트병행': ['N잡러','교대근무','아르바이트병행','주4일알바'],
  '행정직': ['우정행정직','행정직','고용노동직'],
  '세무직': ['관세직','세무직'],
  '공안직': ['검찰직','교정직','보호직','철도경찰직','출입국관리직'],
  '교육직': ['교육직'],
  '기술직': ['건축직','공업직','군수직','기계일반','기계직','기술직','농업직','방송통신직','시설직','임업직','전기직','전산직','토목직','환경직'],
  '간호보건직': ['간호보건직','보건직'],
  '사회복지직': ['사회복지직'],
  '기타직렬': ['감사직','계리직','국회직8급','국회직9급','기상직','기체직','도시계획직','방재안전직','법원직9급','소수직렬','식품위생직','외무영사직','운전직','조경직','지적직','직업상담직','차량직','통계직','회계직'],
  '노베이스': ['노베이스','경찰직베이스','국어베이스','수능베이스','제2외국어','한국사베이스','한능검','한능검베이스','한자자격증'],
  '전공자': ['4년제','CPA베이스','IT경력','경영학전공','경제학전공','공학전공','관세사베이스','국시베이스','국어전공','기사자격증','무역학전공','법학전공','부전공','사범대','사회과학전공','사회복지전공','석사학위','세무사베이스','심리학전공','역사학전공','영어전공','임용베이스','전공위주','전공자','전기기사','전산회계베이스','통계학전공','행정법베이스','행정학전공','형사소송법베이스','회계세무전공'],
  '토익베이스': ['영어강사경력','영어베이스','지텔프','토익베이스','해외거주수험생'],
}
Q1 = ['전업수험생','직장병행','재학수험생','육아병행','퇴직수험생','아르바이트병행']
Q3 = ['행정직','세무직','공안직','교육직','기술직','간호보건직','사회복지직','기타직렬']
Q4 = ['노베이스','전공자','토익베이스']   # 수능베이스 병합됨(노베이스가 흡수)

SITU_LABEL = {'전업수험생':'전업','직장병행':'직장병행','재학수험생':'재학','육아병행':'육아','퇴직수험생':'퇴직','아르바이트병행':'알바'}
PERIODS = ['6개월미만','6개월~1년','1년~1년6개월','1년6개월~2년','2년~3년','3년이상']
PERIOD_SHORT = {'6개월미만':'6개월','6개월~1년':'1년이내','1년~1년6개월':'1년반','1년6개월~2년':'2년','2년~3년':'2년이상','3년이상':'3년이상'}

def has_expanded(ts, tag):
    if not tag: return True
    if tag in Q1:
        for o in Q1:
            if o != tag and o in ts: return False
    for t in TAG_EXPANSION.get(tag, [tag]):
        if t in ts: return True
    return False

def job_match(p, q3):
    if not q3: return True
    ts = set(p.get('tags') or [])
    if q3 == '행정직' and '교육직' in ts: return False
    for t in TAG_EXPANSION.get(q3, [q3]):
        if t in ts or p.get('job') == t: return True
    return False

KW_EMO = ['처음에','막막','걱정','불안','그래도','결국','해냈','됐','됩니다','버텼','꾸준','놓지','포기하지','다잡','마음','다짐','용기','희망','확신','다행','감사','조금씩','버티','버텨','한 발']
KW_METHOD = ['공부법','루틴','회독','기출','단권화','계획','시간표','순서','전략','방법','이렇게','베이스','수월','인강','강의','복습','오답','정리','암기','문제풀이','진도','커리','스케줄','하루에','시간을']

# 1년 이하 단기합격 우선 가점 (되도록 — 하드필터 아님)
SHORT_TAGS = {'6개월미만', '6개월~1년', '단기합격', '단기완성'}
def short_bonus(p):
    ts = set(p.get('tags') or [])
    return 5 if (ts & SHORT_TAGS) else 0

# ── 사용자 검수 패턴 자동화 (제외 기준) ──
#   1) 이중석 언급(텍스트) = 하드제외  2) 2023년 = 소프트제외  3) 2년이상 = 소프트제외
#   소프트제외는 조합에 그것밖에 없으면 유지(tier 폴백). 이중석은 그것밖에 없을 때만 최후로 유지.
LONG_TAGS = {'2년~3년', '3년이상'}
def reject_reasons(p):
    txt = (p.get('title') or '') + ' ' + (p.get('passage') or '') + ' ' + ' '.join(p.get('quotes') or [])
    r = []
    if '이중석' in txt: r.append('이중석')
    if '2023' in str(p.get('year') or ''): r.append('2023년')
    if set(p.get('tags') or []) & LONG_TAGS: r.append('2년이상')
    return r

def survives(reasons, tier):
    # tier 0: 결격 0  /  tier 1: 이중석만 아니면 OK  /  tier 2: 전부 OK
    if tier == 0: return not reasons
    if tier == 1: return '이중석' not in reasons
    return True

def score_emo(p):
    t = p.get('passage') or ''
    s = sum(1 for k in KW_EMO if k in t)
    if 180 <= len(t) <= 350: s += 3
    if p.get('quotes'): s += 1
    return s + short_bonus(p)

# no.06 테크니컬 후기 = 공부법 + '힘들었지만 극복' 서사 둘 다
KW_OVERCOME = ['힘들','어려','극복','슬럼프','약점','부족','보완','메우','버텼','버티','결국','그래서','덕분','포기하지','한계','고비']
def score_method(p):
    t = p.get('passage') or ''
    m = sum(1 for k in KW_METHOD if k in t)
    o = sum(1 for k in KW_OVERCOME if k in t)
    s = m + o
    if m >= 3 and o >= 1: s += 4        # 공부법+극복서사 둘 다 = 테크니컬
    if 150 <= len(t) <= 380: s += 2
    if p.get('quotes'): s += 1
    return s + short_bonus(p)

# ── 영역별 후보 선정 (result.html 로직 미러) ──
Q8 = ['멘탈관리', '슬럼프극복', '영어약자', '효율중심', '이해중심학습', '커리큘럼중심']
Q8_QUOTE_KW = {  # result.html Q8_QUOTE_KW와 동일
  '멘탈관리': ['멘탈','마음','심리','불안','걱정','평정','다잡','마인드','흔들리','안정','자신감','감정','컨디션'],
  '슬럼프극복': ['슬럼프','번아웃','무기력','포기','위기','극복','버티','버텼','버텨','견디','한계','다잡','다시','일어서'],
  '영어약자': ['영어','토익','지텔프','단어','문법','독해','어휘','영문','영어단어'],
  '효율중심': ['효율','시간','단기','짧','빠르','압축','집중','핵심','선택과집중','자투리'],
  '이해중심학습': ['이해','원리','개념','흐름','깊이','왜','본질','맥락','머리에','뜻'],
  '커리큘럼중심': ['커리큘럼','커리','학원','인강','단계','순서','계획','로드맵','일정','강의'],
}
FM_KW = ['첫 달','첫달','처음에는','처음 시작','처음으로','시작했을 때','초반에','시작 무렵','처음 한 달']
SLUMP_KW = ['포기하지','포기하려','버텼','버텨','버티','그래도','다잡','마음을 다','놓지','다시 책','다시 시작','한계']

def _topn(scored):
    return sorted(scored, key=lambda x: -x[0])[:TOPN]

# ── 답변 연결성: 후기 본문이 그 답변(상황/직렬/베이스)을 실제로 다루면 가점 ──
ANSWER_KW = {
  # Q1 상황
  '전업수험생': ['전업', '풀타임', '올인', '수험에만', '하루종일'],
  '직장병행': ['직장', '회사', '퇴근', '출근', '일하면서', '직장인', '재직', '병행', '점심시간', '주말'],
  '재학수험생': ['학교', '학업', '휴학', '복학', '대학', '수업', '학점', '재학', '학과', '졸업'],
  '육아병행': ['육아', '아이', '엄마', '아빠', '워킹맘', '어린이집', '아기', '자녀'],
  '퇴직수험생': ['퇴직', '퇴사', '그만두', '경력', '이직', '다니던', '늦은 나이', '30대', '40대'],
  '아르바이트병행': ['알바', '아르바이트', '파트타임', '부업'],
  # Q3 직렬 (과목/직무)
  '행정직': ['행정법', '행정학', '일반행정'],
  '세무직': ['세법', '회계', '세무', '관세'],
  '공안직': ['교정', '형사', '형법', '형소법', '보호직', '검찰', '출입국'],
  '교육직': ['교육학', '교육행정', '교행'],
  '기술직': ['전공', '기계', '전기', '토목', '전산', '건축', '화공', '임업', '농업'],
  '간호보건직': ['간호', '보건', '공중보건'],
  '사회복지직': ['사회복지', '복지'],
  # Q4 베이스
  '노베이스': ['노베이스', '처음', '기초부터', '막막', '문외한', '생초보', '아무것도', '베이스가 없'],
  '전공자': ['전공자', '전공이라', '관련 학과', '전공 살'],
  '토익베이스': ['토익', '영어는 자신', '영어 베이스'],
}
def conn_bonus(p, combo, keys):
    # 그 답변 키워드가 본문에 실제로 등장하면 +3 (연결성)
    t = (p.get('passage') or '') + ' ' + ' '.join(p.get('quotes') or [])
    b = 0
    for k in keys:
        kws = ANSWER_KW.get(combo.get(k), [])
        if kws and any(w in t for w in kws):
            b += 3
    return b

def pick_no01(reviews, combo):
    ks = ['Q1', 'Q3', 'Q4']
    return _topn([(score_emo(p) + conn_bonus(p, combo, ks), p) for p in cand(reviews, ks, combo)])

def pick_no06(reviews, combo):
    ks = ['Q1', 'Q4']
    return _topn([(score_method(p) + conn_bonus(p, combo, ks), p) for p in cand(reviews, ks, combo)])

def pick_no07(reviews, combo):   # Q8 다잡은 한마디 — 인용에 Q8 키워드
    kws = Q8_QUOTE_KW.get(combo['Q8'], [])
    out = []
    for p in reviews:
        if not has_expanded(set(p.get('tags') or []), combo['Q8']):
            continue
        best = 0
        for q in (p.get('quotes') or []):
            hits = sum(1 for k in kws if k in q)
            if hits:
                best = max(best, hits * 2 + (3 if 50 <= len(q) <= 130 else 0))
        if best:
            out.append((best + short_bonus(p), p))
    return _topn(out)

def pick_no08(reviews, combo):   # Q1×Q3 첫 한 달 — passage에 첫달 문장
    out = []
    for p in cand(reviews, ['Q1', 'Q3'], combo):
        t = p.get('passage') or ''
        if not any(k in t for k in FM_KW):
            continue
        s = sum(1 for k in FM_KW if k in t) * 2 + (2 if 130 <= len(t) <= 380 else 0)
        out.append((s + short_bonus(p), p))
    return _topn(out)

def pick_no09(reviews, combo):   # Q1 포기 직전 — 인용에 슬럼프 키워드
    out = []
    for p in reviews:
        if not p.get('passage') or not has_expanded(set(p.get('tags') or []), combo['Q1']):
            continue
        best = 0
        for q in (p.get('quotes') or []):
            hits = sum(1 for k in SLUMP_KW if k in q)
            if hits:
                best = max(best, hits * 2 + (3 if 50 <= len(q) <= 130 else 0))
        if best:
            out.append((best + short_bonus(p), p))
    return _topn(out)

# no.10 내 직렬 팁 — 같은직렬 전공과목 + 공통(국·영) 공부 팁 문장
SUBJECT_BY_JOB = {
  '행정직': ['행정법','행정학'], '세무직': ['세법','회계학','회계','관세법'],
  '공안직': ['형법','형사소송법','형소법','교정학','형사정책'], '교육직': ['교육학'],
  '기술직': ['전공','기계','전기','토목','전산','건축','화학','물리','정보보호'],
  '간호보건직': ['간호','보건','공중보건'], '사회복지직': ['사회복지','사회복지학'], '기타직렬': [],
}
COMMON_SUBJ = ['국어','영어']
ADVICE10 = ['회독','기출','단권화','정리','이해','암기','강의','인강','복습','문제풀이','반복','개념','오답','공부법']
def _sents(t):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', t or '') if len(s.strip()) > 5]
def pick_no10(reviews, combo):   # Q3 직렬 — 같은직렬 전공/공통과목 팁
    subj = (SUBJECT_BY_JOB.get(combo['Q3']) or []) + COMMON_SUBJ
    out = []
    for p in cand(reviews, ['Q3'], combo):
        best = 0
        for s in _sents(p.get('passage') or ''):
            if not (22 <= len(s) <= 110): continue
            hit = any(k in s for k in subj)
            adv = sum(1 for k in ADVICE10 if k in s)
            if not adv: continue
            sc = adv + (3 if hit else 0)
            if sc > best: best = sc
        if best:
            out.append((best + short_bonus(p), p))
    return _topn(out)

# no.08(첫한달)·no.09(포기직전)는 결과페이지에서 삭제됨 → 후보생성 제외
AREAS = {
  'no.01': {'keys': ['Q1','Q3','Q4'], 'pick': pick_no01, 'label': '동일경로 대표후기(감정형)'},
  'no.06': {'keys': ['Q1','Q4'],      'pick': pick_no06, 'label': '같은 출발점(실전형)'},
  'no.07': {'keys': ['Q8'],           'pick': pick_no07, 'label': '내 약점은 이렇게 보완했다(Q8)'},
  'no.10': {'keys': ['Q3'],           'pick': pick_no10, 'label': '내 직렬 팁(전공·국영)'},
}
COMBOS = {
  'no.01': [{'Q1': a, 'Q3': b, 'Q4': c} for a in Q1 for b in Q3 for c in Q4],
  'no.06': [{'Q1': a, 'Q4': c} for a in Q1 for c in Q4],
  'no.07': [{'Q8': x} for x in Q8],
  'no.10': [{'Q3': b} for b in Q3],
}

def profile(p):
    ts = set(p.get('tags') or [])
    situ = next((SITU_LABEL[x] for x in Q1 if x in ts), '')
    per = next((PERIOD_SHORT[x] for x in PERIODS if x in ts), '')
    return ' · '.join(x for x in [situ, (per + ' 합격') if per else ''] if x)

def quotes_of(p):
    return [q for q in (p.get('quotes') or []) if q][:3]

def match_tags(p, combo):
    ts = set(p.get('tags') or [])
    out = []
    for k, v in combo.items():
        ok = job_match(p, v) if k == 'Q3' else has_expanded(ts, v)
        out.append({'tag': v, 'matched': ok})
    return out

def cand(reviews, keys, combo):
    out = []
    for p in reviews:
        if not p.get('passage'): continue
        ts = set(p.get('tags') or [])
        ok = all((job_match(p, combo[k]) if k == 'Q3' else has_expanded(ts, combo[k])) for k in keys)
        if ok: out.append(p)
    return out

def main():
    d = json.load(open(SRC, encoding='utf-8'))
    reviews = d.get('passnotes') if isinstance(d, dict) else d
    result = {'exam': '공무원', 'topN': TOPN, 'areas': {}}
    for area, cfg in AREAS.items():
        keys = cfg['keys']
        combos_out = []
        for combo in COMBOS[area]:
            cs = cfg['pick'](reviews, combo)
            if not cs: continue
            triples = [(s, p, reject_reasons(p)) for s, p in cs]
            # 폴백 tier 결정: 살아남는 게 생기는 첫 tier
            tier = next((t for t in (0, 1, 2) if any(survives(r, t) for _, _, r in triples)), 2)
            rows = []
            for s, p, reasons in triples:
                surv = survives(reasons, tier)
                rows.append({'id': p['id'], 'title': (p.get('title') or '').strip(),
                             'profile': profile(p), 'passage': (p.get('passage') or '').strip(),
                             'quotes': quotes_of(p), 'url': p.get('url') or '',
                             'year': p.get('year') or '', 'short': bool(set(p.get('tags') or []) & SHORT_TAGS),
                             'reject': '' if surv else '·'.join(reasons),   # ''=생존, 사유='제외'
                             'tags': match_tags(p, combo), 'score': s})
            # 생존(상단) → 제외(하단), 각 그룹 내 점수순
            rows.sort(key=lambda x: (x['reject'] != '', -x['score']))
            combos_out.append({'combo': combo, 'items': rows})
        result['areas'][area] = {'keys': keys, 'label': cfg['label'], 'combos': combos_out}
        print(f"{area}: 후보 있는 조합 {len(combos_out)}개 / 총 {len(COMBOS[area])}")
    json.dump(result, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print('저장:', OUT)

if __name__ == '__main__':
    main()
