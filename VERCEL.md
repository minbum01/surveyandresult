# VERCEL — 내가 할 일 (체크리스트 · 계속 누적)

> 이 문서 = **사람(나)이 직접 클릭해야 하는 것만** 모음. 코드/설정은 서버터미널이 함.
> 진행하면서 체크하고, 값 생기면 아래 "값" 칸에 적기. (assistant가 계속 갱신)

---

## 🎯 지금 할 것 (우선)
- [ ] **vercel.com** 접속 → **Continue with GitHub** 로그인
- [ ] **Add New… → Project** → 목록에서 **`minbum01/surveyandresult`** → **Import**
- [ ] 설정 그대로 (Framework: Other / Build·Output 비움) → **Deploy**
- [ ] 배포 끝나면 **URL 복사** → 아래 "값"에 붙이고 assistant에게 알려주기

## 📌 값 (생기면 기록)
```
Vercel 배포 URL = (예: https://surveyandresult-xxxx.vercel.app)
```

## ✅ 준비 완료된 것 (assistant가 이미 함)
- `vercel.json` — `/` → `/live/home.html` 리다이렉트, JSON/폰트 캐시 헤더
- `.vercelignore` — .py/.db/원본JSON/tools 제외 (웹만 배포)

## ⏭ 다음 (URL 나온 뒤)
- [ ] (assistant) `/live/home.html`·`result.html`·`police_result.html` 로딩 점검
- [ ] (assistant) supa.js 키 넣고 커밋 → **push하면 Vercel 자동 재배포**
- [ ] (나) **스탠바이미(태블릿) 실기기**에서 그 URL로 설문→결과 테스트
- [ ] (선택) 커스텀 도메인 연결

## 🧠 알아둘 것
- GitHub에 push할 때마다 **자동 재배포**됨 (따로 할 것 없음)
- 무료 100GB/월 — 행사 규모(500명) 여유

---

## 📒 진행 로그
- 2026-06-26: 문서 생성. vercel.json/.vercelignore 준비 완료. **Vercel Import+Deploy 대기 중.**
