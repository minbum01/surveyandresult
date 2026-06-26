# -*- coding: utf-8 -*-
"""
regen_review_md.py — 강사교재_검수목록.md 를 데이터+현재 큐레이션 기준으로 재생성(정규화).

  · 과목은 subject_canon.json 기준 대표과목으로 병합
  · 강사는 result_exclude.json 의 aliases 로 OCR 변형 병합
  · blacklist(instructors) 는 '제거:' 줄로, 나머지는 '강사:' 줄로
  · 교재 TOP5 동봉

⚠ 실행 전 반드시 sync_exclude.py 를 먼저 돌려 현재 문서의 ❌/✅ 마크를
   result_exclude.json 에 반영해 둘 것. (이 스크립트는 exclude.json 을 기준으로 문서를 다시 그림)
"""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, 'live', 'reviews_data.json')
EXC  = os.path.join(HERE, 'live', 'result_exclude.json')
SC   = os.path.join(HERE, 'live', 'subject_canon.json')
MD   = os.path.join(HERE, '강사교재_검수목록.md')

MIN_SUBJECT = 5    # 이 미만 언급 과목은 문서에서 숨김(간소화). 카드엔 영향 없음.

def is_junk(name):
    # OCR 쓰레기(Latin OO·자모단독·기호·한자리)는 숨겨 가독성↑. 순수 한글 2~5자만 통과.
    return not re.fullmatch(r'[가-힣]{2,5}', name)

def main():
    ps = json.load(open(SRC, encoding='utf-8'))['passnotes']
    exc = json.load(open(EXC, encoding='utf-8')) if os.path.exists(EXC) else {}
    black = set(exc.get('instructors') or [])
    excl_subj = set(exc.get('subjects') or [])
    alias = dict(exc.get('aliases') or {})
    canon = dict(json.load(open(SC, encoding='utf-8'))) if os.path.exists(SC) else {}
    csubj = lambda s: canon.get(s, s)
    cinst = lambda n: alias.get(n, n)

    subj_inst = collections.defaultdict(collections.Counter)
    subj_book = collections.defaultdict(collections.Counter)
    subj_total = collections.Counter()
    for p in ps:
        for pr in (p.get('inst') or []):
            if len(pr) == 2 and pr[0] and pr[1]:
                s, n = csubj(pr[0]), cinst(pr[1])
                subj_inst[s][n] += 1
                subj_total[s] += 1
        for pr in (p.get('book') or []):
            if len(pr) == 2 and pr[0] and pr[1]:
                subj_book[csubj(pr[0])][pr[1]] += 1

    shown = [(s, subj_total[s]) for s, _ in subj_total.most_common()
             if s not in excl_subj and subj_total[s] >= MIN_SUBJECT]
    hidden = len(subj_total) - len(shown) - len(excl_subj & set(subj_total))

    out = []
    out.append('# 강사·과목·교재 검수 목록 (과목 병합본)')
    out.append('')
    out.append(f'- 과목 {len(shown)}종 표시 (언급 {MIN_SUBJECT}회 미만 {hidden}종 숨김 · 제외과목 {len(excl_subj)}종)')
    out.append('- 마킹: 강사 빼기=강사줄 이름 앞 ❌ · 잘못 뺀 강사 살리기=제거줄 이름 앞 ✅')
    out.append('- 과목 통째 빼기/OCR병합은 `live/curation_manual.json`·`aliases_manual.json` 편집')
    out.append('- 반영: `python sync_exclude.py && python regen_review_md.py`')
    out.append('')

    for s, tot in shown:
        insts = subj_inst[s].most_common()
        keep = [(n, c) for n, c in insts if n not in black and not is_junk(n)]   # 쓰레기 숨김
        rem  = [(n, c) for n, c in insts if n in black and not is_junk(n)]
        out.append(f'## {s}  (언급 {tot})')
        out.append('강사: ' + (' / '.join(f'{n}({c})' for n, c in keep) if keep else '—'))
        if rem:
            out.append('제거: ' + ' / '.join(f'{n}({c})' for n, c in rem) + '  ❌')
        bks = subj_book[s].most_common(5)
        if bks:
            out.append('교재 TOP5: ' + ' / '.join(f'{b}({c})' for b, c in bks))
        out.append('')

    open(MD, 'w', encoding='utf-8').write('\n'.join(out))
    print(f'재생성: 표시 {len(shown)}종 / 숨김 {hidden}종 / 제외 {len(excl_subj)}종')

if __name__ == '__main__':
    main()
