"""
실제 수기로 --dangerously-skip-permissions 테스트
"""
import sqlite3, subprocess, os, re, json

CLAUDE_CMD = r"C:\Users\admin\AppData\Roaming\npm\claude.cmd"
TIMEOUT = 60

def call_claude(prompt):
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE", None)
    result = subprocess.run(
        [CLAUDE_CMD, "--dangerously-skip-permissions", "-p", prompt],
        capture_output=True, timeout=TIMEOUT, shell=False, env=env
    )
    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    print(f"returncode: {result.returncode}")
    if stderr:
        print(f"stderr: {stderr[:200]}")
    print(f"stdout ({len(stdout)}chars):\n{stdout[:600]}")
    return stdout if result.returncode == 0 else None

conn = sqlite3.connect("reviews.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
item = dict(cur.execute(
    "SELECT id, title, exam_type, grade, job_series, study_period, content FROM passnotes LIMIT 1"
).fetchone())
conn.close()

prompt = f"""아래 텍스트를 분류해서 JSON만 반환해. 설명 없이 JSON만. 파일이나 도구 사용 금지.

제목: {item['title']}
시험: {item['exam_type']} {item['grade']} {item['job_series']}
수험기간: {item['study_period']}

내용:
{item['content'][:1500]}

위 텍스트에서 추출:
{{
  "tags": ["태그1", "태그2"],
  "instructors": [{{"subject": "과목", "name": "강사명"}}],
  "textbooks": [{{"subject": "과목", "name": "교재명"}}]
}}"""

response = call_claude(prompt)
print("\n--- 파싱 ---")
if response:
    text = re.sub(r"```(?:json)?", "", response).strip("` \n")
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            print(f"성공: tags={data.get('tags', [])[:3]}")
        except Exception as e:
            print(f"JSON 파싱 실패: {e}")
    else:
        print("JSON 없음")
