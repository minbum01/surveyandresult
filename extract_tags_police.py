"""
경찰 합격수기 태그 추출 (extract_tags.py 의 경찰판)
- 대상 DB: police_reviews.db (공무원 reviews.db 와 분리)
- claude CLI -p 호출로 수기 1건씩 tags/instructors/textbooks 추출
- 100건마다 태그 정규화, keywords_extracted 로 이어받기
사용:
  python extract_tags_fire.py            # 전체 미처리 실행
  python extract_tags_fire.py test 3     # 앞 3건만 시험 실행(저장함)
"""
import sqlite3, subprocess, json, time, logging, re, os, sys
from datetime import datetime

DB_FILE = "police_reviews.db"
LOG_FILE = "extract_tags_police.log"
NORMALIZE_EVERY = 100
TIMEOUT = 90            # 수기 1건 태그 추출 타임아웃
NORM_TIMEOUT = 240      # 정규화는 태그 목록 전체를 처리 → 더 길게
CONTENT_LIMIT = 12000   # 본문 사용 길이(자). 소방 최대 12,104자 → 사실상 무손실

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger()

import shutil as _shutil
CLAUDE_CMD = (_shutil.which("claude") or _shutil.which("claude.cmd")
             or r"C:\Users\admin\AppData\Roaming\npm\claude.cmd")

