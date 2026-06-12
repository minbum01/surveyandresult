"""
police_reviews.json → police_reviews.db (경찰 전용, 소방/공무원 DB 와 분리)
매핑: 카테고리→category, 응시연도→pass_year, 응시직렬→job_series, exam_type='경찰'
"""
import sqlite3, json, os

JSON_FILE = "police_reviews.json"
DB_FILE = "police_reviews.db"

if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

conn = sqlite3.connect(DB_FILE); cur = conn.cursor()
cur.executescript("""
CREATE TABLE passnotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,   -- police idx
    title TEXT, views INTEGER, url TEXT,
    exam_type TEXT, grade TEXT, region TEXT, job_series TEXT,
    study_period TEXT, pass_year TEXT, category TEXT, content TEXT,
    keywords_extracted INTEGER DEFAULT 0
);
CREATE TABLE tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, count INTEGER DEFAULT 0);
CREATE TABLE passnote_tags (passnote_id INTEGER, tag_id INTEGER, PRIMARY KEY (passnote_id, tag_id));
CREATE TABLE instructors (id INTEGER PRIMARY KEY AUTOINCREMENT, passnote_id INTEGER, subject TEXT, name TEXT);
CREATE TABLE textbooks (id INTEGER PRIMARY KEY AUTOINCREMENT, passnote_id INTEGER, subject TEXT, name TEXT);
""")

data = json.load(open(JSON_FILE, encoding="utf-8"))
for x in data:
    s = x.get("summary", {})
    ey = x.get("exam_year")
    cur.execute("""INSERT INTO passnotes
        (source_id,title,views,url,exam_type,grade,region,job_series,study_period,pass_year,category,content)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (x.get("idx"), x.get("title",""), 0, x.get("url",""),
         "경찰", s.get("응시차수",""), s.get("응시지역",""), s.get("응시직렬",""),
         s.get("수험기간",""), str(ey) if ey else "", s.get("카테고리",""), x.get("content","")))
conn.commit()

print(f"DB 저장 완료: {cur.execute('SELECT COUNT(*) FROM passnotes').fetchone()[0]}개 → {DB_FILE}")
print("\n── 카테고리 ──")
for r in cur.execute("SELECT category, COUNT(*) c FROM passnotes GROUP BY category ORDER BY c DESC"):
    print(f"  {r[0] or '미상':12}: {r[1]}")
print("\n── 응시연도 ──")
for r in cur.execute("SELECT pass_year, COUNT(*) c FROM passnotes GROUP BY pass_year ORDER BY pass_year DESC"):
    print(f"  {r[0] or '미상':8}: {r[1]}")
conn.close()
