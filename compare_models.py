"""
태그 추출 모델 비교: 같은 경찰 수기 N건을 Opus vs Sonnet 으로 돌려 태그 비교.
사용: python compare_models.py [건수=3]
"""
import sqlite3, subprocess, json, re, os, sys, time

CLAUDE_CMD = r"C:\Users\admin\AppData\Roaming\npm\claude.cmd"
MODEL_A = "claude-opus-4-8"
MODEL_B = "claude-sonnet-4-6"

def call(prompt, model):
    env = os.environ.copy()
    env.pop("CLAUDECODE", None); env.pop("CLAUDE_CODE", None)
    cmd = [CLAUDE_CMD, "--dangerously-skip-permissions", "--model", model, "-p", "-"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    t0 = time.time()
    out, err = p.communicate(input=prompt.encode("utf-8"), timeout=120)
    elapsed = time.time() - t0
    if p.returncode != 0:
        return None, err.decode("utf-8", "replace")[:200], elapsed
    return out.decode("utf-8", "replace").strip(), None, elapsed

def parse_json(t):
    try:
        t = re.sub(r"```(?:json)?", "", t).strip("` \n")
        m = re.search(r"(\{.*\}|\[.*\])", t, re.DOTALL)
        return json.loads(m.group(1)) if m else None
    except:
        return None

def build_prompt(item):
    return f"""다음 경찰공무원 합격수기를 읽고 JSON만 반환해줘. 설명 없이 JSON만.

[규칙]
1. tags: 생활상황/나이대/수험이력/공부법/루틴/멘탈관리 등 모든 특징, 간결하게(2~6글자), 개수제한 없음
2. instructors: 언급된 강사 (풀네임, 과목: 헌법/형사법/경찰학/영어/한국사 등)
3. textbooks: 언급된 교재/강의명

[합격수기]
제목: {item['title']}
{item['content'][:12000]}

[출력 - JSON만]
{{"tags":["..."],"instructors":[{{"subject":"","name":""}}],"textbooks":[{{"subject":"","name":""}}]}}"""

def fmt_list(lst, indent="    "):
    if not lst: return f"{indent}(없음)"
    return "\n".join(f"{indent}- {x}" for x in lst)

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    c = sqlite3.connect("police_reviews.db"); c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT title, content FROM passnotes WHERE category LIKE '%최종%' "
        "AND LENGTH(content) > 1500 ORDER BY id LIMIT ?", (n,)
    ).fetchall()

    print(f"\n{'='*70}")
    print(f"  모델 비교: {MODEL_A}  vs  {MODEL_B}")
    print(f"  대상: 경찰 최종합격 수기 {len(rows)}건 (본문 1,500자 이상)")
    print(f"{'='*70}\n")

    for i, item in enumerate(rows, 1):
        item = dict(item)
        content_len = len(item['content'])
        print(f"[{i}/{len(rows)}] {item['title']}")
        print(f"  본문 {content_len:,}자\n")
        prompt = build_prompt(item)

        print(f"  ⏳ Opus 호출 중...")
        ra, ea, ta_sec = call(prompt, MODEL_A)
        print(f"  ⏳ Sonnet 호출 중...")
        rb, eb, tb_sec = call(prompt, MODEL_B)

        ja = parse_json(ra or "")
        jb = parse_json(rb or "")

        tags_a = ja.get("tags", []) if ja else [f"실패: {ea}"]
        tags_b = jb.get("tags", []) if jb else [f"실패: {eb}"]
        ins_a  = [f"{x.get('subject','?')}:{x.get('name','?')}" for x in (ja.get("instructors", []) if ja else [])]
        ins_b  = [f"{x.get('subject','?')}:{x.get('name','?')}" for x in (jb.get("instructors", []) if jb else [])]
        tb_a   = [f"{x.get('subject','?')}:{x.get('name','?')}" for x in (ja.get("textbooks", []) if ja else [])]
        tb_b   = [f"{x.get('subject','?')}:{x.get('name','?')}" for x in (jb.get("textbooks", []) if jb else [])]

        only_a = set(tags_a) - set(tags_b)
        only_b = set(tags_b) - set(tags_a)
        common = set(tags_a) & set(tags_b)

        print(f"  ── Opus ({ta_sec:.1f}s) ─── 태그 {len(tags_a)}개")
        print(fmt_list(sorted(tags_a)))
        print(f"\n  ── Sonnet ({tb_sec:.1f}s) ─ 태그 {len(tags_b)}개")
        print(fmt_list(sorted(tags_b)))

        print(f"\n  ── 차이 분석 ──")
        print(f"  공통 {len(common)}개 | Opus만 {len(only_a)}개 | Sonnet만 {len(only_b)}개")
        if only_a: print(f"  Opus만:   {', '.join(sorted(only_a))}")
        if only_b: print(f"  Sonnet만: {', '.join(sorted(only_b))}")

        print(f"\n  강사 Opus:   {ins_a or '없음'}")
        print(f"  강사 Sonnet: {ins_b or '없음'}")
        print(f"  교재 Opus:   {tb_a or '없음'}")
        print(f"  교재 Sonnet: {tb_b or '없음'}")
        print(f"\n{'─'*70}\n")

if __name__ == "__main__":
    main()
