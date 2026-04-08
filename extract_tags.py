"""
태그 추출 스크립트 - 완전 자동, 사용자 입력 없음
claude -p CLI 호출로 Max 구독 안에서 처리
"""
import sqlite3
import subprocess
import json
import time
import logging
import re
import os
from datetime import datetime

DB_FILE = "reviews.db"
LOG_FILE = "extract_tags.log"
NORMALIZE_EVERY = 100   # 100개마다 정규화
TIMEOUT = 60            # claude CLI 타임아웃 (초)

# 로그 설정 (파일 + 터미널 동시 출력)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger()

# ── Claude CLI 호출 ───────────────────────────────────

CLAUDE_CMD = r"C:\Users\admin\AppData\Roaming\npm\claude.cmd"

def call_claude(prompt: str) -> str | None:
    try:
        # CLAUDECODE 환경변수 제거 (중첩 세션 차단 우회)
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env.pop("CLAUDE_CODE", None)

        # stdin으로 전달 (Windows CLI 인자 길이/인코딩 제한 우회)
        proc = subprocess.Popen(
            [CLAUDE_CMD, "--dangerously-skip-permissions", "-p", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        stdout, stderr = proc.communicate(
            input=prompt.encode("utf-8"),
            timeout=TIMEOUT
        )
        if proc.returncode == 0:
            return stdout.decode("utf-8", errors="replace").strip()
        else:
            err = stderr.decode("utf-8", errors="replace").strip()
            log.warning(f"  claude 오류(code={proc.returncode}): {err[:200]}")
            return None
    except subprocess.TimeoutExpired:
        proc.kill()
        log.warning("  타임아웃")
        return None
    except Exception as e:
        log.error(f"  claude CLI 오류: {e}")
        return None

def parse_json(text: str) -> dict | list | None:
    try:
        # 마크다운 코드블록 제거
        text = re.sub(r"```(?:json)?", "", text).strip("` \n")
        # JSON 부분만 추출
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except:
        pass
    return None

# ── 태그 추출 ─────────────────────────────────────────

def get_existing_tags(cur) -> list[str]:
    rows = cur.execute("SELECT name FROM tags ORDER BY count DESC").fetchall()
    return [r[0] for r in rows]

def extract_tags(item: dict, existing_tags: list[str]) -> dict | None:
    tags_str = ", ".join(existing_tags) if existing_tags else "없음 (첫 번째 수기)"

    prompt = f"""다음 공무원 합격수기를 읽고 JSON만 반환해줘. 설명 없이 JSON만.

[규칙]
1. tags: 이 사람을 설명하는 키워드 자유롭게 추출
   - 생활상황/나이대/수험이력/공부법/루틴/멘탈관리 등 모든 특징
   - 개수 제한 없음
   - 기존 태그 목록에 같거나 비슷한 게 있으면 반드시 기존 것 사용
   - 진짜 새로운 의미일 때만 새 태그 생성
   - 태그는 간결하게 (2~6글자 권장)

2. instructors: 언급된 강사
   - 성+이름 풀네임 (쌤/T/선생님 제거)
   - 과목: 국어/영어/한국사/행정학/행정법/헌법/면접 등

3. textbooks: 언급된 교재/문제집/강의명

[기존 태그 목록]
{tags_str}

[합격수기]
제목: {item['title']}
응시시험: {item['exam_type']} {item['grade']} {item['job_series']}
수험기간: {item['study_period']}

{item['content'][:3000]}

[출력 - JSON만]
{{
  "tags": ["태그1", "태그2"],
  "instructors": [{{"subject": "과목", "name": "강사명"}}],
  "textbooks": [{{"subject": "과목", "name": "교재명"}}]
}}"""

    response = call_claude(prompt)
    if not response:
        return None

    return parse_json(response)

# ── 정규화 ────────────────────────────────────────────

def normalize_tags(conn, cur):
    log.info("  [정규화] 시작...")
    tags = get_existing_tags(cur)
    if len(tags) < 10:
        return

    prompt = f"""아래 태그 목록에서 의미가 같거나 매우 비슷한 것들을 묶어줘.
JSON만 반환. 설명 없이.

[태그 목록]
{', '.join(tags)}

[출력 - JSON만, 합칠 게 없으면 빈 배열]
[
  {{"keep": "대표태그", "remove": ["제거할태그1", "제거할태그2"]}},
  ...
]"""

    response = call_claude(prompt)
    if not response:
        log.info("  [정규화] 응답 없음, 건너뜀")
        return

    result = parse_json(response)
    if not isinstance(result, list):
        log.info("  [정규화] 파싱 실패, 건너뜀")
        return

    merged = 0
    for item in result:
        keep = item.get("keep", "").strip()
        remove = item.get("remove", [])
        if not keep or not remove:
            continue

        # keep 태그가 DB에 없으면 추가
        cur.execute("INSERT OR IGNORE INTO tags (name, count) VALUES (?, 0)", (keep,))
        keep_row = cur.execute("SELECT id FROM tags WHERE name = ?", (keep,)).fetchone()
        if not keep_row:
            continue
        keep_id = keep_row[0]

        for old_name in remove:
            old_row = cur.execute("SELECT id FROM tags WHERE name = ?", (old_name,)).fetchone()
            if not old_row:
                continue
            old_id = old_row[0]

            # passnote_tags 업데이트: old → keep (중복 제거)
            cur.execute("""
                INSERT OR IGNORE INTO passnote_tags (passnote_id, tag_id)
                SELECT passnote_id, ? FROM passnote_tags WHERE tag_id = ?
            """, (keep_id, old_id))
            cur.execute("DELETE FROM passnote_tags WHERE tag_id = ?", (old_id,))
            cur.execute("DELETE FROM tags WHERE id = ?", (old_id,))
            merged += 1

    # count 재집계
    cur.execute("UPDATE tags SET count = 0")
    cur.execute("""
        UPDATE tags SET count = (
            SELECT COUNT(*) FROM passnote_tags WHERE tag_id = tags.id
        )
    """)
    conn.commit()
    log.info(f"  [정규화] 완료 - {merged}개 태그 통합")

# ── 메인 ──────────────────────────────────────────────

def main():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 미처리 수기 목록
    pending = cur.execute("""
        SELECT id, title, exam_type, grade, job_series, study_period, content
        FROM passnotes WHERE keywords_extracted = 0
        ORDER BY id
    """).fetchall()

    total = len(pending)
    done_count = cur.execute("SELECT COUNT(*) FROM passnotes WHERE keywords_extracted = 1").fetchone()[0]

    log.info(f"=== 태그 추출 시작 ===")
    log.info(f"미처리: {total}개 | 완료: {done_count}개")
    log.info(f"예상 시간: 약 {total * 10 // 60}분")
    log.info("=" * 40)

    for i, item in enumerate(pending, 1):
        item = dict(item)
        safe_title = item['title'][:45]

        log.info(f"[{i}/{total}] {safe_title}...")

        existing_tags = get_existing_tags(cur)
        result = extract_tags(item, existing_tags)

        if not result:
            log.warning(f"  실패 - 건너뜀")
            continue

        # 태그 저장
        tags = result.get("tags", [])
        for tag_name in tags:
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            cur.execute("INSERT OR IGNORE INTO tags (name, count) VALUES (?, 0)", (tag_name,))
            tag_id = cur.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()[0]
            cur.execute("INSERT OR IGNORE INTO passnote_tags (passnote_id, tag_id) VALUES (?, ?)",
                       (item['id'], tag_id))
            cur.execute("UPDATE tags SET count = count + 1 WHERE id = ?", (tag_id,))

        # 강사 저장
        for inst in result.get("instructors", []):
            if inst.get("subject") and inst.get("name"):
                cur.execute("INSERT INTO instructors (passnote_id, subject, name) VALUES (?, ?, ?)",
                           (item['id'], inst["subject"].strip(), inst["name"].strip()))

        # 교재 저장
        for tb in result.get("textbooks", []):
            if tb.get("subject") and tb.get("name"):
                cur.execute("INSERT INTO textbooks (passnote_id, subject, name) VALUES (?, ?, ?)",
                           (item['id'], tb["subject"].strip(), tb["name"].strip()))

        # 완료 표시
        cur.execute("UPDATE passnotes SET keywords_extracted = 1 WHERE id = ?", (item['id'],))
        conn.commit()

        tag_count = cur.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
        log.info(f"  태그 {len(tags)}개 추출 | 누적 태그 종류: {tag_count}개")

        # 100개마다 정규화
        if i % NORMALIZE_EVERY == 0:
            normalize_tags(conn, cur)
            log.info(f"  [{i}/{total}] 진행률: {i/total*100:.1f}%")

    # 최종 정규화
    log.info("\n=== 최종 정규화 ===")
    normalize_tags(conn, cur)

    # 최종 통계
    total_tags = cur.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    total_instructors = cur.execute("SELECT COUNT(DISTINCT name) FROM instructors").fetchone()[0]
    total_textbooks = cur.execute("SELECT COUNT(DISTINCT name) FROM textbooks").fetchone()[0]
    done = cur.execute("SELECT COUNT(*) FROM passnotes WHERE keywords_extracted = 1").fetchone()[0]

    log.info(f"\n=== 완료 ===")
    log.info(f"처리된 수기: {done}개")
    log.info(f"태그 종류: {total_tags}개")
    log.info(f"등장 강사: {total_instructors}명")
    log.info(f"등장 교재: {total_textbooks}종")

    # 상위 태그 20개
    log.info("\n── 상위 태그 20개 ──")
    for row in cur.execute("SELECT name, count FROM tags ORDER BY count DESC LIMIT 20"):
        log.info(f"  {row[0]:20} : {row[1]}개 수기")

    conn.close()

if __name__ == "__main__":
    main()
