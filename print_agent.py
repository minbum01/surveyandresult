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
      AUTO_CLAIM            = 1(기본,자동큐) / 0(수동 picker 전용 폴백)
실행:  set 환경변수 후  →  python print_agent.py
      · 자동:  print_station.bat / print_station_2printers.bat
      · 수동 폴백:  print_station_manual.bat  (브라우저에서 목록 보고 직접 출력)

수동 출력 폴백(클라우드 자동분배가 말썽일 때):
  - 에이전트가 로컬 http://127.0.0.1:<포트>/__pick 페이지를 띄움
  - print_jobs 목록을 service_role로 읽어 표시 → [이 PC로 출력] 클릭 시 그 PC에서 렌더·인쇄
  - 출력 전 status를 printing으로 선점 → 자동 스테이션과 중복 출력 방지
설계: 클라우드_인쇄시스템_설계.md §5
"""
import os, sys, json, time, subprocess, shutil, tempfile, threading, urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")
STATION_ID   = os.environ.get("STATION_ID", "A")
PRINTER      = os.environ.get("PRINTER", "")   # 특정 프린터명. 빈값=기본 프린터
PRINTER_A    = os.environ.get("PRINTER_A", "") # 수동 picker용 프린터 A 이름
PRINTER_B    = os.environ.get("PRINTER_B", "") # 수동 picker용 프린터 B 이름
#  ── 한 PC에 프린터 2대(인스턴스 2개) ──
#    창1: STATION_ID=A PRINTER="Canon ..."    창2: STATION_ID=B PRINTER="Epson ..."
#    아래 PORT/PRINT_DATA/PDF_OUT 가 STATION_ID 별로 자동 분리되어 동시 인쇄해도 충돌 없음.
#    큐(SKIP LOCKED)가 두 인스턴스에 작업을 자동 분배 → 2대 병렬 출력(밀림 방지).

# 인스턴스 격리: 같은 PC에서 2개 띄워도 렌더 포트·임시파일이 안 겹치도록 STATION_ID로 분리
_sid = "".join(c for c in STATION_ID if c.isalnum()) or "A"
PORT = int(os.environ.get("AGENT_PORT", str(8191 + (sum(map(ord, _sid)) % 80))))  # 렌더용 로컬 서버 포트
PRINT_DATA = os.path.join(ROOT, "live", f"_printdata_{_sid}.json")  # 인스턴스별 답변 주입 파일
PDF_OUT    = os.path.join(ROOT, f"_agent_report_{_sid}.pdf")        # 인스턴스별 PDF
PRINT_SETTINGS = os.environ.get("PRINT_SETTINGS", "noscale")
POLL_SEC   = 1.5

# 자동 큐 폴링 on/off. "0"이면 자동으로 안 가져가고 수동 picker로만 출력(폴백 모드).
AUTO_CLAIM = os.environ.get("AUTO_CLAIM", "1") != "0"
# 렌더/인쇄는 임시파일(PRINT_DATA/PDF_OUT) 공유 → 같은 인스턴스 내 동시실행 방지용 락
PRINT_LOCK = threading.Lock()

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

# ── Supabase REST (service_role) — 테이블 직접 read/patch (수동 picker용) ──
def rest(method, path, body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json", "Prefer": "return=representation",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        txt = r.read().decode("utf-8")
        return json.loads(txt) if txt.strip() else None


# ── 로컬 정적 서버 (+ 수동 picker API) ───────────────────────
def start_local_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), partial(PickerHandler, directory=ROOT))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


# ── 렌더 + 인쇄 (print_server.py 방식 재활용) ─────────────────
def render_pdf(page):
    if os.path.exists(PDF_OUT):
        try: os.remove(PDF_OUT)
        except OSError: pass
    prof = tempfile.mkdtemp(prefix="agent_")
    pdname = os.path.basename(PRINT_DATA)   # 인스턴스별 답변파일을 페이지가 fetch 하도록 전달
    url = f"http://127.0.0.1:{PORT}/live/{page}?print=1&pd={pdname}&_={int(time.time()*1000)}"
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

def print_pdf(printer=None):
    name = printer if printer is not None else PRINTER   # 명시 프린터 > 기본 PRINTER > 윈도우 기본
    target = ["-print-to", name] if name else ["-print-to-default"]
    subprocess.run([SUMATRA] + target + ["-silent",
                    "-print-settings", PRINT_SETTINGS, PDF_OUT],
                   timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def handle(job, printer=None):
    exam = job.get("exam") or "공무원"
    page = EXAM_PAGE.get(exam, "result.html")
    # 답변·큐레이션 스냅샷·출력번호 주입 (결과 페이지 ?print=1 가 이 파일을 읽음)
    #   label = 기기별 라벨(C-3). 종이에 찍혀 사람↔종이 매칭에 쓰임.
    dev, seq = job.get("device"), job.get("device_seq")
    label = f"{dev}-{seq}" if (dev and seq is not None) else None
    os.makedirs(os.path.dirname(PRINT_DATA), exist_ok=True)
    with open(PRINT_DATA, "w", encoding="utf-8") as f:
        json.dump({"ans": job.get("answers"), "cur": job.get("cur"),
                   "ticket": job.get("ticket"), "label": label,
                   "seed": job.get("seed")}, f, ensure_ascii=False)   # 시드로 후기선택 고정
    if not render_pdf(page):
        raise RuntimeError("render 실패")
    print_pdf(printer)


# ── 수동 출력: 특정 작업 1건을 골라 인쇄 (picker가 호출) ──────
def print_specific(job_id, printer=None, station_label=None):
    rows = rest("GET", f"print_jobs?id=eq.{int(job_id)}&select=*")
    if not rows:
        raise RuntimeError(f"작업 #{job_id} 없음")
    job = rows[0]
    with PRINT_LOCK:
        # 'printing'으로 먼저 표시 → 자동 스테이션이 같은 걸 못 가져가게(중복 출력 방지)
        rest("PATCH", f"print_jobs?id=eq.{int(job_id)}",
             {"status": "printing", "station": station_label or STATION_ID})
        try:
            handle(job, printer)
            rpc("complete_job", {"p_id": int(job_id)})
        except Exception as e:
            rpc("fail_job", {"p_id": int(job_id), "p_err": str(e)[:300]})
            raise
    return job.get("ticket")


# ── picker 페이지 (스테이션 PC 브라우저에서 목록 보고 직접 출력) ──
PICKER_HTML = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>수동 출력 — 프린트대</title>
<style>
 body{margin:0;font-family:system-ui,'Malgun Gothic',sans-serif;background:#0f1115;color:#e7eaf0}
 header{display:flex;align-items:center;gap:12px;padding:12px 18px;border-bottom:1px solid #262b36;position:sticky;top:0;background:#0f1115}
 h1{font-size:16px;margin:0} .sp{flex:1} .muted{color:#9aa3b2;font-size:13px}
 button{font:inherit;border:1px solid #262b36;background:#1f2530;color:#e7eaf0;border-radius:8px;padding:7px 12px;cursor:pointer}
 button.p{background:#2f7de0;border-color:#2f7de0;color:#fff;font-weight:700}
 table{width:100%;border-collapse:collapse} th,td{text-align:left;padding:9px 12px;border-bottom:1px solid #262b36;font-size:14px}
 th{color:#9aa3b2;font-size:12px;text-transform:uppercase} .tk{font-weight:800;font-size:16px}
 .b{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:700}
 .pending{background:rgba(201,162,39,.16);color:#c9a227}.printing{background:rgba(47,125,224,.16);color:#2f7de0}
 .done{background:rgba(46,158,91,.16);color:#2e9e5b}.error{background:rgba(217,72,75,.18);color:#d9484b}
 .prof{color:#9aa3b2;font-size:13px;max-width:360px}
</style></head><body>
<header><h1>🖨️ 수동 출력</h1><span class=muted id=prn></span><span class=muted id=msg></span>
 <span class=sp></span>
 <input id=q placeholder="번호 검색 예: C-3" style="font:inherit;background:#1f2530;color:#e7eaf0;border:1px solid #262b36;border-radius:8px;padding:7px 12px;width:150px">
 <label class=muted><input type=checkbox id=onlywait> 대기만</label>
 <label class=muted><input type=checkbox id=auto checked> 자동새로고침</label>
 <button onclick=load()>새로고침</button></header>
<table><thead><tr><th>번호</th><th>태블릿</th><th>시험</th><th>프로필</th><th>상태</th><th>시각</th><th>출력</th></tr></thead>
<tbody id=rows><tr><td colspan=7 style=padding:40px;text-align:center;color:#9aa3b2>불러오는 중…</td></tr></tbody></table>
<script>
const $=id=>document.getElementById(id);
const ST={pending:'대기',printing:'인쇄중',done:'완료',error:'오류'};
let PRN={A:'',B:'',default:''}, TWO=false;
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function lab(j){return (j.device&&j.device_seq!=null)?(j.device+'-'+j.device_seq):('#'+(j.ticket==null?'—':j.ticket))}
function prof(a){try{if(!Array.isArray(a))return'';return a.map(s=>Array.isArray(s)?s.map(x=>x.label||x.tagId).join('·'):'').filter(Boolean).slice(0,5).join(' / ')}catch(e){return''}}
function fmt(s){if(!s)return'—';const d=new Date(s),p=n=>String(n).padStart(2,'0');return p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds())}
async function cfg(){try{PRN=await (await fetch('/__printers')).json();TWO=!!(PRN.A&&PRN.B);
  $('prn').textContent=TWO?('A: '+PRN.A+'   B: '+PRN.B):('프린터: '+(PRN.default||'윈도우 기본'));}catch(e){}}
function actions(j){
  if(TWO) return '<button class="p go" data-id='+j.id+' data-pr=A>🖨 A로</button> '
                +'<button class="p go" data-id='+j.id+' data-pr=B>🖨 B로</button>';
  return '<button class="p go" data-id='+j.id+' data-pr="">이 PC로 출력</button>';
}
async function load(){
 try{const r=await fetch('/__jobs');let d=await r.json();
  if(!Array.isArray(d)){$('rows').innerHTML='<tr><td colspan=7 style=padding:30px;text-align:center;color:#d9484b>'+esc(d.error||'읽기 오류')+'</td></tr>';return}
  if($('onlywait').checked) d=d.filter(j=>j.status==='pending'||j.status==='error');
  const q=($('q').value||'').trim().toLowerCase();
  if(q) d=d.filter(j=>lab(j).toLowerCase().includes(q)||String(j.device||'').toLowerCase().includes(q));
  if(!d.length){$('rows').innerHTML='<tr><td colspan=7 style=padding:40px;text-align:center;color:#9aa3b2>표시할 작업이 없습니다.</td></tr>';return}
  $('rows').innerHTML=d.map(j=>'<tr><td class=tk>'+esc(lab(j))+'</td><td>'+esc(j.device||'미상')+'</td><td>'+esc(j.exam||'')+'</td><td class=prof>'+esc(prof(j.answers))+'</td><td><span class="b '+j.status+'">'+(ST[j.status]||j.status)+'</span></td><td class=muted>'+fmt(j.created_at)+'</td><td>'+actions(j)+'</td></tr>').join('');
 }catch(e){$('msg').textContent='오류: '+e.message}
}
$('rows').addEventListener('click',e=>{const b=e.target.closest('.go');if(b)pr(b);});
async function pr(btn){
 const id=+btn.dataset.id, printer=btn.dataset.pr||'';
 btn.disabled=true;btn.textContent='출력 중…';
 try{const r=await fetch('/__print',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,printer})});
  const d=await r.json();if(d.ok){btn.textContent='완료 ✓ #'+(d.ticket??'')}else{btn.textContent='실패';btn.disabled=false;alert('실패: '+(d.error||''))}
 }catch(e){btn.textContent='실패';btn.disabled=false;alert(e.message)}
 setTimeout(load,1500);
}
let t=null;function poll(){if(t)clearInterval(t);if($('auto').checked)t=setInterval(load,4000)}
$('auto').onchange=poll;$('onlywait').onchange=load;$('q').oninput=load;
(async()=>{await cfg();load();poll();})();
</script></body></html>"""


