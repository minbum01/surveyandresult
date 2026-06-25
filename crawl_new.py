"""
공무원 합격수기 — 증분 크롤 (신규 글만) · 견고화 버전
- 대상: 목록 2~19페이지
- 수집 조건: 글 idx 가 IDX_MIN ~ IDX_MAX 범위인 것만 (1페이지급 최신 idx>MAX 제외)
- 기존 all_reviews.json 에 idx 기준 중복 제거 후 합치기
- 페이지마다 저장 → 중단해도 crawl_new_progress.json 으로 이어받기
- 견고화:
    * 페이지 로드 타임아웃 40초 (멈춤 글을 120초씩 기다리지 않음)
    * 상세 수집 실패 시 드라이버 재생성 후 최대 3회 재시도
    * 그래도 실패하면 all_reviews.json 에 저장하지 않음 → 재실행 시 재시도
      (실패 idx 는 crawl_new_failed.json 에 기록)
    * RESTART_EVERY 건마다 크롬 자동 재시작(메모리/세션 누적 방지)
- crawl_progress.json(기존 전체크롤) 은 건드리지 않음 · 토큰 0
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time, json, os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# === 설정 ===
BASE_URL = "https://gosi.hackers.com/html/mmove.htm?id=exam_passnote_new&m=&cate=&cate2=&cate3=&cate4=&cate5=&cate6=&idx=&user_id=&search_opt=&search_txt=&hb_year=&page={page}"
OUTPUT_FILE   = "all_reviews.json"
PROGRESS_FILE = "crawl_new_progress.json"
FAILED_FILE   = "crawl_new_failed.json"
PAGE_START = 2
PAGE_END   = 19
IDX_MIN    = 42266
IDX_MAX    = 42904
PAGE_LOAD_TIMEOUT = 40    # 한 페이지 로드 최대 대기(초)
POST_LOAD_WAIT = 4        # 로드 후 렌더 대기
LIST_LOAD_WAIT = 5
MAX_RETRY = 3             # 상세 수집 실패 시 재시도 횟수
RESTART_EVERY = 40        # n건마다 크롬 재시작


def idx_of(url):
    m = re.search(r"[?&]idx=(\d+)", url or "")
    return int(m.group(1)) if m else None


def load_existing():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_results(results):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_page": PAGE_START - 1, "added": 0}


def save_progress(page, added):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_page": page, "added": added}, f, ensure_ascii=False)


def record_failed(ix, title):
    failed = []
    if os.path.exists(FAILED_FILE):
        try:
            with open(FAILED_FILE, "r", encoding="utf-8") as f:
                failed = json.load(f)
        except Exception:
            failed = []
    if not any(x.get("idx") == ix for x in failed):
        failed.append({"idx": ix, "title": title})
        with open(FAILED_FILE, "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)


def clear_failed(ix):
    """이전에 실패했던 idx 가 재시도로 성공하면 실패목록에서 제거"""
    if not os.path.exists(FAILED_FILE):
        return
    try:
        with open(FAILED_FILE, "r", encoding="utf-8") as f:
            failed = json.load(f)
    except Exception:
        return
    new = [x for x in failed if x.get("idx") != ix]
    if len(new) != len(failed):
        with open(FAILED_FILE, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, indent=2)


def make_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    d = webdriver.Chrome(options=options)
    d.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    try:
        d.set_script_timeout(PAGE_LOAD_TIMEOUT)
    except Exception:
        pass
    return d


def get_posts_from_list(driver, page):
    driver.get(BASE_URL.format(page=page))
    time.sleep(LIST_LOAD_WAIT)
    posts = []
    tr_start, tr_end = (10, 25) if page == 1 else (2, 17)
    for i in range(tr_start, tr_end):
        try:
            base = f'//*[@id="wrapper"]/div[4]/div[2]/div[8]/div[1]/div/div/table/tbody/tr[{i}]'
            a = driver.find_element(By.XPATH, f"{base}/td[1]/a")
            title = a.text.strip()
            href = a.get_attribute("href")
            views = driver.find_element(By.XPATH, f"{base}/td[3]").text.strip()
            if title and href:
                posts.append({"title": title, "views": views, "href": href})
        except Exception:
            continue
    return posts


def get_post_detail(driver, href):
    driver.get(href)
    time.sleep(POST_LOAD_WAIT)
    summary = {}
    try:
        elem = driver.find_element(By.XPATH, '//*[@id="wrapper"]/div[4]/div[2]/div/div/div[1]/div/div/div[1]')
        for line in elem.text.strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                summary[k.strip()] = v.strip()
    except Exception:
        pass
    content = ""
    try:
        elem = driver.find_element(By.XPATH, '//*[@id="wrapper"]/div[4]/div[2]/div/div/div[2]')
        content = elem.text.strip()
    except Exception:
        pass
    return summary, content


def safe(s):
    return s[:50].encode("cp949", errors="replace").decode("cp949")


def main():
    results = load_existing()
    existing_idx = {idx_of(r.get("url")) for r in results}
    existing_idx.discard(None)
    print(f"기존 데이터: {len(results)}개 (idx {min(existing_idx)}~{max(existing_idx)})")
    print(f"수집 범위: 페이지 {PAGE_START}~{PAGE_END}, idx {IDX_MIN}~{IDX_MAX}")

    prog = load_progress()
    start_page = max(PAGE_START, prog["last_page"] + 1)
    added = prog.get("added", 0)
    if start_page > PAGE_START:
        print(f"이어받기: {prog['last_page']}p 완료, {added}건 추가됨 → {start_page}p부터")
    print()

    driver = make_driver()
    since_restart = 0
    first_fail_page = None   # 실패가 처음 생긴 페이지 (진행상황을 그 직전까지만 저장)

    def prog_page(cur):
        return cur if first_fail_page is None else first_fail_page - 1

    try:
        for page in range(start_page, PAGE_END + 1):
            print(f"\n{'='*50}\n[페이지 {page}] 목록 크롤링...")
            # 목록 로드도 타임아웃 시 1회 재시도(드라이버 재생성)
            try:
                posts = get_posts_from_list(driver, page)
            except Exception as e:
                print(f"  목록 로드 실패 → 드라이버 재시작 후 재시도 ({e})")
                try: driver.quit()
                except Exception: pass
                time.sleep(5)
                driver = make_driver(); since_restart = 0
                posts = get_posts_from_list(driver, page)

            print(f"  목록 {len(posts)}건")
            page_idxs = [idx_of(p["href"]) for p in posts if idx_of(p["href"])]

            targets = []
            for p in posts:
                ix = idx_of(p["href"])
                if ix is None or ix > IDX_MAX or ix < IDX_MIN or ix in existing_idx:
                    continue
                targets.append((ix, p))
            print(f"  → 대상 {len(targets)}건 (범위/중복 필터 후)")

            for n, (ix, p) in enumerate(targets):
                # 주기적 크롬 재시작
                if since_restart >= RESTART_EVERY:
                    print(f"  … {RESTART_EVERY}건마다 크롬 재시작")
                    try: driver.quit()
                    except Exception: pass
                    time.sleep(3)
                    driver = make_driver(); since_restart = 0

                print(f"  [{n+1}/{len(targets)}] idx{ix} {safe(p['title'])}...", end=" ")
                ok = False
                content = ""
                for attempt in range(1, MAX_RETRY + 1):
                    try:
                        summary, content = get_post_detail(driver, p["href"])
                        if content:           # 내용 있어야 성공
                            ok = True
                            break
                        raise RuntimeError("빈 본문")
                    except Exception as e:
                        if attempt < MAX_RETRY:
                            print(f"[재시도{attempt}]", end=" ")
                            try: driver.quit()
                            except Exception: pass
                            time.sleep(5)
                            driver = make_driver(); since_restart = 0
                        else:
                            print(f"실패({type(e).__name__})", end=" ")

                if ok:
                    results.append({
                        "title": p["title"], "views": p["views"], "url": p["href"],
                        "summary": summary, "content": content,
                    })
                    existing_idx.add(ix)
                    added += 1
                    since_restart += 1
                    clear_failed(ix)
                    print(f"OK ({len(content)}자)")
                else:
                    # 저장하지 않음 → 재실행 시 재시도. 실패 idx만 기록
                    record_failed(ix, p["title"])
                    if first_fail_page is None or page < first_fail_page:
                        first_fail_page = page
                    print("→ 건너뜀(다음 실행때 재시도)")

            save_results(results)
            save_progress(prog_page(page), added)
            print(f"  → 저장 (누적 {len(results)}개 / 이번 추가 {added}건)")

            if page_idxs and max(page_idxs) < IDX_MIN:
                print("\n페이지 최대 idx가 하한 미만 → 종료")
                break

    except KeyboardInterrupt:
        save_results(results); save_progress(prog_page(page), added)
        print(f"\n사용자 중단. {added}건 추가 저장됨. 재실행 시 {prog_page(page)+1}p부터.")
    except Exception as e:
        save_results(results); save_progress(prog_page(page), added)
        print(f"\n오류: {e}. {added}건 추가 저장됨. 재실행 시 이어받기.")
    finally:
        try: driver.quit()
        except Exception: pass
        print(f"\n{'='*50}\n증분 크롤 종료. 신규 {added}건 추가 → 총 {len(results)}개")
        if os.path.exists(FAILED_FILE):
            print(f"⚠ 실패분 있음 → {FAILED_FILE} 확인 후 재실행하면 재시도됨")


if __name__ == "__main__":
    main()
