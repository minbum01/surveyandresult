"""
해커스경찰 합격수기 크롤러 (police.hackers.com, id=pass_review)
- 대상: 경찰크롤링필요.md (CSV: page,idx,title,url) 의 url 들 — 깨진 title은 무시, url만 사용
- 인코딩: euc-kr (content.decode('euc-kr'))
- 서버 렌더링 → requests + BeautifulSoup (Selenium 불필요)
- 결과: police_reviews.json / 진행: crawl_police_progress.json

구조:
  제목   div.board_header h3.h3
  메타   div.board_details  ("작성월 2026.04 이*현")
  요약   ul.infoList > li ("카테고리 : 필기합격수기" 등 6필드)
  본문   div.board_body
"""
import requests
from bs4 import BeautifulSoup
import csv, io, json, os, sys, re, time

LIST_FILE = "경찰크롤링필요.md"
OUTPUT_FILE = "police_reviews.json"
PROGRESS_FILE = "crawl_police_progress.json"
DELAY = 0.6
TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def load_targets():
    """CSV에서 (page, idx, url) 추출. 깨진 title 무시."""
    txt = open(LIST_FILE, encoding="utf-8", errors="replace").read()
    rows = list(csv.DictReader(io.StringIO(txt)))
    out = []
    for r in rows:
        url = (r.get("url") or "").strip()
        idx = (r.get("idx") or "").strip()
        page = (r.get("page") or "").strip()
        if url.startswith("http") and idx.isdigit():
            out.append({"page": int(page) if page.isdigit() else None,
                        "idx": int(idx), "url": url})
    return out

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        return json.load(open(PROGRESS_FILE, encoding="utf-8"))
    return {"next": 0, "done": 0}

def save_progress(nxt, done):
    json.dump({"next": nxt, "done": done}, open(PROGRESS_FILE, "w", encoding="utf-8"))

def load_results():
    if os.path.exists(OUTPUT_FILE):
        return json.load(open(OUTPUT_FILE, encoding="utf-8"))
    return []

def save_results(res):
    json.dump(res, open(OUTPUT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _clean(s):
    return re.sub(r"\s+\n", "\n", s).strip() if s else ""

def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    hdr = soup.select_one("div.board_header h3.h3") or soup.select_one("h3.h3")
    title = hdr.get_text(strip=True) if hdr else ""

    author, wdate = "", ""
    det = soup.select_one("div.board_details")
    if det:
        dt = det.get_text(" ", strip=True)
        m = re.search(r"작성월\s*([\d.]+)", dt)
        if m:
            wdate = m.group(1)
        # 작성자: 작성월 값 뒤의 마지막 토큰(이름)
        toks = dt.replace("작성월", "").split()
        if toks:
            author = toks[-1] if not re.match(r"^[\d.]+$", toks[-1]) else ""

    summary = {}
    ul = soup.select_one("ul.infoList")
    if ul:
        for li in ul.find_all("li"):
            t = li.get_text(" ", strip=True)
            if ":" in t:
                k, v = t.split(":", 1)
                summary[k.strip()] = v.strip()

    body = soup.select_one("div.board_body")
    content = _clean(body.get_text("\n", strip=True)) if body else ""

    return {"title": title, "author": author, "date": wdate,
            "summary": summary, "content": content}

NOTICE_PAT = re.compile(r"\[필독\]|공지사항|게시판\s*이용|이용\s*안내")

def is_valid(p):
    # 진짜 합격수기: 요약(카테고리)+본문 존재, 공지/안내글([필독]·공지사항)은 제외
    if NOTICE_PAT.search(p["title"]):
        return False
    return bool(p["summary"].get("카테고리")) and bool(p["content"])

def main():
    targets = load_targets()
    prog = load_progress()
    results = load_results()
    start = prog["next"]
    total = len(targets)
    print(f"경찰 합격수기 크롤링: 총 {total}건")
    if start > 0:
        print(f"이어받기: {start}번째부터 (이미 {len(results)}건 수집)")

    sess = requests.Session(); sess.headers.update(HEADERS)
    skipped = 0
    i = start
    try:
        while i < total:
            t = targets[i]
            try:
                r = sess.get(t["url"], timeout=TIMEOUT)
                html = r.content.decode("euc-kr", errors="replace")
                p = parse(html)
                if is_valid(p):
                    p["idx"] = t["idx"]; p["page"] = t["page"]; p["url"] = t["url"]
                    results.append(p)
                    cat = p["summary"].get("카테고리", "?")
                    safe = p["title"][:38].encode("cp949", "replace").decode("cp949")
                    print(f"  [{i+1}/{total}] OK ({cat}) {safe} | {len(p['content'])}자")
                else:
                    skipped += 1
                    print(f"  [{i+1}/{total}] 스킵(공지/빈글) idx={t['idx']}")
            except requests.RequestException as e:
                skipped += 1
                print(f"  [{i+1}/{total}] 요청오류 idx={t['idx']}: {e}")

            i += 1
            if i % 50 == 0 or i == total:
                save_results(results)
                save_progress(i, len(results))
                print(f"  --- 중간저장: 수집 {len(results)} / 진행 {i}/{total} (스킵 {skipped}) ---")
            time.sleep(DELAY)
    except KeyboardInterrupt:
        print("\n중단(Ctrl+C). 저장합니다.")
    finally:
        save_results(results)
        save_progress(i, len(results))
        print(f"\n{'='*48}\n종료. 수집 {len(results)}건 (스킵 {skipped}) → {OUTPUT_FILE}")

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "test":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        targets = load_targets()
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        sess = requests.Session(); sess.headers.update(HEADERS)
        for t in targets[:n]:
            r = sess.get(t["url"], timeout=TIMEOUT)
            p = parse(r.content.decode("euc-kr", "replace"))
            print(f"idx={t['idx']} valid={is_valid(p)}")
            print("  제목:", p["title"], "| 작성:", p["date"], p["author"])
            print("  요약:", json.dumps(p["summary"], ensure_ascii=False))
            print("  본문:", len(p["content"]), "자 |", p["content"][:60].replace("\n"," "))
            print("-"*40)
    else:
        main()
