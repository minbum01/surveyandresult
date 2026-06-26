"""
자동 큐레이션 선정기 — 조합마다 상위 N개를 점수로 추려 '자동 핀' JSON 생성.
- 사람이 빈 화면에서 찾는 대신, 이걸 관리자 페이지에 '핀 가져오기' 한 뒤 나쁜 것만 빼면 됨(마지막 확인).
- 칸(영역) 성격별로 점수 기준이 다름:
    no.01 대표후기(히어로)  = 감정/격려형
    no.06 같은 출발점        = 실전형(공부법/순서/베이스)
- 매칭 규칙(TAG_EXPANSION/hasExpanded/jobMatch)은 result.html과 동일하게 복제.
출력: auto_curation.json  (admin_curation_v2 v3 구조)
사용: python auto_curate.py            (전체 생성 + 샘플 출력)
      python auto_curate.py --sample   (샘플만, 파일 안 씀)
"""
import json, sys, re

REVIEWS = "live/reviews_data.json"
OUT = "auto_curation.json"
TOPN = 15

TAG_EXPANSION = {
  '전업수험생': ['20대초반','군복무수험생','재시생','전업수험생','전역수험생','전직렬전환','초시생'],
  '직장병행': ['고졸수험생','재직수험생','직장병행'],
  '재학수험생': ['복학수험생','서울4년제','재학수험생','지거국','지방4년제','통학수험생','학업병행','휴학수험생'],
  '육아병행': ['40대','결혼준비','기혼','맘시생','워킹맘','육아병행','임신수험생','출산직후면접'],
  '퇴직수험생': ['50대','경력단절','경력직','계약직경력','물류경력','사업경험','생산직경력','서비스직경력','주6일직장','콜센터경력','퇴직수험생'],
  '아르바이트병행': ['N잡러','교대근무','아르바이트병행','주4일알바'],
  '국가직9급': ['1차2차병행','2관왕','7급병행','PSAT병행','국가직7급','국가직9급','국가직병행'],
  '지방직9급': ['2관왕','지방직7급','지방직8급','지방직9급','지방직병행'],
  '서울시9급': ['서울시8급','서울시9급'],
  '행정직': ['우정행정직','행정직'],
  '세무직': ['관세직','세무직'],
  '공안직': ['검찰직','교정직','보호직','철도경찰직','출입국관리직'],
  '교육직': ['교육직'],
  '기술직': ['건축직','공업직','군수직','기계일반','기계직','기술직','농업직','방송통신직','시설직','임업직','전기직','전산직','토목직','환경직'],
  '간호보건직': ['간호보건직','보건직'],
  '사회복지직': ['사회복지직'],
  '기타직렬': ['감사직','계리직','고용노동직','국회직8급','국회직9급','기상직','기체직','도시계획직','방재안전직','법원직9급','소수직렬','식품위생직','외무영사직','운전직','조경직','지적직','직업상담직','차량직','통계직','회계직'],
  '노베이스': ['노베이스'],
  '수능베이스': ['경찰직베이스','국어베이스','수능베이스','제2외국어','한국사베이스','한능검','한능검베이스','한자자격증'],
  '전공자': ['4년제','CPA베이스','IT경력','경영학전공','경제학전공','공학전공','관세사베이스','국시베이스','국어전공','기사자격증','무역학전공','법학전공','부전공','사범대','사회과학전공','사회복지전공','석사학위','세무사베이스','심리학전공','역사학전공','영어전공','임용베이스','재경관리사베이스','전공위주','전공자','전기기사','전산회계베이스','통계학전공','행정법베이스','행정학전공','형사소송법베이스','회계세무전공'],
  '토익베이스': ['영어강사경력','영어베이스','지텔프','토익베이스','해외거주수험생'],
}
Q1_DIRECT = ['전업수험생','직장병행','재학수험생','육아병행','퇴직수험생','아르바이트병행']
Q1 = Q1_DIRECT
Q3 = ['행정직','세무직','공안직','교육직','기술직','간호보건직','사회복지직','기타직렬']
Q4 = ['노베이스','수능베이스','전공자','토익베이스']

def has_expanded(ts, tag):
    if not tag: return True
    if tag in Q1_DIRECT:
        for o in Q1_DIRECT:
            if o != tag and o in ts: return False
    if tag == '행정직' and '교육직' in ts: return False
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

