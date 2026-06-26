"""
프린트 스테이션 에이전트 (클라우드 큐 폴링형)
- Supabase print_jobs 큐를 폴링 → 작업 선점(claim_next_job) → 로컬 렌더 → 인쇄 → 완료
- 2대(A/B)가 같은 코드, STATION_ID만 다르게 → SKIP LOCKED 큐로 무충돌 자동분배
- 렌더는 "로컬 사본"으로 함(이 PC에 레포 + 로컬 정적서버). 답변은 live/_printdata.json 주입
  → 기존 print_server.py 의 ?print=1 + _printdata.json 방식 그대로 재활용

필요(이 PC에):
  - 레포 클론(이 파일과 live/ 등)
  - Chrome, tools/SumatraPDF.exe, 기본 프린터(A4) 지정
  - 환경변수:
      SUPABASE_URL          = https://xxxx.supabase.co
      SUPABASE_SERVICE_KEY  = service_role 키 (🔴 비공개! 이 PC에만)
      STATION_ID            = A   (또는 B)
실행:  set 환경변수 후  →  python print_agent.py
설계: 클라우드_인쇄시스템_설계.md §5
"""
import os, sys, json, time, subprocess, shutil, tempfile, threading, urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("AGENT_PORT", "8191"))           # 렌더용 로컬 서버 포트
PRINT_DATA = os.path.join(ROOT, "live", "_printdata.json")
PDF_OUT    = os.path.join(ROOT, "_agent_report.pdf")
PRINT_SETTINGS = os.environ.get("PRINT_SETTINGS", "noscale")
POLL_SEC   = 1.5

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")
STATION_ID   = os.environ.get("STATION_ID", "A")
PRINTER      = os.environ.get("PRINTER", "")   # 특정 프린터명(잉크젯 A/B). 빈값=기본 프린터
#  잉크젯 2대를 한 PC에서 쓰려면: 인스턴스 2개 실행, 각각
#    STATION_ID=A PRINTER="Canon ..."   /   STATION_ID=B PRINTER="Epson ..."
#  큐(SKIP LOCKED)가 두 인스턴스에 작업을 자동 분배 → 2대 병렬 출력.

# 시험종류 → 결과 페이지
EXAM_PAGE = {"공무원": "result.html", "경찰": "police_result.html", "소방": "result.html"}

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def find_chrome():
    for c in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")]:
        if os.path.isfile(c): return c
    return shutil.which("chrome") or shutil.which("chrome.exe")

def find_sumatra():
    c = os.path.join(ROOT, "tools", "SumatraPDF.exe")
    return c if os.path.isfile(c) else shutil.which("SumatraPDF")

CHROME = find_chrome()
SUMATRA = find_sumatra()


# ── Supabase RPC (service_role) ─────────────────────────────
def rpc(fn, args):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    body = json.dumps(args).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        txt = r.read().decode("utf-8")
        return json.loads(txt) if txt.strip() else None


# ── 로컬 정적 서버 (헤드리스 렌더용) ─────────────────────────
def start_local_server():
    class H(SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), partial(H, directory=ROOT))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


# ── 렌더 + 인쇄 (print_server.py 방식 재활용) ─────────────────
def render_pdf(page):
    if os.path.exists(PDF_OUT):
        try: os.remove(PDF_OUT)
        except OSError: pass
    prof = tempfile.mkdtemp(prefix="agent_")
    url = f"http://127.0.0.1:{PORT}/live/{page}?print=1&_={int(time.time()*1000)}"
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
           "--no-default-browser-check", "--disable-background-networking",
           f"--user-data-dir={prof}", "--virtual-time-budget=10000",
           "--run-all-compositor-stages-before-draw", "--no-pdf-header-footer",
           f"--print-to-pdf={PDF_OUT}", url]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try: p.wait(timeout=70)
    except subprocess.TimeoutExpired: pass
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(prof, ignore_errors=True)
    return os.path.exists(PDF_OUT) and os.path.getsize(PDF_OUT) > 1000

def print_pdf():
    target = ["-print-to", PRINTER] if PRINTER else ["-print-to-default"]
    subprocess.run([SUMATRA] + target + ["-silent",
                    "-print-settings", PRINT_SETTINGS, PDF_OUT],
                   timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def handle(job):
    exam = job.get("exam") or "공무원"
    page = EXAM_PAGE.get(exam, "result.html")
    # 답변·큐레이션 스냅샷·출력번호 주입 (결과 페이지 ?print=1 가 이 파일을 읽음)
    os.makedirs(os.path.dirname(PRINT_DATA), exist_ok=True)
    with open(PRINT_DATA, "w", encoding="utf-8") as f:
        json.dump({"ans": job.get("answers"), "cur": job.get("cur"),
                   "ticket": job.get("ticket")}, f, ensure_ascii=False)
    if not render_pdf(page):
        raise RuntimeError("render 실패")
    print_pdf()


def main():
    miss = [k for k, v in {"SUPABASE_URL": SUPABASE_URL, "SUPABASE_SERVICE_KEY": SERVICE_KEY}.items() if not v]
    if miss:
        print(f"⚠ 환경변수 필요: {', '.join(miss)}"); sys.exit(1)
    if not CHROME:  print("⚠ Chrome 없음"); sys.exit(1)
    if not SUMATRA: print("⚠ tools/SumatraPDF.exe 없음"); sys.exit(1)

    start_local_server()
    print(f"[station {STATION_ID}] 시작 · 프린터={PRINTER or '기본'} · 렌더서버 :{PORT} · 큐 폴링 {POLL_SEC}s")
    while True:
        try:
            job = rpc("claim_next_job", {"p_station": STATION_ID})
            if not job:
                time.sleep(POLL_SEC); continue
            jid = job.get("id"); tk = job.get("ticket")
            print(f"[station {STATION_ID}] 작업 #{jid} ticket={tk} exam={job.get('exam')} 처리중…")
            try:
                handle(job)
                rpc("complete_job", {"p_id": jid})
                print(f"[station {STATION_ID}] #{jid} 완료(출력)")
            except Exception as e:
                rpc("fail_job", {"p_id": jid, "p_err": str(e)[:300]})
                print(f"[station {STATION_ID}] #{jid} 실패: {e}")
        except KeyboardInterrupt:
            print("종료"); break
        except Exception as e:
            print(f"[station {STATION_ID}] 폴링 오류: {e} — {POLL_SEC*4:.0f}s 후 재시도")
            time.sleep(POLL_SEC * 4)


if __name__ == "__main__":
    main()
