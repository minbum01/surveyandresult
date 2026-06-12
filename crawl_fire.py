"""
해커스소방 합격수기 크롤러 (efire.hackers.com/review/{id})
- 대상: review id 915 ~ 1348 (역순으로 1348 → 915)
- 서버 렌더링 HTML → Selenium 불필요, requests + BeautifulSoup
- 추출: 제목, 작성자, 작성일, 조회수, 요약 6필드, Q&A 본문
- 결과: fire_reviews.json  / 진행상황: crawl_fire_progress.json

구조 (2026-06 기준):
  제목      <p class="...__title">...</p>          (detail info 블록)
  메타      <div class="...__regInfo">작성자 | 날짜 | 조회수 N</div>
  요약      <ul class="...__reviewInfo"><li><span>키</span><span>값</span></li>×6</ul>
  본문      <div class="review-template"> 6×<div class="question-box">
              <p class="question-title">..</p> <div class="answer-area">..</div>
"""
import requests
from bs4 import BeautifulSoup
import json, os, sys, time

# === 설정 ===
URL_TMPL = "https://efire.hackers.com/review/{id}"
ID_START = 1348          # 최신
ID_END   = 915           # 가장 오래된 (포함)
OUTPUT_FILE   = "fire_reviews.json"
PROGRESS_FILE = "crawl_fire_progress.json"
REQUEST_DELAY = 0.6      # 서버 배려용 대기 (초)
TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# === 진행상황/결과 입출력 ===
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_id": ID_START + 1, "done": 0}   # 아직 시작 안함 → 1349

def save_progress(last_id, done):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_id": last_id, "done": done}, f, ensure_ascii=False)

def load_results():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_results(results):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

# === 파싱 ===
def _clean(s):
    return s.replace("﻿", "").strip() if s else ""

def _find_by_suffix(soup, suffix, include=None):
    """CSS-module 해시 클래스(예: ...__title)는 빌드마다 바뀔 수 있어 접미사로 매칭.
    include 문자열이 클래스에 포함된 것만(예: 'detail' → 본문 상세 블록)."""
    def ok(t):
        if not t.has_attr("class"):
            return False
        return any(c.endswith(suffix) and (not include or include in c) for c in t["class"])
    return soup.find(ok)

def parse_review(html):
    soup = BeautifulSoup(html, "html.parser")

    # 제목: 상세 블록(detail-...__title) — 상단 브레드크럼의 __title 과 구분
    title_el = _find_by_suffix(soup, "__title", include="detail")
    title = _clean(title_el.get_text(strip=True)) if title_el else ""

    # 메타: "작성자 | 날짜 | 조회수 N"
    author, date, views = "", "", ""
    reg_el = _find_by_suffix(soup, "__regInfo")
    if reg_el:
        parts = [p.strip() for p in reg_el.get_text("|", strip=True).split("|") if p.strip()]
        if len(parts) >= 1: author = parts[0]
        if len(parts) >= 2: date = parts[1]
        if len(parts) >= 3:
            views = "".join(ch for ch in parts[2] if ch.isdigit())

    # 요약 6필드
    summary = {}
    info_ul = _find_by_suffix(soup, "__reviewInfo")
    if info_ul:
        for li in info_ul.find_all("li"):
            spans = li.find_all("span")
            # 구조: <span>키</span><span class=line></span><span>값</span> → 값은 마지막 span
            if len(spans) >= 2:
                key = _clean(spans[0].get_text(strip=True))
                val = _clean(spans[-1].get_text(strip=True))
                if key:
                    summary[key] = val

    # 본문: detail-...__content 안에 신양식(.review-template Q&A) 또는 구양식(자유서술)
    questions = []
    content = ""
    body_el = _find_by_suffix(soup, "__content", include="detail")
    tpl = body_el.find(class_="review-template") if body_el else soup.find(class_="review-template")
    if tpl:  # 신양식: 6문항 Q&A
        for box in tpl.find_all(class_="question-box"):
            q_el = box.find(class_="question-title")
            a_el = box.find(class_="answer-area")
            q = _clean(q_el.get_text(strip=True)) if q_el else ""
            a = _clean(a_el.get_text("\n", strip=True)) if a_el else ""
            if q or a:
                questions.append({"q": q, "a": a})
        content = "\n\n".join(f"{x['q']}\n{x['a']}" for x in questions if x["a"])
    elif body_el:  # 구양식: 자유서술 전체 텍스트
        content = _clean(body_el.get_text("\n", strip=True))

    return {
        "title": title, "author": author, "date": date, "views": views,
        "summary": summary, "questions": questions, "content": content,
    }

