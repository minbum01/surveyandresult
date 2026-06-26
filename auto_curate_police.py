"""
경찰 자동 큐레이션 선정기 — 조합마다 상위 N개를 점수로 추려 '자동 핀' JSON 생성.
- 사람이 빈 화면에서 찾는 대신, police_admin.html 에 '핀 가져오기' 한 뒤 나쁜 것만 빼면 됨(검수).
- 경찰 데이터는 상황(Q1) 태그가 거의 없어 **전형(Q3)×성별(Q4)** 축으로 선정한다.
- 칸(영역) 성격별 점수:
    no.01 대표후기(히어로)  = 감정/격려형
    no.06 같은 출발점        = 실전형(공부법/순서/체력/순공)
- 매칭 규칙(TAG_EXPANSION/has_expanded/job_match)은 police_result.html 388행 권위본과 동일.
출력: police_auto_curation.json  (admin_curation_v2_경찰 v3 구조, areas 포함)
사용: python auto_curate_police.py            (전체 생성 + 샘플 출력)
      python auto_curate_police.py --sample   (샘플만, 파일 안 씀)
"""
import json, sys

REVIEWS = "police_reviews_data.json"
OUT = "police_auto_curation.json"
TOPN = 15

# ── 경찰 TAG_EXPANSION (police_result.html 388행 권위본) ──
TAG_EXPANSION = {
  # 상황 (Q1)
  '전업수험생': ['전업수험생'], '직장병행': ['직장병행','직장휴직'],
  '재학수험생': ['재학수험생','학업병행','통학병행','휴학','복학수험생'],
  '육아병행': ['육아병행'], '퇴직수험생': ['퇴직','퇴사후도전','현직퇴사후재도전'],
  '아르바이트병행': ['아르바이트','아르바이트병행'],
  # 기간 (Q2)
  '6개월미만': ['수험기간6개월미만'], '6개월~1년': ['수험기간6개월~1년'],
  '1년~2년': ['수험기간1년이상'], '2년이상': ['수험기간2년이상'],
  # 전형 (Q3)
  '일반공채': ['일반공채','일반공채(남)','일반공채(여)','공채'],
  '경찰간부': ['경찰간부','간부후보','경행','경행경채'],
  '101경비단': ['101경비단'],
  '경채': ['경채','해양경찰','해경'],
  # 성별 (Q4)
  '남성': ['남성'], '여성': ['여성'],
  # 시간 (Q5)
  '5시간미만': ['6시간공부','효율공부'], '5~8시간': ['8시간공부','순공시간확보'],
  '8~10시간': ['10시간공부','순공시간확보'], '10시간이상': ['10시간이상공부','12시간공부','13시간공부'],
  # 방식 (Q7)
  '인강병행': ['인강수강','풀커리수강','강사고정'], '기출반복': ['기출중시','기출분석','기출활용'],
  '회독반복': ['반복회독','다회독','급제약점중심회독'], '독학위주': ['단권화','OX학습','기출중시'],
  '스터디병행': ['스터디활용','면접스터디'],
  # 걱정 (Q8)
  '체력시험': ['체력준비','체력학원','체력약점','체력역전','체력중요인식'],
  '영어약자': ['이해+암기병행','자투리시간활용'], '형사법': ['최신판례중시','형사법약점','OX학습'],
  '면접': ['면접준비','면접스터디','면접학원','면접중요인식'],
  '멘탈관리': ['멘탈관리','불안극복','루틴유지'], '슬럼프극복': ['슬럼프극복','동기부여','꾸준함'],
}

# 선정 축
Q3 = ['일반공채','경찰간부','101경비단','경채']   # 전형
Q4 = ['남성','여성']                              # 성별

def has_expanded(ts, tag):
    if not tag: return True
    for t in TAG_EXPANSION.get(tag, [tag]):
        if t in ts: return True
    return False

def job_match(p, q3):
    """전형 매칭 — 태그 확장 + job 필드 (police_result.html jobMatch 동일)"""
    if not q3: return True
    ts = set(p.get('tags') or [])
    for t in TAG_EXPANSION.get(q3, [q3]):
        if t in ts or p.get('job') == t: return True
    return False

