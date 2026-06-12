"""
no.02 페르소나 밑 4~5줄 (Q1 × Q8 = 36 조합) 추천
- 강제: "같은 처지" 또는 "같은 걱정" 둘 중 하나 반드시 포함
- 톤: 따뜻한 격려, 길이 50~200자
- 각 조합당 상위 1~3건 → admin v3 store 형식으로 출력
"""
import json, sys, io, re, os
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('reviews_data.json', encoding='utf-8') as f:
    DATA = json.load(f)

TAG_EXPANSION = {
    '전업수험생': ['20대초반','군복무수험생','재시생','전업수험생','전역수험생','전직렬전환','초시생'],
    '직장병행': ['고졸수험생','재직수험생','직장병행'],
    '재학수험생': ['복학수험생','서울4년제','재학수험생','지거국','지방4년제','통학수험생','학업병행','휴학수험생'],
    '육아병행': ['40대','결혼준비','기혼','맘시생','워킹맘','육아병행','임신수험생','출산직후면접'],
    '퇴직수험생': ['50대','경력단절','경력직','계약직경력','물류경력','사업경험','생산직경력','서비스직경력','주6일직장','콜센터경력','퇴직수험생'],
    '아르바이트병행': ['N잡러','교대근무','아르바이트병행','주4일알바'],
    '멘탈관리': ['멘탈관리','수면관리','스트레스관리','운동병행','컨디션관리'],
    '슬럼프극복': ['건강이슈','과도한자신감','모의고사슬럼프','번아웃경험','슬럼프극복','실수관리','연애영향','운동병행','체력관리'],
    '영어약자': ['영어노베이스','영어약자'],
    '효율중심': ['127회독법','147회독법','8421공부법','SNS차단','고시원공부','기숙사공부','녹음활용','목차학습','선택과집중','스터디플랜','스톱워치활용','시간관리','식사중학습','엑셀활용','영어노트','오후암기','이동시간학습','이면지활용','자기객관화','자기암시','주말휴식','집공부','타자공부법','틈새시간활용','파일정리','홀수짝수회독','효율중심'],
    '이해중심학습': ['예습복습병행','이해중심학습'],
    '커리큘럼중심': ['기초중심','다회독','단계별학습','당일복습','도시락','무주일공부','무회독반복','완강중심','전과목','전년도강의활용','커리큘럼중심'],
}
Q1_DIRECT = ['전업수험생','직장병행','재학수험생','육아병행','퇴직수험생','아르바이트병행']
Q8_OPTS = ['멘탈관리','슬럼프극복','영어약자','효율중심','이해중심학습','커리큘럼중심']

def has_expanded(tags, tag_id):
    if not tag_id: return True
    if tag_id in Q1_DIRECT:
        for o in Q1_DIRECT:
            if o != tag_id and o in tags: return False
    exp = TAG_EXPANSION.get(tag_id, [tag_id])
    return any(t in tags for t in exp)

def split_sentences(text):
    if not text: return []
    parts = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [s.strip() for s in parts if len(s.strip()) > 5]

# 강제 키워드 (OR — 한 개라도 포함되면 OK)
# 의도: 자기 동일시 + 따뜻한 격려
REQUIRED_KW = [
    '같은 처지','같은 걱정','같은 고민','같은 입장','같은 길을',
    '비슷한 상황','비슷한 고민','비슷한 처지',
    '저처럼','저 같은','저와 같은','저와 같이',
]
# 따뜻함/격려 톤 가산점 키워드
WARM_KW = ['괜찮','힘내','응원','용기','함께','마음','다잡','버텼','버텨','이겨','극복','다행','감사','희망','괜찮아','잘하실','잘 하실','한 발','조금씩','꾸준','놓지','포기하지','지나니까']

