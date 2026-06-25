"""
합격 리포트 — 완전 무창 인쇄 서버
- 기존 python -m http.server 대체 (정적 파일 서빙 + /print 엔드포인트)
- 흐름: 브라우저 "리포트 인쇄" 버튼 → POST /print {ans, cur}
        → live/_printdata.json 기록
        → 헤드리스 크롬으로 result.html?print=1 을 PDF 렌더 (창 0)
        → SumatraPDF 로 양면·가로넘김(short-edge) 무창 인쇄
- 인터넷 0 / 창 0
실행:  python print_server.py     (포트 8181)
"""
import json, os, sys, subprocess, threading, time, shutil, tempfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8181
PRINT_DATA = os.path.join(ROOT, "live", "_printdata.json")
PDF_OUT    = os.path.join(ROOT, "_print_report.pdf")
HEADLESS_PROFILE = os.path.join(ROOT, "_chrome_headless_profile")

# 인쇄 설정: A4 세로 1장(단면) + 실제크기 (위 1면 / 아래 2면 2-up)
PRINT_SETTINGS = "noscale"

def find_chrome():
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in cands:
        if os.path.isfile(c): return c
    return shutil.which("chrome") or shutil.which("chrome.exe")

def find_sumatra():
    c = os.path.join(ROOT, "tools", "SumatraPDF.exe")
    return c if os.path.isfile(c) else shutil.which("SumatraPDF")

CHROME = find_chrome()
SUMATRA = find_sumatra()
_lock = threading.Lock()


def render_pdf():
    """헤드리스 크롬으로 result.html?print=1 → PDF (창 없음)"""
    if os.path.exists(PDF_OUT):
        try: os.remove(PDF_OUT)
        except OSError: pass
    prof = tempfile.mkdtemp(prefix="hlc_")   # 매 인쇄마다 독립 프로필(잠금 충돌 방지)
    url = f"http://127.0.0.1:{PORT}/live/result.html?print=1&_={int(time.time()*1000)}"
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
        "--no-default-browser-check", "--disable-background-networking",
        f"--user-data-dir={prof}",
        "--virtual-time-budget=10000", "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_OUT}", url,
    ]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        p.wait(timeout=70)
    except subprocess.TimeoutExpired:
        pass
    # 프로세스 트리(자식까지) 정리 → 잔여 누적/프로필 잠금 방지
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(prof, ignore_errors=True)
    return os.path.exists(PDF_OUT) and os.path.getsize(PDF_OUT) > 1000


def print_pdf():
    """SumatraPDF 무창 인쇄 (기본 프린터, 양면 가로넘김)"""
    cmd = [SUMATRA, "-print-to-default", "-silent",
           "-print-settings", PRINT_SETTINGS, PDF_OUT]
    subprocess.run(cmd, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):  # 콘솔 조용히
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.split("?")[0] != "/print":
            return self._json(404, {"ok": False, "error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"bad payload: {e}"})

        if not CHROME:  return self._json(500, {"ok": False, "error": "Chrome 경로 없음"})
        if not SUMATRA: return self._json(500, {"ok": False, "error": "SumatraPDF 없음(tools/)"})

        with _lock:
            try:
                os.makedirs(os.path.dirname(PRINT_DATA), exist_ok=True)
                with open(PRINT_DATA, "w", encoding="utf-8") as f:
                    json.dump({"ans": payload.get("ans"), "cur": payload.get("cur")},
                              f, ensure_ascii=False)
                if not render_pdf():
                    return self._json(500, {"ok": False, "error": "PDF 렌더 실패"})
                print_pdf()
            except subprocess.TimeoutExpired:
                return self._json(500, {"ok": False, "error": "타임아웃"})
            except Exception as e:
                return self._json(500, {"ok": False, "error": str(e)})
        return self._json(200, {"ok": True})


def main():
    print(f"[print_server] ROOT={ROOT}")
    print(f"[print_server] Chrome={CHROME}")
    print(f"[print_server] Sumatra={SUMATRA}")
    print(f"[print_server] http://localhost:{PORT}/live/home.html  (Ctrl+C 종료)")
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=ROOT))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