# ── 점수 기준 ──
KW_EMO = ['처음에','막막','걱정','불안','그래도','결국','해냈','됐','됩니다','버텼','꾸준',
          '놓지','포기하지','다잡','마음','다짐','용기','희망','확신','다행','감사','조금씩','버티','버텨','한 발']
# 경찰 실전형: 공부법 + 체력/순공/판례 등 경찰 특화어 포함
KW_METHOD = ['공부법','루틴','회독','기출','단권화','계획','시간표','순서','전략','방법','이렇게',
             '인강','강의','복습','오답','정리','암기','문제풀이','진도','커리','스케줄','하루에','시간을',
             '체력','순공','판례','형사법','경찰학','단어','면접']

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

# ── 영역 정의 (전형×성별 축) ──
AREAS = {
  'no.01': {'keys': ['Q3','Q4'], 'score': score_emo,    'need': 'passage'},
  'no.06': {'keys': ['Q3','Q4'], 'score': score_method, 'need': 'passage'},
}

# 결과페이지(curation_sync.js)가 읽는 area matchKeys — 덮어쓰기 import 시에도 정합 유지
AREAS_META = {
  'no.01': {'name': '같은 길을 걸은 분의 기록',   'matchKeys': ['Q3','Q4']},
  'no.02': {'name': '먼저 걸은 사람의 한마디',     'matchKeys': ['Q5','Q7','Q8']},
  'no.06': {'name': '같은 출발점에서 시작한 분들', 'matchKeys': ['Q3','Q4']},
  'no.07': {'name': '흔들렸을 때 다잡은 한 마디',  'matchKeys': ['Q8']},
  'no.08': {'name': '첫 한 달 풍경',              'matchKeys': ['Q3']},
  'no.09': {'name': '포기 직전, 다시 책상 앞',     'matchKeys': ['Q3']},
  'no.10': {'name': '꾸준함을 말하는 한 줄',       'matchKeys': ['Q1','Q2','Q3','Q4','Q5','Q6','Q7','Q8']},
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
    store = {'version': 3, 'areas': dict(AREAS_META), 'pins': {},
             'excludesCombo': {}, 'excludesGlobal': [], 'reviewed': {}, '_auto': True}
    combos = {
      'no.01': [{'Q3': b, 'Q4': c} for b in Q3 for c in Q4],
      'no.06': [{'Q3': b, 'Q4': c} for b in Q3 for c in Q4],
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
    print("\n===== 샘플: 일반공채 × 남성 (no.01 감정형) =====")
    for p in topn(reviews, 'no.01', {'Q3':'일반공채','Q4':'남성'}, 8):
        print(f"  [{score_emo(p):2}] {str(p.get('title',''))[:42]}")
    print("\n===== 샘플: 일반공채 × 남성 (no.06 실전형) =====")
    for p in topn(reviews, 'no.06', {'Q3':'일반공채','Q4':'남성'}, 8):
        t = (p.get('passage') or '')[:50]
        print(f"  [{score_method(p):2}] {str(p.get('title',''))[:26]} | {t}")

def main():
    d = json.load(open(REVIEWS, encoding='utf-8'))
    reviews = d.get('passnotes') if isinstance(d, dict) else d
    print(f"경찰 후기 {len(reviews)}건 로드")
    sample(reviews)
    if '--sample' not in sys.argv:
        store = build(reviews)
        total = sum(len(v) for v in store['pins'].values())
        payload = {  # police_admin '📤 핀 가져오기'가 받는 형식
            'version': 2, 'exportedAt': '', 'auto': True,
            'totalPins': total, 'store': store,
        }
        json.dump(payload, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f"\n저장: {OUT} (핀 {total}건)")
        print("→ police_admin.html '핀 가져오기'로 올리고(처음엔 '덮어쓰기') 조합별로 검수")

if __name__ == '__main__':
    main()
