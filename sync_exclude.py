# -*- coding: utf-8 -*-
"""
sync_exclude.py — 검수목록(강사교재_검수목록.md)을 단일 기준으로 강사 블랙리스트를 재도출.

원리: 원본 강사목록(reviews_data.json) − 문서에 '남긴' 강사 = 제외 대상.
  · 강사: 줄 이름 = 유지. 단 이름 앞 ❌ → 그 과목에서 제외.
  · 제거: 줄 이름 = 제외. 단 이름 앞 ✅ → 부활(유지).
  · 어느 과목에서든 한 번이라도 유지된 강사(=해커스 명단)는 전역 제외에서 보호.

실행: python sync_exclude.py  →  live/result_exclude.json 재작성 + build_result_stats.py 호출
"""
import json, re, os, subprocess, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
MD     = os.path.join(HERE, '강사교재_검수목록.md')
SRC    = os.path.join(HERE, 'live', 'reviews_data.json')
EXC    = os.path.join(HERE, 'live', 'result_exclude.json')
MANUAL = os.path.join(HERE, 'live', 'aliases_manual.json')  # 사용자 수동 별칭 (선택)

def parse_line(line):
    """'강사:'/'제거:' 뒤의 토큰들을 (mark, name) 목록으로. name = '(' 앞부분."""
    body = line.split(':', 1)[1] if ':' in line else line
    out = []
    for tok in body.split('/'):
        tok = tok.strip()
        if not tok:
            continue
        mark = ''
        if tok[:1] == '❌':
            mark, tok = '❌', tok[1:].strip()
        elif tok[:1] == '✅':
            mark, tok = '✅', tok[1:].strip()
        name = tok.split('(')[0].strip().rstrip('❌✅').strip()
        if name:
            out.append((mark, name))
    return out

def main():
    # 1) 원본 과목별 강사 집합 + 전역 강사 카운트 + 강사별 대표과목
    ps = json.load(open(SRC, encoding='utf-8'))['passnotes']
    orig = collections.defaultdict(set)
    inst_cnt = collections.Counter()
    inst_subj = collections.defaultdict(collections.Counter)   # 강사→과목별 카운트
    for p in ps:
        for pr in (p.get('inst') or []):
            if len(pr) == 2 and pr[0] and pr[1]:
                orig[pr[0]].add(pr[1])
                inst_cnt[pr[1]] += 1
                inst_subj[pr[1]][pr[0]] += 1
    def top_subj(n):
        return inst_subj[n].most_common(1)[0][0] if inst_subj[n] else None

    # 2) 문서 파싱 (❌=전역 강제제외 / ✅=전역 강제유지 — 다른 과목 표시보다 우선)
    kept_all, excl_all = set(), set()
    force_excl, force_keep = set(), set()
    cur = None
    for line in open(MD, encoding='utf-8'):
        s = line.strip()
        if s.startswith('## '):
            cur = s[3:].split('(언급')[0].strip()
            _subj_keep.setdefault(cur, set())
            _subj_excl.setdefault(cur, set())
        elif cur and s.startswith('강사:'):
            for mark, name in parse_line(s):
                if mark == '❌':
                    _subj_excl[cur].add(name); force_excl.add(name)
                else:
                    _subj_keep[cur].add(name)
        elif cur and s.startswith('제거:'):
            for mark, name in parse_line(s):
                if mark == '✅':
                    _subj_keep[cur].add(name); force_keep.add(name)
                else:
                    _subj_excl[cur].add(name)

    # 3) 과목별: 원본 − 유지 = 제외, 전역 유지명단으로 보호
    for subj in set(list(_subj_keep) + list(orig)):
        keep = _subj_keep.get(subj, set())
        excl = set(_subj_excl.get(subj, set()))
        for n in orig.get(subj, set()):
            if n not in keep:
                excl.add(n)
        kept_all |= keep
        excl_all |= excl
    kept_all -= force_excl                     # 강제제외는 보호 무효화
    kept_all |= force_keep
    # 수동 별칭(사용자 추가) — 별도 파일에서만 로드 (자동분과 분리해 freezing 방지)
    manual_alias = {}
    if os.path.exists(MANUAL):
        try:
            manual_alias = dict(json.load(open(MANUAL, encoding='utf-8')))
        except Exception:
            pass

    # 4) OCR 변형 → 실제 강사명 별칭 (정밀: 같은 성·같은 대표과목·한 글자 차이·진짜가 압도적)
    roster = sorted([n for n in kept_all if re.fullmatch(r'[가-힣]{2,5}', n)],
                    key=lambda n: -inst_cnt.get(n, 0))
    def hamming1(a, b):
        return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1
    auto = {}
    for v, cv in inst_cnt.items():
        if v in kept_all or not re.fullmatch(r'[가-힣]{2,5}', v) or cv > 5:
            continue
        for c in roster:                       # 카운트 내림차순 → 가장 흔한 실제 이름 우선
            if (v[0] == c[0] and hamming1(v, c)
                    and top_subj(v) == top_subj(c)
                    and inst_cnt[c] >= 10 and inst_cnt[c] >= 5 * cv):
                auto[v] = c
                break
    aliases = {**auto, **manual_alias}         # 수동 별칭 우선
    for n in force_excl:                        # 강제제외는 별칭보다 우선(병합하지 않고 제외)
        aliases.pop(n, None)
    blacklist = sorted((((excl_all - kept_all) | force_excl) - force_keep) - set(aliases))

    data = {'instructors': blacklist, 'subjects': [], 'aliases': aliases}
    json.dump(data, open(EXC, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"해커스 유지 {len(kept_all)}명 / 블랙리스트 {len(blacklist)}명 / 별칭 {len(aliases)}개(자동 {len(auto)})")

    subprocess.run([sys.executable, os.path.join(HERE, 'build_result_stats.py')], check=True)

_subj_keep, _subj_excl = {}, {}

if __name__ == '__main__':
    main()