class PickerHandler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.split("?")[0] == "/__pick":
            b = PICKER_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b); return
        if self.path.split("?")[0] == "/__printers":
            self._json(200, {"A": PRINTER_A, "B": PRINTER_B, "default": PRINTER})
            return
        if self.path.split("?")[0] == "/__jobs":
            try:
                rows = rest("GET", "print_jobs?select=id,ticket,device,device_seq,exam,status,"
                                   "created_at,answers&order=created_at.desc&limit=60")
                self._json(200, rows or [])
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] == "/__print":
            try:
                ln = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(ln) or b"{}")
                pr = (body.get("printer") or "").strip().upper()   # ''|'A'|'B'
                pname = (PRINTER_A or None) if pr == "A" else (PRINTER_B or None) if pr == "B" else None
                tk = print_specific(body["id"], printer=pname, station_label=(pr or STATION_ID))
                self._json(200, {"ok": True, "ticket": tk})
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
            return
        self.send_response(404); self.end_headers()


def main():
    miss = [k for k, v in {"SUPABASE_URL": SUPABASE_URL, "SUPABASE_SERVICE_KEY": SERVICE_KEY}.items() if not v]
    if miss:
        print(f"⚠ 환경변수 필요: {', '.join(miss)}"); sys.exit(1)
    if not CHROME:  print("⚠ Chrome 없음"); sys.exit(1)
    if not SUMATRA: print("⚠ tools/SumatraPDF.exe 없음"); sys.exit(1)

    start_local_server()
    pick_url = f"http://127.0.0.1:{PORT}/__pick"
    print(f"[station {STATION_ID}] 시작 · 프린터={PRINTER or '기본'} · 렌더서버 :{PORT}")
    print(f"[station {STATION_ID}] 수동 출력 페이지: {pick_url}")

    if not AUTO_CLAIM:
        # 폴백(수동) 모드: 자동으로 큐를 가져가지 않음. 위 picker 페이지에서 직접 출력.
        print(f"[station {STATION_ID}] 자동 큐 OFF — 수동 출력 모드. 위 주소를 브라우저에서 여세요.")
        try:
            while True: time.sleep(3600)
        except KeyboardInterrupt:
            print("종료"); return

    print(f"[station {STATION_ID}] 자동 큐 폴링 {POLL_SEC}s (자동+수동 둘 다 가능)")
    while True:
        try:
            job = rpc("claim_next_job", {"p_station": STATION_ID})
            if not job:
                time.sleep(POLL_SEC); continue
            jid = job.get("id"); tk = job.get("ticket")
            print(f"[station {STATION_ID}] 작업 #{jid} ticket={tk} exam={job.get('exam')} 처리중…")
            try:
                with PRINT_LOCK:                 # 수동 picker와 동시 인쇄 충돌 방지
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
