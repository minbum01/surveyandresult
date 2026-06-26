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
Supabase Project URL = https://zxjhgcumweqaxcemoiga.supabase.co
anon public key      = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp4amhnY3Vtd2VxYXhjZW1vaWdhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI0MTExNjksImV4cCI6MjA5Nzk4NzE2OX0.vRETMCzDvd0HONqz9rlDXFqrF_ZQP_kp-wURphltsQo
관리자 이메일         = minbum01@gmail.com
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

---

## ✅ 연결 완료 (2026-06-26)
- [x] 프로젝트 생성 / 스키마 RUN (테이블 curation·print_jobs·stations 존재 확인)
- [x] 관리자 계정 (minbum01@gmail.com)
- [x] URL·anon 키 → `live/supa.js`에 입력 완료
- [x] (assistant 점검) REST로 curation·print_jobs 접근 OK, RLS 작동 확인
- 라이브 사이트(Vercel)에 supa.js 반영됨(push 시 자동 재배포)

## ⏭ 다음 (큐레이션을 라이브에 띄우려면)
- [ ] (assistant) 페이지에 supabase-js + supa.js 로드 + `curation_sync`를 Supabase 읽기로 전환 → **result.html 건드려서 결과페이지 터미널과 조율 필요**
- [ ] (나) 공무원 핀 작업 끝나면 → 내보낸 JSON을 Supabase `curation`(exam='공무원') 행에 주입 (assistant가 넣어줌)
- [ ] (나중) service_role 키 → 프린트 스테이션 PC에만

## 📒 진행 로그
- 2026-06-26: URL=zxjhgcumweqaxcemoiga / anon·관리자이메일 입력, 스키마·RLS 점검 통과, supa.js 연결.

## 🔌 큐레이션 ↔ Supabase 연동 완료 (2026-06-26)
- 결과페이지(result/police_result): supabase-js+supa.js 로드, `Curation.loadRemote()`로 **서버에서 핀 읽어 랜덤 출력**
- 관리자(no01): **☁ 서버 저장**(로그인 후 upsert) / **⬇ 서버 불러오기** 버튼 추가
- 라이브(Vercel) 재배포 확인됨
- **[나] 할 일: 관리자에서 `☁ 서버 저장` 1번 클릭(로그인=minbum01@gmail.com+비번) → 라이브에 핀 반영됨**

## 🖨️ 인쇄 모니터 실시간 + 스테이션 실행 (2026-06-27)
- (assistant) `print_admin.html` 폴링 → **Supabase Realtime 구독**으로 전환(끊김 대비 5초 백업 폴링 유지)
- (assistant) 스테이션 실행용 `print_station.bat` + `station_env.bat.example` 추가
- **[나] 할 일 ①** SQL Editor에서 **`supabase/migration_realtime.sql` RUN**
      → print_jobs·stations 를 realtime publication에 등록(이거 안 하면 모니터가 실시간으로 안 뜨고 5초 폴링만 됨)
- **[나] 할 일 ②** 프린트 스테이션 PC에서:
      1) `station_env.bat.example` 복사 → `station_env.bat`
      2) **service_role 키**(대시보드 → Settings → API → service_role 'secret') 를 `SUPABASE_SERVICE_KEY` 에 입력
      3) 2대면 한쪽 `STATION_ID=A`, 다른쪽 `B`
      4) `print_station.bat` 더블클릭 → 인쇄 모니터에서 🟢 가동 확인
      ⚠ `station_env.bat`(키 포함)은 .gitignore 처리됨 — 절대 커밋·웹업로드 금지
