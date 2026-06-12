"""
police_reviews.json 분리
  ① 필기합격 → police_필기합격.json
  ② 최종합격 → police_최종합격.json
  ③ 응시연도 2023년 이후 → police_2023이후.json
경찰은 응시연도("2026년")가 전건 채워져 있음 → 그대로 int 변환.
"""
import json, re

SRC = "police_reviews.json"

def exam_year(x):
    y = (x["summary"].get("응시연도") or "")
    m = re.search(r"(20\d\d)", y)
    if m:
        return int(m.group(1))
    m = re.search(r"(20\d\d)", x["title"])
    return int(m.group(1)) if m else None

def cat(x):
    return x["summary"].get("카테고리", "")

def dump(name, items):
    json.dump(items, open(name, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  {name}: {len(items)}개")

def main():
    data = json.load(open(SRC, encoding="utf-8"))
    for x in data:
        x["exam_year"] = exam_year(x)

    final   = [x for x in data if "최종" in cat(x)]
    written = [x for x in data if "필기" in cat(x)]
    y2023   = [x for x in data if x["exam_year"] and x["exam_year"] >= 2023]

    print(f"전체 {len(data)}개 분리:")
    dump("police_최종합격.json", final)
    dump("police_필기합격.json", written)
    dump("police_2023이후.json", y2023)
    dump(SRC, data)  # exam_year 부여본 갱신

    fy = sum(1 for x in final if x["exam_year"] and x["exam_year"] >= 2023)
    miss = sum(1 for x in data if x["exam_year"] is None)
    print(f"\n참고: 최종합격 ∩ 2023이후 = {fy}개 | 응시연도 미상 = {miss}개")

if __name__ == "__main__":
    main()
