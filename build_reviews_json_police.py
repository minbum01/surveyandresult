"""
police_reviews.db → police_reviews_data.json (프론트용 export)
- build_reviews_json.py 의 경찰판
"""
import sqlite3, json, re, os

conn = sqlite3.connect('police_reviews.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

tags_by_id = {r['id']: r['name'] for r in cur.execute('SELECT id, name FROM tags').fetchall()}

pn_tags = {}
for row in cur.execute('SELECT passnote_id, tag_id FROM passnote_tags').fetchall():
    name = tags_by_id.get(row['tag_id'])
    if name:
        pn_tags.setdefault(row['passnote_id'], []).append(name)

pn_inst = {}
for row in cur.execute('SELECT passnote_id, subject, name FROM instructors').fetchall():
    pn_inst.setdefault(row['passnote_id'], []).append([row['subject'], row['name']])

pn_book = {}
for row in cur.execute('SELECT passnote_id, subject, name FROM textbooks').fetchall():
    pn_book.setdefault(row['passnote_id'], []).append([row['subject'], row['name']])

GREET_PREFIX = ('안녕', '반갑', '저는', '제 이름', '인사', '드립니다', '드려요', '소개')
SKIP_KEYWORDS = ('수기 작성', '글입', '이번에', '인삿', '말씀드', '부탁드')
STRATEGY_KW = [
    '기출', '루틴', '공부', '시간', '강사', '인강', '회독', '단권화', '암기',
    '집중', '하루', '매일', '주말', '평일', '아침', '저녁', '새벽',
    '계획', '오답', '문제', '복습', '강의', '교재', '노트', '꾸준', '습관',
    '핵심', '필기', '플래너', '개념', '점수', '실수', '약점', '꼼꼼',
    '체력', '헌법', '형사법', '경찰학', '영어', '한국사', '면접',
]
FIRST_PERSON = ('저는', '제가', '저한테', '저의', '제 경우', '제 생각')

ENCOURAGE_KW = [
    '처음에', '처음엔', '처음은', '막막', '걱정', '두려', '불안', '고민',
    '그래도', '하지만', '결국', '해냈', '할 수 있', '됐', '됩니다', '되었',
    '버텼', '버틸', '꾸준', '놓지', '포기하지', '포기 안', '다잡',
    '마음', '다짐', '결심', '용기', '희망', '확신', '다행', '감사',
    '한 발', '하루하루', '꾸역꾸역', '조금씩', '천천히', '버티',
    '저도', '저는', '제가', '돌아보면', '돌이켜', '시작'
]

def split_sentences(text):
    if not text:
        return []
    sents = re.split(r'(?<=[.!?。])\s+|\n+', text)
    return [s.strip() for s in sents if s and s.strip()]

def score_sentence(s):
    n = len(s)
    if n < 55 or n > 220:
        return -1
    head = s[:30]
    if any(g in head for g in GREET_PREFIX):
        return -1
    if any(k in s for k in SKIP_KEYWORDS):
        return -1
    score = 0
    for kw in STRATEGY_KW:
        if kw in s:
            score += 1
    if any(p in s for p in FIRST_PERSON):
        score += 2
    if '"' in s or '!' in s:
        score += 1
    return score

def extract_quotes(content, n=2):
    sents = split_sentences(content)
    scored = [(score_sentence(s), s) for s in sents if score_sentence(s) > 0]
    scored.sort(key=lambda x: -x[0])
    out = []
    for _, s in scored[:n]:
        if not s.endswith(('.', '!', '?', '다', '요', '죠', '음')):
            s += '.'
        out.append(s)
    return out

def extract_passage(content, length_min=150, length_max=420):
    if not content:
        return ''
    sents = split_sentences(content)
    valid = [s for s in sents
             if len(s) >= 20
             and not any(g in s[:20] for g in GREET_PREFIX)
             and not any(k in s for k in SKIP_KEYWORDS)]
    if not valid:
        return ''
    sent_scores = [sum(1 for kw in ENCOURAGE_KW if kw in s) for s in valid]
    best = (-1, 0, 2)
    for start in range(len(valid)):
        for length in (2, 3, 4, 5):
            end = start + length
            if end > len(valid):
                break
            window_text = ' '.join(valid[start:end])
            if not (length_min <= len(window_text) <= length_max):
                continue
            score_sum = sum(sent_scores[start:end])
            position_bonus = max(0, (len(valid) // 2) - start) * 0.1
            total = score_sum + position_bonus
            if total > best[0]:
                best = (total, start, length)
    if best[0] >= 0:
        s, e = best[1], best[1] + best[2]
        return ' '.join(valid[s:e])
    for start in range(len(valid)):
        for length in (3, 4, 2, 5):
            end = start + length
            if end > len(valid):
                break
            window_text = ' '.join(valid[start:end])
            if length_min <= len(window_text) <= length_max:
                return window_text
    return ''

passnotes = []
for r in cur.execute('SELECT * FROM passnotes').fetchall():
    pid = r['id']
    passnotes.append({
        'id': pid,
        'title': r['title'],
        'url': r['url'],
        'exam': r['exam_type'] or '',
        'grade': r['grade'] or '',
        'region': r['region'] or '',
        'job': (r['job_series'] or '').strip(),
        'period': r['study_period'] or '',
        'year': r['pass_year'] or '',
        'category': r['category'] or '',
        'tags': pn_tags.get(pid, []),
        'inst': pn_inst.get(pid, [])[:10],
        'book': pn_book.get(pid, [])[:10],
        'quotes': extract_quotes(r['content']),
        'passage': extract_passage(r['content']),
    })

tag_counts = {r['name']: r['count'] for r in cur.execute('SELECT name, count FROM tags').fetchall()}

out = {
    'passnotes': passnotes,
    'tagCounts': tag_counts,
    'totalCount': len(passnotes),
}

OUTPUT = 'police_reviews_data.json'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

n_with_quotes  = sum(1 for p in passnotes if p['quotes'])
n_with_passage = sum(1 for p in passnotes if p['passage'])
n_with_tags    = sum(1 for p in passnotes if p['tags'])
print(f'합격수기:            {len(passnotes)}건')
print(f'인용구(short) 성공:  {n_with_quotes}건')
print(f'passage(3~4줄) 성공: {n_with_passage}건')
print(f'태그 보유:           {n_with_tags}건')
print(f'총 태그 종류:        {len(tag_counts)}종')
print(f'파일 크기:           {os.path.getsize(OUTPUT)/1024/1024:.2f} MB  →  {OUTPUT}')
