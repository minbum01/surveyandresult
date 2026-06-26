@echo off
REM ───────────────────────────────────────────────────────────────
REM  프린터 2대 동시 운영 — 인스턴스 2개(A/B)를 각각 새 창으로 실행
REM  큐(SKIP LOCKED)가 두 인스턴스에 작업을 자동 분배 → 병렬 출력(밀림 방지)
REM
REM  먼저 station_env.bat 에 PRINTER_A / PRINTER_B (각 프린터 정확한 이름) 입력 필수.
REM  창 2개가 뜸. 둘 다 켜둔 채로 행사 진행. 닫으면 그 프린터만 멈춤.
REM ───────────────────────────────────────────────────────────────
cd /d "%~dp0"

if not exist "station_env.bat" (
  echo  [!] station_env.bat 가 없습니다. station_env.bat.example 복사 후 값 입력하세요.
  pause
  exit /b 1
)

start "Print Station A" cmd /k print_station.bat A
start "Print Station B" cmd /k print_station.bat B

echo  스테이션 A/B 두 창을 띄웠습니다. 인쇄 모니터에서 둘 다 초록불인지 확인하세요.
echo  (이 창은 닫아도 됩니다)
timeout /t 5 >nul
