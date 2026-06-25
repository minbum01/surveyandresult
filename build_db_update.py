"""
all_reviews.json → reviews.db  (증분 INSERT, 새 글만)
- 기존 reviews.db 를 삭제하지 않음 → 기존 태그(passnote_tags 등) 전부 보존
- DB 에 없는 idx 의 글만 passnotes 에 INSERT (keywords_extracted=0)
  → 이후 extract_tags.py 가 이 새 글만 태깅
- 매칭 키: url 의 idx (url 의 page= 파라미터는 글마다 다를 수 있어 idx로 비교)
- 토큰 0 (claude 호출 없음)
- 재실행 안전: 이미 들어간 idx 는 건너뜀
"""
import sqlite3, json, os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JSON_FILE = "all_reviews.json"
DB_FILE   = "reviews.db"


def idx_of(url):
    m = re.search(r"[?&]idx=(\d+)", url or "")
    return int(m.group(1)) if m else None


def main():
    if not os.path.exists(DB_FILE):
        print(f"⚠ {DB_FILE} 가 없습니다. 최초 1회는 build_db.py 로 전체 생성하세요.")
        sys.exit(1)
    if not os.path.exists(JSON_FILE):
        print(f"⚠ {JSON_FILE} 가 없습니다.")
        sys.exit(1)

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # 기존 DB 의 idx 집합
    existing_idx = set()
    for (url,) in cur.execute("SELECT url FROM passnotes").fetchall():
        ix = idx_of(url)
        if ix is not None:
            existing_idx.add(ix)
    before = cur.execute("SELECT COUNT(*) FROM passnotes").fetchone()[0]
    print(f"기존 DB: {before}개 (idx {min(existing_idx)}~{max(existing_idx)})")
    print(f"JSON   : {len(data)}개")

    inserted = 0
    skipped = 0
    seen = set()
    for item in data:
        ix = idx_of(item.get("url"))
        if ix is None:
            skipped += 1
            continue
        if ix in existing_idx or ix in seen:
            continue  # 이미 DB 에 있거나 JSON 내 중복
        seen.add(ix)

        s = item.get("summary", {}) or {}
        try:
            views = int(item.get("views", 0))
        except Exception:
            views = 0

        cur.execute("""
            INSERT INTO passnotes
                (title, views, url, exam_type, grade, region, job_series,
                 study_period, pass_year, category, content, keywords_extracted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            item.get("title", ""),
            views,
            item.get("url", ""),
            s.get("응시시험", ""),
            s.get("급수", ""),
            s.get("응시지역", ""),
            s.get("응시직렬", ""),
            s.get("수험기간", ""),
            s.get("합격년도", ""),
            s.get("카테고리", ""),
            item.get("content", ""),
        ))
        inserted += 1

    conn.commit()

    after = cur.execute("SELECT COUNT(*) FROM passnotes").fetchone()[0]
    pending = cur.execute("SELECT COUNT(*) FROM passnotes WHERE keywords_extracted=0").fetchone()[0]
    print(f"\n신규 INSERT: {inserted}개  (idx 없음 스킵 {skipped}개)")
    print(f"DB 총계   : {before} → {after}")
    print(f"태깅 대기(keywords_extracted=0): {pending}개  ← extract_tags.py 가 처리할 대상")
    if inserted:
        print("\n다음: python extract_tags.py  (오푸스 태깅, 사용량 보면서)")
        print("그 다음: python build_reviews_json.py  →  copy reviews_data.json live\\")

    conn.close()


if __name__ == "__main__":
    main()
