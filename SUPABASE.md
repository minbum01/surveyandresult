# SUPABASE — 내가 할 일 (체크리스트 · 계속 누적)

> 이 문서 = **사람(나)이 직접 클릭해야 하는 것만** 모음. 스키마/연결 코드는 서버터미널이 함.
> ⚠️ **service_role 키는 절대 여기/깃에 적지 말 것** (비공개). anon 키·URL은 공개 OK.

---

## 🎯 지금 할 것 (우선)
- [ ] **supabase.com** → **New project** (지역 Seoul/Tokyo, DB 비밀번호 설정·따로 메모)
- [ ] 왼쪽 **SQL Editor → New query** → 프로젝트의 **`supabase/schema.sql` 전체** 복붙 → **RUN**
      - 파일: `C:\Users\admin\Documents\이민범 개발\설명회\supabase\schema.sql`
      - 성공 시 테이블 3개(curation·print_jobs·stations) + 함수들 생성됨
- [ ] **Authentication → Users → Add user** → 관리자 **이메일/비번 1개** 생성 (큐레이션 저장·인쇄관리자 로그인용)
- [ ] **Settings → API** 에서 복사 → 아래 "값"에 + assistant에게 전달:
      - **Project URL**
      - **anon public** 키 (공개 OK)

## 📌 값 (생기면 기록 — service_role 금지)
```
Supabase Project URL = https://____.supabase.co
anon public key      = eyJ____
관리자 이메일         = ____
(DB 비번/ service_role 키 = 여기 적지 말 것, 따로 안전하게 보관)
```

## ✅ 준비 완료된 것 (assistant가 이미 함)
- `supabase/schema.sql` — curation/print_jobs/stations + RPC(enqueue/claim/complete/fail/requeue) + RLS
- `live/supa.js` — 클라이언트 (URL·anon 받으면 assistant가 채움)
- `live/curation_sync.js` — 시험별 저장소 분리(공무원/경찰) 준비됨

## ⏭ 다음 (URL·anon 받은 뒤)
- [ ] (assistant) `live/supa.js`에 URL·anon 입력 → 커밋
- [ ] (assistant) 각 페이지에 supabase-js + supa.js 로드, curation_sync를 Supabase 읽기로 전환 (결과페이지 터미널과 조율)
- [ ] (assistant) 관리자 페이지 로그인 게이트 + 핀 저장을 Supabase로
- [ ] (나) 핀 작업 끝난 큐레이션 JSON을 Supabase `curation` 테이블에 주입 (공무원/경찰 각 행)
- [ ] (나중) **service_role 키 → 프린트 스테이션 PC 환경변수에만** (print_agent.py용)

## 🧠 알아둘 것
- 키 3종 용도: **anon**=프런트(공개) / **로그인**=관리자 쓰기 / **service_role**=스테이션(절대 비공개)
- 큐레이션은 시험별 행(`exam='공무원'`/`'경찰'`)으로 분리 저장

---

## 📒 진행 로그
- 2026-06-26: 문서 생성. schema.sql·supa.js·exam분리 준비 완료. **Supabase 프로젝트 생성+스키마 RUN+키 전달 대기 중.**
