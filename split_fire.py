"""
fire_reviews.json 분리
  ① 필기합격  → fire_필기합격.json
  ② 최종합격  → fire_최종합격.json
  ③ 응시연도 2023년 이후 → fire_2023이후.json
각 레코드에 정규화 연도 'exam_year'(응시연도 필드 우선, 없으면 제목에서 20XX 추출) 부여.
"""
import json, re

SRC = "fire_reviews.json"

def exam_year(x):
    y = (x["summary"].get("응시연도") or "").strip()
    if y.isdigit():
        return int(y)
    m = re.search(r"(20\d\d)", x["title"])
    if m:
        return int(m.group(1))
    return None  # 미상

def is_final(x):
    return "최종" in x["summary"].get("구분", "")

def is_written(x):
    return "필기" in x["summary"].get("구분", "")

def dump(name, items):
    with open(name, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"  {name}: {len(items)}개")

def main():
    data = json.load(open(SRC, encoding="utf-8"))
    for x in data:
        x["exam_year"] = exam_year(x)  # 정규화 연도(없으면 None)

    final  = [x for x in data if is_final(x)]
    written = [x for x in data if is_written(x)]
    y2023  = [x for x in data if x["exam_year"] is not None and x["exam_year"] >= 2023]
    other  = [x for x in data if not is_final(x) and not is_written(x)]

    print(f"전체 {len(data)}개 분리:")
    dump("fire_최종합격.json", final)
    dump("fire_필기합격.json", written)
    dump("fire_2023이후.json", y2023)
    if other:
        dump("fire_기타구분.json", other)

    # exam_year 부여된 원본도 갱신 저장(다운스트림에서 연도 사용)
    dump(SRC, data)

    # 교차 통계
    fy = sum(1 for x in final if x["exam_year"] and x["exam_year"] >= 2023)
    print(f"\n참고: 최종합격 ∩ 2023이후 = {fy}개 | 응시연도 미상 = {sum(1 for x in data if x['exam_year'] is None)}개")

if __name__ == "__main__":
    main()
