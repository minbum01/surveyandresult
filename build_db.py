"""
JSON → SQLite DB 변환
"""
import sqlite3
import json
import os

JSON_FILE = "all_reviews.json"
DB_FILE = "reviews.db"

# DB 새로 만들기
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

# ── 테이블 생성 ──────────────────────────────────────

cur.executescript("""
CREATE TABLE passnotes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT,
    views           INTEGER,
    url             TEXT,
    exam_type       TEXT,   -- 응시시험
    grade           TEXT,   -- 급수
    region          TEXT,   -- 응시지역
    job_series      TEXT,   -- 응시직렬
    study_period    TEXT,   -- 수험기간
    pass_year       TEXT,   -- 합격년도
    category        TEXT,   -- 카테고리
    content         TEXT,
    keywords_extracted INTEGER DEFAULT 0
);

CREATE TABLE tags (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT UNIQUE,
    count   INTEGER DEFAULT 0
);

CREATE TABLE passnote_tags (
    passnote_id INTEGER,
    tag_id      INTEGER,
    PRIMARY KEY (passnote_id, tag_id),
    FOREIGN KEY (passnote_id) REFERENCES passnotes(id),
    FOREIGN KEY (tag_id)      REFERENCES tags(id)
);

CREATE TABLE instructors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    passnote_id INTEGER,
    subject     TEXT,
    name        TEXT,
    FOREIGN KEY (passnote_id) REFERENCES passnotes(id)
);

CREATE TABLE textbooks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    passnote_id INTEGER,
    subject     TEXT,
    name        TEXT,
    FOREIGN KEY (passnote_id) REFERENCES passnotes(id)
);
""")

# ── JSON 투입 ─────────────────────────────────────────

with open(JSON_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"총 {len(data)}개 수기 투입 중...")

success = 0
for item in data:
    s = item.get('summary', {})

    # views가 숫자인지 확인
    try:
        views = int(item.get('views', 0))
    except:
        views = 0

    cur.execute("""
        INSERT INTO passnotes
            (title, views, url, exam_type, grade, region, job_series, study_period, pass_year, category, content)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item.get('title', ''),
        views,
        item.get('url', ''),
        s.get('응시시험', ''),
        s.get('급수', ''),
        s.get('응시지역', ''),
        s.get('응시직렬', ''),
        s.get('수험기간', ''),
        s.get('합격년도', ''),
        s.get('카테고리', ''),
        item.get('content', '')
    ))
    success += 1

conn.commit()

# ── 결과 확인 ─────────────────────────────────────────

total = cur.execute("SELECT COUNT(*) FROM passnotes").fetchone()[0]
print(f"DB 저장 완료: {total}개")
print()

# 응시시험 분포
print("── 응시시험 분포 ──")
for row in cur.execute("SELECT exam_type, COUNT(*) as cnt FROM passnotes GROUP BY exam_type ORDER BY cnt DESC"):
    print(f"  {row[0] or '미상':12} : {row[1]}개")

# 급수 분포
print("\n── 급수 분포 ──")
for row in cur.execute("SELECT grade, COUNT(*) as cnt FROM passnotes GROUP BY grade ORDER BY cnt DESC"):
    print(f"  {row[0] or '미상':10} : {row[1]}개")

# 합격년도 분포
print("\n── 합격년도 분포 ──")
for row in cur.execute("SELECT pass_year, COUNT(*) as cnt FROM passnotes GROUP BY pass_year ORDER BY pass_year DESC"):
    print(f"  {row[0] or '미상':10} : {row[1]}개")

conn.close()
print(f"\n파일 저장: {DB_FILE}")
