"""
태깅 자동재개 러너
- extract_tags.py 를 반복 실행. 중단/오류/사용량한도로 죽어도 알아서 재시작.
- 재시작해도 extract_tags 가 keywords_extracted=0 인 글만 처리(이어받기).
- 남은 대기(pending)=0 이면 종료.
- 진전이 없으면(한도 등) 더 길게 쉬었다 재시도.
- 로그: run_tagging.log
사용:  python run_tagging.py
중지:  이 프로세스(또는 창) 종료
"""
import subprocess, sqlite3, time, sys, os, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "reviews.db")
LOG = os.path.join(ROOT, "run_tagging.log")
PY = sys.executable

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg):
    line = f"{datetime.datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def pending():
    c = sqlite3.connect(DB)
    try:
        return c.execute("SELECT COUNT(*) FROM passnotes WHERE keywords_extracted=0").fetchone()[0]
    finally:
        c.close()


def main():
    stale_rounds = 0
    round_no = 0
    log("===== run_tagging 시작 =====")
    while True:
        p = pending()
        if p == 0:
            log("✅ 모든 태깅 완료 — 종료")
            break
        round_no += 1
        log(f"[round {round_no}] 남은 {p}건 → extract_tags.py 실행")
        try:
            rc = subprocess.run([PY, "extract_tags.py"], cwd=ROOT).returncode
        except KeyboardInterrupt:
            log("사용자 중단(Ctrl+C) — 종료. 재실행하면 이어서 진행됩니다.")
            break
        except Exception as e:
            rc = -1
            log(f"extract_tags 실행 예외: {e}")

        after = pending()
        done = p - after
        log(f"[round {round_no}] extract_tags 종료(rc={rc}) · 이번 처리 {done}건 · 남은 {after}건")

        if after == 0:
            log("✅ 모든 태깅 완료 — 종료")
            break

        if done <= 0:
            stale_rounds += 1
            wait = min(120 * stale_rounds, 1800)   # 진전 없으면 2분→점점 늘려 최대 30분
            log(f"⚠ 진전 없음(한도/오류 추정). {wait}s 쉬었다 재시도 (연속 {stale_rounds}회)")
        else:
            stale_rounds = 0
            wait = 5
            log(f"{wait}s 후 다음 배치")
        time.sleep(wait)


if __name__ == "__main__":
    main()
