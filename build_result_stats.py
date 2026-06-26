# -*- coding: utf-8 -*-
"""
build_result_stats.py — 결과페이지 2p '합격자가 남긴 전략' 집계.

입력: live/reviews_data.json (passnotes[].passage/quotes/tags/job/title/inst)
출력: live/result_stats.json
  { "<직렬>": {
       "count":  N,
       "strategy": [ {text, source, cat}, ... ],   # 다시 시작한다면 꼭 할 것 (긍정 전략, 숫자 미노출)
       "courses":  [ {subject, instructor}, ... ],  # 나와 비슷한 합격자들이 들은 강의 (구매유도)
       "passCopy": "..." }, ...,
    "_default": {...} }   # 희소 직렬 폴백

⚠ 직렬 귀속은 result.html의 jobMatch 와 동일:
   q3 확장태그가 tags에 있거나 job이 확장태그면 귀속, 단 '행정직'은 tags에 '교육직'이면 제외.
"""
import json, re, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, 'live', 'reviews_data.json')
OUT  = os.path.join(HERE, 'live', 'result_stats.json')

JOB_EXP = {
    '행정직': ['우정행정직', '행정직'],
    '세무직': ['관세직', '세무직'],
    '공안직': ['검찰직', '교정직', '보호직', '철도경찰직', '출입국관리직'],
    '교육직': ['교육직'],
    '기술직': ['건축직','공업직','군수직','기계일반','기계직','기술직','농업직','방송통신직','시설직','임업직','전기직','전산직','토목직','환경직'],
    '간호보건직': ['간호보건직', '보건직'],
    '사회복지직': ['사회복지직'],
    '기타직렬': ['감사직','계리직','고용노동직','국회직8급','국회직9급','기상직','기체직','도시계획직','방재안전직','법원직9급','소수직렬','식품위생직','외무영사직','운전직','조경직','지적직','직업상담직','차량직','통계직','회계직'],
}

def job_match(p, q3):
    ts = set(p.get('tags') or [])
    if q3 == '행정직' and '교육직' in ts:
        return False
    exp = JOB_EXP[q3]
    return bool(ts & set(exp)) or p.get('job') in exp

def split_sentences(text):
    if not text:
        return []
    parts = re.split(r'(?<=[다요음])\.\s*|[.!?]\s+|\n+', text)
    return [s.strip() for s in parts if len(s.strip()) >= 14]

# ── 전략(no.12 긍정) ─────────────────────────────────────────
ADVICE = ['추천', '하시길', '하시는 걸', '하는 게 좋', '하는 것이 좋', '하시면',
          '중요하', '도움이 되', '효과적', '꼭 ', '반드시', '매일']
CAT = {
    '공부전략': ['회독', '기출', '인강', '강의', '암기', '복습', '단권화', '정리', '오답', '문제풀이', '개념'],
    '수험전략': ['모의고사', '시간 배분', '시간배분', '마킹', '실전', '동형', '하프', '시험장', '컨디션'],
    '생활습관': ['루틴', '기상', '운동', '수면', '식사', '스터디', '멘탈', '체력', '산책', '휴식', '규칙적'],
}
# 형식적 마무리/감사 인사 컷
STRAT_DROP = ['감사드', '감사합', '되었으면 좋겠', '화이팅', '응원합', '읽어주셔', '봐주셔']

def cat_of(s):
    for c, kws in CAT.items():
        if any(k in s for k in kws):
            return c
    return None

def pick_strategy(reviews):
    seen = set()
    scored = []
    for p in reviews:
        for sent in split_sentences(p.get('passage') or ''):
            if not (22 <= len(sent) <= 82):
                continue
            if any(d in sent for d in STRAT_DROP):
                continue
            if not any(a in sent for a in ADVICE):
                continue
            cat = cat_of(sent)
            if not cat:
                continue
            key = sent[:18]
            if key in seen:
                continue
            seen.add(key)
            score = 0
            if '도움이 되' in sent: score += 2
            if '중요하' in sent: score += 2
            if '추천' in sent: score += 1
            if 30 <= len(sent) <= 70: score += 2
            scored.append((score, cat, sent, (p.get('title') or '').strip()))
    scored.sort(key=lambda x: -x[0])
    # 카테고리 다양성: 공부/수험/생활 각 1개 우선 확보 후 점수순 보충
    out, used_cat = [], set()
    for sc, cat, sent, title in scored:
        if cat in used_cat:
            continue
        out.append({'text': sent, 'source': title, 'cat': cat})
        used_cat.add(cat)
        if len(out) >= 3:
            break
    if len(out) < 3:
        for sc, cat, sent, title in scored:
            if any(o['text'] == sent for o in out):
                continue
            out.append({'text': sent, 'source': title, 'cat': cat})
            if len(out) >= 3:
                break
    return out