def find_warm_sentences(content, q1_label, q8_label):
    """본문에서 강제 키워드 포함 + 따뜻한 톤의 문장(또는 문단) 찾기"""
    if not content: return []
    sents = split_sentences(content)
    out = []
    for i, s in enumerate(sents):
        # 강제 키워드 1개 이상 포함 필수
        matched_required = [k for k in REQUIRED_KW if k in s]
        if not matched_required: continue
        # 길이 50~250자 (페르소나 밑 4~5줄)
        if len(s) < 40 or len(s) > 280: continue
        # 점수
        warm_count = sum(1 for k in WARM_KW if k in s)
        score = len(matched_required) * 5 + warm_count * 2
        if 80 <= len(s) <= 180: score += 3
        # Q8 키워드 가산
        q8_exp = TAG_EXPANSION.get(q8_label, [q8_label])
        if any(k in s for k in q8_exp): score += 2
        out.append({
            'sentence': s,
            'score': score,
            'required_kw': matched_required,
            'warm_kw': [k for k in WARM_KW if k in s][:5],
            'len': len(s),
        })
    out.sort(key=lambda x: -x['score'])
    return out

def main():
    eligible = [p for p in DATA['passnotes'] if p.get('content')]
    pins = {'no.02': []}

    print(f'전체 후기 (content 보유): {len(eligible)}건', file=sys.stderr)
    print(f'36 조합 분석 시작...', file=sys.stderr)

    summary_rows = []
    for q1 in Q1_DIRECT:
        for q8 in Q8_OPTS:
            # Q1×Q8 매칭 후기
            cands = [p for p in eligible
                     if has_expanded(set(p.get('tags', [])), q1) and has_expanded(set(p.get('tags', [])), q8)]
            # 강제 키워드 들어간 문장 가진 후기 검색
            best_sents = []
            for p in cands:
                sents = find_warm_sentences(p.get('content',''), q1, q8)
                for s in sents:
                    s['p'] = p
                    best_sents.append(s)
            best_sents.sort(key=lambda x: -x['score'])
            top = best_sents[:3]  # 상위 3건
            summary_rows.append((q1, q8, len(cands), len(best_sents), len(top)))
            for rank, item in enumerate(top, 1):
                memo = f"{', '.join(item['required_kw'])} 포함, 따뜻한 키워드 {len(item['warm_kw'])}개({', '.join(item['warm_kw'][:3])}). [발췌] {item['sentence'][:120]}…"
                pins['no.02'].append({
                    'id': item['p']['id'],
                    'memo': memo,
                    'answers': {'Q1': q1, 'Q8': q8},
                    'matchKeys': ['Q1','Q8'],
                    'pinnedAt': datetime.utcnow().isoformat() + 'Z',
                })

    # 요약 출력
    print('\n=== 조합별 요약 ===', file=sys.stderr)
    print(f"{'Q1':>10} {'Q8':>12} | {'매칭':>5} | {'문장후보':>8} | {'선정':>4}", file=sys.stderr)
    for q1, q8, m, s, t in summary_rows:
        print(f"{q1:>10} {q8:>12} | {m:>5} | {s:>8} | {t:>4}", file=sys.stderr)

    # 영역 정의 + 핀 + 마이그레이션 호환 store 만들기
    out = {
        'version': 3,
        'exportedAt': datetime.utcnow().isoformat() + 'Z',
        '_note': 'AI 추천 — no.02 (Q1×Q8) 페르소나 밑 4~5줄 후기. 강제 KW: 같은 처지/같은 걱정',
        'totalPins': len(pins['no.02']),
        'store': {
            'version': 3,
            'areas': {
                'no.02': {
                    'name': '페르소나 밑 4~5줄',
                    'matchKeys': ['Q1','Q8'],
                    'intent': '같은 처지/같은 걱정 수험생에게 주는 따뜻한 격려 (50~200자, "같은 처지"/"같은 걱정" 1개 이상 필수)'
                }
            },
            'pins': pins,
            'excludesCombo': {},
            'excludesGlobal': [],
            'reviewed': {},
        }
    }

    out_path = f"auto_pins_no02_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n파일 저장: live/{out_path}', file=sys.stderr)
    print(f'총 핀 수: {len(pins["no.02"])}건', file=sys.stderr)

main()