def call_claude(prompt: str, timeout: int = TIMEOUT):
    try:
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env.pop("CLAUDE_CODE", None)
        proc = subprocess.Popen(
            [CLAUDE_CMD, "--dangerously-skip-permissions", "-p", "-"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
        stdout, stderr = proc.communicate(input=prompt.encode("utf-8"), timeout=timeout)
        if proc.returncode == 0:
            return stdout.decode("utf-8", "replace").strip()
        log.warning(f"  claude 오류(code={proc.returncode}): {stderr.decode('utf-8','replace')[:200]}")
        return None
    except subprocess.TimeoutExpired:
        proc.kill(); log.warning("  타임아웃"); return None
    except Exception as e:
        log.error(f"  claude CLI 오류: {e}"); return None

def parse_json(text: str):
    try:
        text = re.sub(r"```(?:json)?", "", text).strip("` \n")
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
    except:
        pass
    return None

def get_existing_tags(cur):
    return [r[0] for r in cur.execute("SELECT name FROM tags ORDER BY count DESC").fetchall()]

def extract_tags(item, existing_tags):
    tags_str = ", ".join(existing_tags) if existing_tags else "없음 (첫 번째 수기)"
    prompt = f"""다음 경찰공무원 합격수기를 읽고 JSON만 반환해줘. 설명 없이 JSON만.

[규칙]
1. tags: 이 사람을 설명하는 키워드 자유롭게 추출
   - 생활상황/나이대/수험이력/공부법/루틴/멘탈관리 등 모든 특징
   - 개수 제한 없음
   - 기존 태그 목록에 같거나 비슷한 게 있으면 반드시 기존 것 사용
   - 진짜 새로운 의미일 때만 새 태그 생성
   - 태그는 간결하게 (2~6글자 권장)

2. instructors: 언급된 강사
   - 성+이름 풀네임 (쌤/T/선생님 제거)
   - 과목: 헌법/형사법/형법/형사소송법/경찰학/경찰행정법/영어/한국사/면접 등

3. textbooks: 언급된 교재/문제집/강의명

[기존 태그 목록]
{tags_str}

[합격수기]
제목: {item['title']}
응시시험: {item['exam_type']} {item['job_series']} ({item['category']})
응시지역: {item['region']} | 수험기간: {item['study_period']}

{item['content'][:CONTENT_LIMIT]}

[출력 - JSON만]
{{
  "tags": ["태그1", "태그2"],
  "instructors": [{{"subject": "과목", "name": "강사명"}}],
  "textbooks": [{{"subject": "과목", "name": "교재명"}}]
}}"""
    resp = call_claude(prompt)
    return parse_json(resp) if resp else None

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
  {{"keep": "대표태그", "remove": ["제거할태그1", "제거할태그2"]}}
]"""
    resp = call_claude(prompt, timeout=NORM_TIMEOUT)
    result = parse_json(resp) if resp else None
    if not isinstance(result, list):
        log.info("  [정규화] 건너뜀"); return
    merged = 0
    for it in result:
        keep = (it.get("keep") or "").strip(); remove = it.get("remove", [])
        if not keep or not remove:
            continue
        cur.execute("INSERT OR IGNORE INTO tags (name, count) VALUES (?, 0)", (keep,))
        kr = cur.execute("SELECT id FROM tags WHERE name = ?", (keep,)).fetchone()
        if not kr:
            continue
        keep_id = kr[0]
        for old in remove:
            orow = cur.execute("SELECT id FROM tags WHERE name = ?", (old,)).fetchone()
            if not orow:
                continue
            oid = orow[0]
            cur.execute("INSERT OR IGNORE INTO passnote_tags (passnote_id, tag_id) "
                        "SELECT passnote_id, ? FROM passnote_tags WHERE tag_id = ?", (keep_id, oid))
            cur.execute("DELETE FROM passnote_tags WHERE tag_id = ?", (oid,))
            cur.execute("DELETE FROM tags WHERE id = ?", (oid,))
            merged += 1
    cur.execute("UPDATE tags SET count = 0")
    cur.execute("UPDATE tags SET count = (SELECT COUNT(*) FROM passnote_tags WHERE tag_id = tags.id)")
    conn.commit()
    log.info(f"  [정규화] 완료 - {merged}개 통합")

def main(limit=None):
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    q = "SELECT id, title, exam_type, job_series, category, region, study_period, content " \
        "FROM passnotes WHERE keywords_extracted = 0 ORDER BY id"
    if limit:
        q += f" LIMIT {int(limit)}"
    pending = cur.execute(q).fetchall()
    total = len(pending)
    done0 = cur.execute("SELECT COUNT(*) FROM passnotes WHERE keywords_extracted = 1").fetchone()[0]
    log.info("=== 경찰 태그 추출 시작 ===")
    log.info(f"미처리: {total}개 | 이미완료: {done0}개 | 예상 ~{total*10//60}분")
    log.info("=" * 40)

    MAX_CONSEC_FAIL = 8   # 연속 실패(사용량 한도 추정) 시 깔끔히 중단 → 한도 풀린 뒤 재실행으로 이어받기
    consec_fail = 0

    for i, item in enumerate(pending, 1):
        item = dict(item)
        log.info(f"[{i}/{total}] {item['title'][:45]}...")
        result = extract_tags(item, get_existing_tags(cur))
        if not result:
            consec_fail += 1
            log.warning(f"  실패 - 건너뜀 (연속 {consec_fail})")
            if consec_fail >= MAX_CONSEC_FAIL:
                log.error(f"  연속 {consec_fail}회 실패 → 사용량 한도 추정, 중단합니다. "
                          f"한도 회복 후 다시 실행하면 이어집니다.")
                break
            continue
        consec_fail = 0
        tags = result.get("tags", [])
        for t in tags:
            t = (t or "").strip()
            if not t:
                continue
            cur.execute("INSERT OR IGNORE INTO tags (name, count) VALUES (?, 0)", (t,))
            tid = cur.execute("SELECT id FROM tags WHERE name = ?", (t,)).fetchone()[0]
            cur.execute("INSERT OR IGNORE INTO passnote_tags (passnote_id, tag_id) VALUES (?, ?)", (item["id"], tid))
            cur.execute("UPDATE tags SET count = count + 1 WHERE id = ?", (tid,))
        for ins in result.get("instructors", []):
            if ins.get("subject") and ins.get("name"):
                cur.execute("INSERT INTO instructors (passnote_id, subject, name) VALUES (?,?,?)",
                            (item["id"], ins["subject"].strip(), ins["name"].strip()))
        for tb in result.get("textbooks", []):
            if tb.get("subject") and tb.get("name"):
                cur.execute("INSERT INTO textbooks (passnote_id, subject, name) VALUES (?,?,?)",
                            (item["id"], tb["subject"].strip(), tb["name"].strip()))
        cur.execute("UPDATE passnotes SET keywords_extracted = 1 WHERE id = ?", (item["id"],))
        conn.commit()
        tc = cur.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
        log.info(f"  태그 {len(tags)}개 | 누적 태그종류 {tc}개")
        if i % NORMALIZE_EVERY == 0:
            normalize_tags(conn, cur)
            log.info(f"  진행률 {i/total*100:.1f}%")

    log.info("\n=== 최종 정규화 ===")
    normalize_tags(conn, cur)
    tt = cur.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    ti = cur.execute("SELECT COUNT(DISTINCT name) FROM instructors").fetchone()[0]
    tx = cur.execute("SELECT COUNT(DISTINCT name) FROM textbooks").fetchone()[0]
    done = cur.execute("SELECT COUNT(*) FROM passnotes WHERE keywords_extracted = 1").fetchone()[0]
    log.info(f"\n=== 완료 === 처리 {done}개 | 태그 {tt}종 | 강사 {ti}명 | 교재 {tx}종")
    log.info("\n── 상위 태그 20 ──")
    for r in cur.execute("SELECT name, count FROM tags ORDER BY count DESC LIMIT 20"):
        log.info(f"  {r[0]:20}: {r[1]}")
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "test":
        main(limit=int(sys.argv[2]) if len(sys.argv) > 2 else 3)
    else:
        main()
