"""
fire_reviews.json → fire_reviews.db (소방 전용, 공무원 reviews.db 와 분리)
스키마는 기존 build_db.py 와 동일 + source_id(efire review id) 추가.
매핑: 구분→category, exam_year(응시연도 정규화)→pass_year, 급수 없음→''
"""
import sqlite3, json, os

JSON_FILE = "fire_reviews.json"
DB_FILE = "fire_reviews.db"

if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE passnotes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER,  -- efire review id
    title           TEXT,
    views           INTEGER,
    url             TEXT,
    exam_type       TEXT,   -- 응시시험(소방)
    grade           TEXT,   -- 급수(소방 없음 → '')
    region          TEXT,   -- 응시지역
    job_series      TEXT,   -- 응시직렬
    study_period    TEXT,   -- 수험기간
    pass_year       TEXT,   -- 응시연도(정규화)
    category        TEXT,   -- 구분(최종합격/필기합격 등)
    content         TEXT,
    keywords_extracted INTEGER DEFAULT 0
);
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, count INTEGER DEFAULT 0
);
CREATE TABLE passnote_tags (
    passnote_id INTEGER, tag_id INTEGER,
    PRIMARY KEY (passnote_id, tag_id)
);
CREATE TABLE instructors (
    id INTEGER PRIMARY KEY AUTOINCREMENT, passnote_id INTEGER, subject TEXT, name TEXT
);
CREATE TABLE textbooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, passnote_id INTEGER, subject TEXT, name TEXT
);
""")

data = json.load(open(JSON_FILE, encoding="utf-8"))
for x in data:
    s = x.get("summary", {})
    try:
        views = int(x.get("views", 0) or 0)
    except:
        views = 0
    ey = x.get("exam_year")
    cur.execute("""
        INSERT INTO passnotes
          (source_id, title, views, url, exam_type, grade, region, job_series,
           study_period, pass_year, category, content)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        x.get("id"), x.get("title", ""), views, x.get("url", ""),
        s.get("응시시험", ""), "", s.get("응시지역", ""), s.get("응시직렬", ""),
        s.get("수험기간", ""), str(ey) if ey else "", s.get("구분", ""),
        x.get("content", ""),
    ))
conn.commit()

total = cur.execute("SELECT COUNT(*) FROM passnotes").fetchone()[0]
print(f"DB 저장 완료: {total}개 → {DB_FILE}")
print("\n── 구분 분포 ──")
for r in cur.execute("SELECT category, COUNT(*) c FROM passnotes GROUP BY category ORDER BY c DESC"):
    print(f"  {r[0] or '미상':12}: {r[1]}")
print("\n── 응시연도 분포 ──")
for r in cur.execute("SELECT pass_year, COUNT(*) c FROM passnotes GROUP BY pass_year ORDER BY pass_year DESC"):
    print(f"  {r[0] or '미상':8}: {r[1]}")
conn.close()
