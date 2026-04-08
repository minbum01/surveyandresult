"""
실제 수기로 claude 응답 디버깅
"""
import sqlite3, subprocess, os, re, json

CLAUDE_CMD = r"C:\Users\admin\AppData\Roaming\npm\claude.cmd"
TIMEOUT = 60

def call_claude(prompt):
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE", None)
    result = subprocess.run(
        [CLAUDE_CMD, "-p", prompt],
        capture_output=True, timeout=TIMEOUT, shell=False, env=env
    )
    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    print(f"returncode: {result.returncode}")
    print(f"stderr: {stderr[:200]}")
    print(f"stdout ({len(stdout)}chars): {stdout[:500]}")
    return stdout if result.returncode == 0 else None

conn = sqlite3.connect("reviews.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
item = dict(cur.execute(
    "SELECT id, title, exam_type, grade, job_series, study_period, content FROM passnotes LIMIT 1"
).fetchone())
conn.close()

print(f"수기: {item['title'][:60]}")
print("=" * 60)

prompt = f"""다음 공무원 합격수기를 읽고 JSON만 반환해줘. 설명 없이 JSON만.

[규칙]
1. tags: 이 사람을 설명하는 키워드 2~5개
2. instructors: 언급된 강사 (없으면 빈 배열)
3. textbooks: 언급된 교재 (없으면 빈 배열)

[합격수기]
제목: {item['title']}
응시시험: {item['exam_type']} {item['grade']} {item['job_series']}
수험기간: {item['study_period']}

{item['content'][:1000]}

[출력 - JSON만]
{{
  "tags": ["태그1", "태그2"],
  "instructors": [{{"subject": "과목", "name": "강사명"}}],
  "textbooks": [{{"subject": "과목", "name": "교재명"}}]
}}"""

response = call_claude(prompt)
print("\n파싱 시도:")
if response:
    text = re.sub(r"```(?:json)?", "", response).strip("` \n")
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            print(f"파싱 성공: {data}")
        except Exception as e:
            print(f"파싱 실패: {e}")
            print(f"매치된 텍스트: {match.group(1)[:200]}")
    else:
        print("JSON 패턴 없음")