# ── 강의(no.14 대체, 구매유도) ───────────────────────────────
# 공통 교양과목은 모든 직렬에 떠서 직렬 특색이 약함 → 전공/전문과목을 우선 노출
COMMON_SUBJ = {'국어', '영어', '한국사'}

# ▼▼ 검수 후 제외할 항목 — live/result_exclude.json 에서 로드 (강사교재_검수목록.md 기반) ▼▼
# 추가로 빼고 싶으면 아래 set에 직접 넣어도 되고, result_exclude.json 을 편집해도 됨.
EXCLUDE_INSTRUCTORS = set()   # 예: {'면접 빼려면'} — 수동 추가분
EXCLUDE_SUBJECTS    = set()   # 예: {'면접'} — 통째로 빼는 과목
ALIAS = {}                    # OCR 변형 → 실제 강사명 (황지선→황진선 등)
_EXC = os.path.join(HERE, 'live', 'result_exclude.json')
if os.path.exists(_EXC):
    _e = json.load(open(_EXC, encoding='utf-8'))
    EXCLUDE_INSTRUCTORS |= set(_e.get('instructors') or [])
    EXCLUDE_SUBJECTS    |= set(_e.get('subjects') or [])
    ALIAS = dict(_e.get('aliases') or {})
# ▲▲ 재빌드 시 자동 반영 ▲▲

def canon(name):
    return ALIAS.get(name, name)

SUBJ_CANON = {}               # 과목 변형 → 대표과목 (회계/회계원리→회계학 등)
_SC = os.path.join(HERE, 'live', 'subject_canon.json')
if os.path.exists(_SC):
    SUBJ_CANON = dict(json.load(open(_SC, encoding='utf-8')))

def canon_subj(s):
    return SUBJ_CANON.get(s, s)

MIN_SUBJECT_MENTIONS = 5          # OCR 조각·희소 과목 컷
BAD_SUBJECTS = {'미상', '비공개', '기타', '공통', '선택', '없음', '-', '미정'}

def subj_root(s):
    # 과목 유사중복 비교용 어근: '개론/총론/원론/원리/각론' 제거 후 끝의 '학' 제거
    for tok in ('개론', '총론', '원론', '원리', '각론'):
        s = s.replace(tok, '')
    if len(s) > 2 and s.endswith('학'):
        s = s[:-1]
    return s

def pick_courses(reviews, limit=5):
    subj_inst = collections.defaultdict(collections.Counter)
    for p in reviews:
        for pair in (p.get('inst') or []):
            if len(pair) == 2 and pair[0] and pair[1]:
                subj = canon_subj(pair[0])     # 과목 변형을 대표과목으로 병합
                inst = canon(pair[1])          # OCR 변형을 실제 이름으로 병합
                if subj in EXCLUDE_SUBJECTS or inst in EXCLUDE_INSTRUCTORS:
                    continue
                subj_inst[subj][inst] += 1
    subj_total = collections.Counter({s: sum(c.values()) for s, c in subj_inst.items()})
    # 전문과목(비공통) 먼저, 그다음 공통과목 — 둘 다 등장 많은 순
    spec = [s for s, _ in subj_total.most_common() if s not in COMMON_SUBJ]
    comm = [s for s, _ in subj_total.most_common() if s in COMMON_SUBJ]
    ordered = spec + comm
    out, accepted = [], []
    for s in ordered:
        if not subj_inst[s] or s in BAD_SUBJECTS or subj_total[s] < MIN_SUBJECT_MENTIONS:
            continue
        inst, icnt = subj_inst[s].most_common(1)[0]
        if icnt < 2:                  # 1회만 등장한 강사명(OCR 조각 가능) 컷
            continue
        sr = subj_root(s)
        # 유사중복 과목 병합: 어근이 같거나 포함관계면 스킵 (강사 무관, 같은 과목 1회만)
        if any(sr == ar or s in a or a in s for a, ai, ar in accepted):
            continue
        out.append({'subject': s, 'instructor': inst})
        accepted.append((s, inst, sr))
        if len(out) >= limit:
            break
    return out

PASS_COPY = '나와 같은 직렬 합격자들이 가장 많이 들은 강의예요. 해커스공무원 패스로 한 번에 들을 수 있어요.'

def build(reviews):
    return {
        'count': len(reviews),
        'strategy': pick_strategy(reviews),
        'courses': pick_courses(reviews),
        'passCopy': PASS_COPY,
    }

def main():
    data = json.load(open(SRC, encoding='utf-8'))
    ps = data['passnotes']
    result = {q3: build([p for p in ps if job_match(p, q3)]) for q3 in JOB_EXP}
    result['_default'] = build(ps)
    json.dump(result, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for q3, v in result.items():
        print(f"{q3}: n={v['count']} strat={len(v['strategy'])} courses={[c['subject']+'/'+c['instructor'] for c in v['courses']]}")

if __name__ == '__main__':
    main()