# ── 점수 기준 ──
KW_EMO = ['처음에','막막','걱정','불안','그래도','결국','해냈','됐','됩니다','버텼','꾸준','놓지','포기하지','다잡','마음','다짐','용기','희망','확신','다행','감사','조금씩','버티','버텨','한 발']
KW_METHOD = ['공부법','루틴','회독','기출','단권화','계획','시간표','순서','전략','방법','이렇게','베이스','수월','인강','강의','복습','오답','정리','암기','문제풀이','진도','커리','스케줄','하루에','시간을']

def score_emo(p):
    t = p.get('passage') or ''
    s = sum(1 for k in KW_EMO if k in t)
    if 180 <= len(t) <= 350: s += 3
    return s

def score_method(p):
    t = p.get('passage') or ''
    s = sum(1 for k in KW_METHOD if k in t)
    if 130 <= len(t) <= 350: s += 2
    return s

# ── 영역 정의 ──
AREAS = {
  'no.01': {'keys': ['Q1','Q3','Q4'], 'score': score_emo,    'need': 'passage'},
  'no.06': {'keys': ['Q1','Q4'],      'score': score_method, 'need': 'passage'},
}

def cand(reviews, area, combo):
    need = AREAS[area]['need']
    out = []
    for p in reviews:
        if need and not p.get(need): continue
        ts = set(p.get('tags') or [])
        ok = True
        for k in AREAS[area]['keys']:
            v = combo[k]
            if k == 'Q3':
                if not job_match(p, v): ok = False; break
            else:
                if not has_expanded(ts, v): ok = False; break
        if ok: out.append(p)
    return out

def topn(reviews, area, combo, n=TOPN):
    sc = AREAS[area]['score']
    scored = sorted(((sc(p), p) for p in cand(reviews, area, combo)), key=lambda x: -x[0])
    return [p for s, p in scored[:n]]

def build(reviews):
    store = {'version': 3, 'areas': {}, 'pins': {}, 'excludesCombo': {}, 'excludesGlobal': [], 'reviewed': {}, '_auto': True}
    combos = {
      'no.01': [{'Q1': a, 'Q3': b, 'Q4': c} for a in Q1 for b in Q3 for c in Q4],
      'no.06': [{'Q1': a, 'Q4': c} for a in Q1 for c in Q4],
    }
    for area, clist in combos.items():
        pins = []
        filled = 0
        for combo in clist:
            picks = topn(reviews, area, combo)
            if picks: filled += 1
            for p in picks:
                answers = {k: combo[k] for k in AREAS[area]['keys']}
                pins.append({'id': p['id'], 'memo': '', 'answers': answers,
                             'matchKeys': AREAS[area]['keys'], 'pinnedAt': ''})
        store['pins'][area] = pins
        print(f"{area}: 조합 {len(clist)}개 중 {filled}개 채움, 핀 {len(pins)}개")
    return store

def sample(reviews):
    print("\n===== 샘플: 직장 × 행정 × 노베이스 (no.01 감정형) =====")
    for p in topn(reviews, 'no.01', {'Q1':'직장병행','Q3':'행정직','Q4':'노베이스'}, 10):
        print(f"  [{score_emo(p):2}] {str(p.get('title',''))[:42]}")
    print("\n===== 샘플: 직장 × 노베이스 (no.06 실전형) =====")
    for p in topn(reviews, 'no.06', {'Q1':'직장병행','Q4':'노베이스'}, 10):
        t = (p.get('passage') or '')[:50]
        print(f"  [{score_method(p):2}] {str(p.get('title',''))[:30]} | {t}")

def main():
    d = json.load(open(REVIEWS, encoding='utf-8'))
    reviews = d.get('passnotes') if isinstance(d, dict) else d
    print(f"후기 {len(reviews)}건 로드")
    sample(reviews)
    if '--sample' not in sys.argv:
        store = build(reviews)
        total = sum(len(v) for v in store['pins'].values())
        payload = {  # 관리자 '핀 가져오기'가 받는 형식
            'version': 2, 'exportedAt': '', 'auto': True,
            'totalPins': total, 'store': store,
        }
        json.dump(payload, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f"\n저장: {OUT} (핀 {total}건)")
        print("→ 관리자 페이지 '📤 핀 가져오기'로 올리고(처음엔 '덮어쓰기') 조합별로 검수")

if __name__ == '__main__':
    main()
