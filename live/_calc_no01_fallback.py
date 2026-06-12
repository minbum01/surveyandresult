"""
no.01 — Q1×Q3×Q4 모든 조합(6×8×4=192) 별 매칭 합격수기 수
"""
import json, sys, io
from itertools import product
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('reviews_data.json', encoding='utf-8') as f:
    data = json.load(f)
passnotes = data['passnotes']

TAG_EXPANSION = {
    '전업수험생': ['20대초반','군복무수험생','재시생','전업수험생','전역수험생','전직렬전환','초시생'],
    '직장병행': ['고졸수험생','재직수험생','직장병행'],
    '재학수험생': ['복학수험생','서울4년제','재학수험생','지거국','지방4년제','통학수험생','학업병행','휴학수험생'],
    '육아병행': ['40대','결혼준비','기혼','맘시생','워킹맘','육아병행','임신수험생','출산직후면접'],
    '퇴직수험생': ['50대','경력단절','경력직','계약직경력','물류경력','사업경험','생산직경력','서비스직경력','주6일직장','콜센터경력','퇴직수험생'],
    '아르바이트병행': ['N잡러','교대근무','아르바이트병행','주4일알바'],
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

Q1_OPTS = ['전업수험생','직장병행','재학수험생','육아병행','퇴직수험생','아르바이트병행']
Q3_OPTS = ['행정직','세무직','공안직','교육직','기술직','간호보건직','사회복지직','기타직렬']
Q4_OPTS = ['노베이스','수능베이스','전공자','토익베이스']

eligible = [p for p in passnotes if p.get('passage')]

# 후기별 매칭 가능 답변 사전 인덱싱
p_q1, p_q3, p_q4 = [], [], []
for p in eligible:
    ts = set(p.get('tags', []))
    job = p.get('job', '')
    p_q1.append({q for q in Q1_OPTS if any(t in ts for t in TAG_EXPANSION[q])})
    p_q3.append({q for q in Q3_OPTS if any(t in ts or job == t for t in TAG_EXPANSION[q])})
    p_q4.append({q for q in Q4_OPTS if any(t in ts for t in TAG_EXPANSION[q])})

# 192 조합 카운트
combo_counts = {}
for i in range(len(eligible)):
    for q1 in p_q1[i]:
        for q3 in p_q3[i]:
            for q4 in p_q4[i]:
                key = (q1, q3, q4)
                combo_counts[key] = combo_counts.get(key, 0) + 1

# ─── 통계 ───
all_combos = list(product(Q1_OPTS, Q3_OPTS, Q4_OPTS))
counts_only = [combo_counts.get(c, 0) for c in all_combos]
zero_count = sum(1 for c in counts_only if c == 0)
nonzero_count = 192 - zero_count

# ─── MD 작성 ───
out = []
out.append('# no.01 — Q1×Q3×Q4 192 조합별 매칭 합격수기 수')
out.append('')
out.append(f'- 후보 풀: passage 보유 합격수기 **{len(eligible)}건** (전체 {len(passnotes)}건 중)')
out.append(f'- 조합: Q1(6) × Q3(8) × Q4(4) = **192개**')
out.append(f'- 1건 이상 매칭: **{nonzero_count}개** ({nonzero_count/192*100:.1f}%)')
out.append(f'- 0건 (매칭 후기 없음): **{zero_count}개** ({zero_count/192*100:.1f}%)')
out.append(f'- 평균 매칭 수: **{sum(counts_only)/192:.1f}건**')
out.append(f'- 최대: **{max(counts_only)}건**, 최소: **{min(counts_only)}건**')
out.append('')

# Q1별 섹션 (Q3 행 × Q4 열 매트릭스)
for q1 in Q1_OPTS:
    out.append(f'## Q1 = {q1}')
    out.append('')
    header = '| Q3 \\ Q4 | ' + ' | '.join(Q4_OPTS) + ' |'
    sep = '|---|' + '---:|' * len(Q4_OPTS)
    out.append(header)
    out.append(sep)
    for q3 in Q3_OPTS:
        cells = []
        for q4 in Q4_OPTS:
            cnt = combo_counts.get((q1, q3, q4), 0)
            cells.append(f'**0**' if cnt == 0 else str(cnt))
        out.append(f'| {q3} | ' + ' | '.join(cells) + ' |')
    out.append('')

# 0건 조합 목록
out.append('## 0건 조합 목록')
out.append('')
zero_list = [c for c in all_combos if combo_counts.get(c, 0) == 0]
if not zero_list:
    out.append('없음 (모든 조합에 매칭 후기 1건 이상 존재)')
else:
    out.append(f'총 {len(zero_list)}개:')
    out.append('')
    for q1, q3, q4 in zero_list:
        out.append(f'- {q1} × {q3} × {q4}')
out.append('')

content = '\n'.join(out)
with open('no01_폴백_매칭수.md', 'w', encoding='utf-8') as f:
    f.write(content)
print(f'작성 완료: live/no01_폴백_매칭수.md ({len(content):,} bytes, {nonzero_count}/192 조합 매칭, {zero_count}개 0건)', file=sys.stderr)
