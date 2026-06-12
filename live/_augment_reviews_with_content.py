"""
reviews.db 의 content (전체 본문) 를 reviews_data.json 에 합쳐 넣음.
파일 크기: 4.3MB → 약 8MB
"""
import json, sqlite3, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, 'reviews.db')
JSON = 'reviews_data.json'

with open(JSON, encoding='utf-8') as f:
    data = json.load(f)

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute('SELECT id, content FROM passnotes')
contents = {row[0]: row[1] or '' for row in cur.fetchall()}
conn.close()

added = 0
for p in data['passnotes']:
    c = contents.get(p['id'], '')
    if c:
        p['content'] = c
        added += 1

with open(JSON, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)

size_mb = os.path.getsize(JSON) / 1024 / 1024
print(f'완료: {added}건에 content 필드 추가, {JSON} 크기 {size_mb:.1f}MB')