def is_valid(parsed):
    """합격수기 글로 보이는지 (제목 + 본문 또는 요약 존재)."""
    return bool(parsed["title"]) and (bool(parsed["content"]) or bool(parsed["summary"]))

# === 메인 ===
def main():
    progress = load_progress()
    results = load_results()
    start_id = min(progress["last_id"] - 1, ID_START)  # 이어받기: 마지막 처리 id 다음(더 작은 값)

    sess = requests.Session()
    sess.headers.update(HEADERS)

    print(f"크롤링 범위: {ID_START} → {ID_END} (역순)")
    if start_id < ID_START:
        print(f"이어받기: id {start_id}부터 재개 (이미 {len(results)}개 수집)\n")

    miss_streak = 0
    cur = start_id
    try:
        while cur >= ID_END:
            url = URL_TMPL.format(id=cur)
            try:
                r = sess.get(url, timeout=TIMEOUT)
                if r.status_code != 200:
                    print(f"  [{cur}] HTTP {r.status_code} → 건너뜀")
                    miss_streak += 1
                else:
                    r.encoding = "utf-8"
                    parsed = parse_review(r.text)
                    if is_valid(parsed):
                        parsed["id"] = cur
                        parsed["url"] = url
                        results.append(parsed)
                        miss_streak = 0
                        gubun = parsed["summary"].get("구분", "?")
                        safe = parsed["title"][:42].encode("cp949", "replace").decode("cp949")
                        print(f"  [{cur}] OK ({gubun}) {safe} | {len(parsed['content'])}자")
                    else:
                        miss_streak += 1
                        print(f"  [{cur}] 합격수기 아님/빈 페이지 → 건너뜀")
            except requests.RequestException as e:
                print(f"  [{cur}] 요청오류: {e}")
                miss_streak += 1

            # 50개마다 저장
            if cur % 50 == 0 or cur == ID_END:
                save_results(results)
                save_progress(cur, len(results))
                print(f"  --- 중간저장: 누적 {len(results)}개 (id {cur}) ---")

            cur -= 1
            time.sleep(REQUEST_DELAY)

    except KeyboardInterrupt:
        print("\n사용자 중단(Ctrl+C). 현재까지 저장합니다.")
    finally:
        save_results(results)
        save_progress(cur + 1, len(results))
        print(f"\n{'='*48}")
        print(f"종료. 수집 {len(results)}개 → {OUTPUT_FILE}")

if __name__ == "__main__":
    # 인자로 테스트 모드: python crawl_fire.py test 1348 1346
    if len(sys.argv) >= 2 and sys.argv[1] == "test":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        a = int(sys.argv[2]); b = int(sys.argv[3]) if len(sys.argv) > 3 else a
        sess = requests.Session(); sess.headers.update(HEADERS)
        for i in range(a, b - 1, -1):
            r = sess.get(URL_TMPL.format(id=i), timeout=TIMEOUT); r.encoding = "utf-8"
            p = parse_review(r.text)
            print(f"[{i}] valid={is_valid(p)}")
            print("  제목 :", p["title"])
            print("  메타 :", p["author"], "/", p["date"], "/ 조회", p["views"])
            print("  요약 :", json.dumps(p["summary"], ensure_ascii=False))
            print("  문항 :", len(p["questions"]), "개 | 본문", len(p["content"]), "자")
            print("-" * 40)
    else:
        main()
