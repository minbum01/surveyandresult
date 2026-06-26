# VERCEL — 내가 할 일 (체크리스트 · 계속 누적)

> 사람(나)이 직접 클릭하는 것만 모음. 코드/설정은 서버터미널이 함.

---

## ✅ 배포 완료! (2026-06-26)
- **라이브 URL = https://surveyandresult.vercel.app/**
- [x] vercel.com 로그인 / Import / Deploy
- [x] (assistant 점검) home·result·police_result + reviews_data.json·police/fire 데이터·폰트 **전부 200 정상**

## 🧠 지금 라이브 사이트 상태
- 설문→결과는 **자동매칭으로** 잘 뜸. **단, 핀(큐레이션)은 아직 안 보임** — 핀은 지금 "관리자 브라우저의 localStorage"에만 있고, 배포 사이트는 그걸 못 읽어서. → **Supabase 연결하면 핀도 라이브에 반영됨** (SUPABASE.md 참고).

## ⏭ 다음
- [x] (assistant) 페이지 로딩 점검 — **이상없음 확인 완료**
- [ ] (assistant) Supabase 키 받으면 → `supa.js`에 넣고 **git push** → **Vercel이 자동 재배포** (나는 클릭 안 함)
- [ ] (나) 나중에 **스탠바이미(태블릿)** 에서 위 URL로 설문→결과 실기기 테스트
- (커스텀 도메인은 불필요 — 스킵)

## 🧠 알아둘 것
- **GitHub push = 자동 재배포.** 한 번 연결해놨으니 앞으론 코드 바뀔 때마다 사이트 알아서 갱신.
- 무료 100GB/월 — 500명 행사 여유.

---

## 📒 진행 로그
- 2026-06-26: vercel.json/.vercelignore 준비.
- 2026-06-26: **배포 성공** → https://surveyandresult.vercel.app/ · 전 경로 200 점검 완료.
- 2026-06-26: 다음 = Supabase 키 받아 supa.js 연결(=push 시 자동 재배포).
