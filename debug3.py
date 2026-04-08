"""
stdin으로 프롬프트 전달 테스트
"""
import sqlite3, subprocess, os, re, json, tempfile

CLAUDE_CMD = r"C:\Users\admin\AppData\Roaming\npm\claude.cmd"
TIMEOUT = 60

def call_claude_stdin(prompt):
    """stdin으로 프롬프트 전달"""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE", None)

    proc = subprocess.Popen(
        [CLAUDE_CMD, "--dangerously-skip-permissions", "-p", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    try:
        stdout, stderr = proc.communicate(
            input=prompt.encode("utf-8"),
            timeout=TIMEOUT
        )
        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        print(f"[stdin] rc={proc.returncode}, {len(out)}chars")
        if err: print(f"  stderr: {err[:150]}")
        print(f"  out: {out[:300]}")
        return out if proc.returncode == 0 else None
    except subprocess.TimeoutExpired:
        proc.kill()
        return None

def call_claude_tempfile(prompt):
    """tempfile로 프롬프트 전달 (PowerShell 경유)"""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE", None)

    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.txt', delete=False) as f:
        f.write(prompt)
        tmp = f.name

    try:
        ps_cmd = f'$p = [IO.File]::ReadAllText("{tmp}", [Text.Encoding]::UTF8); & "{CLAUDE_CMD}" --dangerously-skip-permissions -p $p'
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, timeout=TIMEOUT + 10, env=env
        )
        out = result.stdout.decode("utf-8", errors="replace").strip()
        err = result.stderr.decode("utf-8", errors="replace").strip()
        print(f"[tempfile] rc={result.returncode}, {len(out)}chars")
        if err: print(f"  stderr: {err[:150]}")
        print(f"  out: {out[:300]}")
        return out if result.returncode == 0 else None
    except Exception as e:
        print(f"  exception: {e}")
        return None
    finally:
        os.unlink(tmp)

conn = sqlite3.connect("reviews.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
item = dict(cur.execute(
    "SELECT id, title, exam_type, grade, job_series, study_period, content FROM passnotes LIMIT 1"
).fetchone())
conn.close()

prompt = f"""아래 합격수기를 분류해서 JSON만 반환해. 설명 없이 JSON만.

제목: {item['title']}
시험: {item['exam_type']} {item['grade']} {item['job_series']}
수험기간: {item['study_period']}

내용:
{item['content'][:2000]}

{{
  "tags": ["태그1", "태그2"],
  "instructors": [{{"subject": "과목", "name": "강사명"}}],
  "textbooks": [{{"subject": "과목", "name": "교재명"}}]
}}"""

print(f"프롬프트 길이: {len(prompt)}자")
print("=" * 50)
print("방법1: stdin")
r1 = call_claude_stdin(prompt)
print()
print("방법2: tempfile+powershell")
r2 = call_claude_tempfile(prompt)
